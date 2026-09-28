import asyncio
import datetime
import json
import logging
import math
import urllib.request
from typing import Dict, Any, Optional, Tuple

import pandas as pd
import yfinance as yf
from sqlalchemy import select, func

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.models import Signal

logger = logging.getLogger("alphaforge.forensic_agent")

BENEISH_THRESHOLD = -1.78  # 8-variable model cutoff


def _row(df: Optional[pd.DataFrame], names, col: int = 0) -> Optional[float]:
    """Returns a statement value for the given column (0 = latest year), or None if unavailable."""
    if df is None or df.empty or df.shape[1] <= col:
        return None
    for name in ([names] if isinstance(names, str) else names):
        if name in df.index:
            try:
                val = float(df.loc[name].iloc[col])
            except (TypeError, ValueError):
                continue
            if not math.isnan(val):
                return val
    return None


def _div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def get_live_price(ticker: str) -> float:
    """Last traded price from Yahoo; 0.0 if it cannot be fetched (callers must treat 0 as 'no price')."""
    ticker = ticker.upper().strip()
    try:
        p = yf.Ticker(ticker).fast_info.get("last_price")
        if p and float(p) > 0:
            return float(p)
    except Exception:
        pass
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            meta = json.loads(resp.read().decode()).get("chart", {}).get("result", [{}])[0].get("meta", {})
            p = meta.get("regularMarketPrice")
            if p and float(p) > 0:
                return float(p)
    except Exception:
        pass
    return 0.0


class ForensicQuantAgent(BaseAgent):
    """
    Computes Piotroski F-Score, Beneish M-Score (8-variable), Altman Z-Score and Sloan accruals
    from Yahoo Finance annual statements. Any score whose inputs are missing is reported as None
    and never replaced with a default.
    """
    def __init__(self):
        super().__init__(
            name="forensic_quant_agent",
            display_name="Forensic Quant & Quality Screener",
            interval_seconds=settings.POLLING_INTERVAL_QUANT
        )
        self.universe = ["PLTR", "SOUN", "HIMS", "SMCI", "BBAI", "RKLB", "IONQ", "ASTS", "JOBY", "ACHR"]

    async def run_iteration(self):
        await self.log("INFO", f"Running forensic quant scan across universe of {len(self.universe)} tickers...")
        scanned = 0

        for ticker in self.universe:
            try:
                metrics = await asyncio.to_thread(self.analyze_ticker, ticker)
                if "error" in metrics:
                    await self.log("WARNING", f"Skipping {ticker}: {metrics['error']}", ticker=ticker)
                    continue
                scanned += 1

                f_score = metrics["piotroski_f_score"]
                m_score = metrics["beneish_m_score"]
                z_score = metrics["altman_z_score"]

                if f_score is not None and z_score is not None and m_score is not None \
                        and f_score >= 7 and z_score > 2.99 and m_score < BENEISH_THRESHOLD:
                    catalyst, action, conf, horizon = "FORENSIC_HIGH_QUALITY", "BUY", 0.80, 90
                    title = f"Forensic quality screen passed: {ticker}"
                elif (m_score is not None and m_score > BENEISH_THRESHOLD) or (f_score is not None and f_score <= 2):
                    catalyst, action, conf, horizon = "ACCOUNTING_RED_FLAG", "SHORT", 0.84, 60
                    title = f"Forensic red flag: {ticker}"
                else:
                    continue

                # Statements change yearly; don't re-emit the same verdict every scan
                if await self._emitted_recently(ticker, catalyst, days=30):
                    continue

                await self.emit_signal(
                    ticker=ticker,
                    catalyst_type=catalyst,
                    action=action,
                    confidence=conf,
                    title=title,
                    summary=(f"Piotroski F: {f_score}/9 ({metrics['piotroski_tests_evaluated']} tests with data) | "
                             f"Altman Z: {z_score} | Beneish M: {m_score} "
                             f"(fiscal year ending {metrics['fiscal_year_end']})"),
                    metadata={**metrics, "horizon_days": horizon}
                )
            except Exception as e:
                logger.error(f"Error scanning ticker {ticker}: {e}")

        await self.update_status("RUNNING", stats={"scanned_tickers": scanned, "universe": len(self.universe)})

    async def _emitted_recently(self, ticker: str, catalyst: str, days: int) -> bool:
        since = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)
        async with async_session_factory() as session:
            res = await session.execute(
                select(func.count(Signal.id)).where(
                    Signal.ticker == ticker, Signal.catalyst_type == catalyst, Signal.timestamp >= since
                )
            )
            return (res.scalar() or 0) > 0

    def analyze_ticker(self, ticker: str) -> Dict[str, Any]:
        """Scores a ticker from its latest annual statements. Returns {'error': ...} if data is unavailable."""
        ticker = ticker.upper().strip()
        try:
            stock = yf.Ticker(ticker)
            fin, bs, cf = stock.financials, stock.balance_sheet, stock.cashflow
        except Exception as e:
            return {"ticker": ticker, "error": f"Could not download statements: {e}"}

        if fin is None or fin.empty or bs is None or bs.empty or cf is None or cf.empty:
            return {"ticker": ticker, "error": "No financial statements available"}

        try:
            info = stock.info or {}
        except Exception:
            info = {}

        current_price = get_live_price(ticker)
        if current_price <= 0:
            return {"ticker": ticker, "error": "No live price available"}

        shares = _row(bs, ["Ordinary Shares Number", "Share Issued"])
        market_cap = info.get("marketCap") or (shares * current_price if shares else None)

        f_score, f_tests, f_breakdown = self._calc_piotroski_f_score(fin, bs, cf)
        m_score, m_breakdown = self._calc_beneish_m_score(fin, bs, cf)
        z_score = self._calc_altman_z_score(fin, bs, market_cap)
        accrual_ratio = self._calc_accruals_ratio(fin, bs, cf)

        if f_score is not None and z_score is not None and m_score is not None:
            if f_score >= 7 and z_score > 2.99 and m_score < BENEISH_THRESHOLD:
                recommendation = "STRONG_BUY"
            elif m_score > BENEISH_THRESHOLD or f_score <= 2 or z_score < 1.81:
                recommendation = "AVOID/SHORT"
            elif f_score >= 6 and z_score > 1.81:
                recommendation = "BUY"
            else:
                recommendation = "HOLD"
        else:
            recommendation = "INSUFFICIENT_DATA"

        short_pct = info.get("shortPercentOfFloat")
        latest = fin.columns[0]
        fiscal_year_end = latest.date().isoformat() if hasattr(latest, "date") else str(latest)

        return {
            "ticker": ticker,
            "company_name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "current_price": round(current_price, 2),
            "market_cap": market_cap,
            "pe_ratio": round(info["trailingPE"], 2) if info.get("trailingPE") else None,
            "forward_pe": round(info["forwardPE"], 2) if info.get("forwardPE") else None,
            "price_to_book": round(info["priceToBook"], 2) if info.get("priceToBook") else None,
            "fiscal_year_end": fiscal_year_end,
            "piotroski_f_score": f_score,
            "piotroski_tests_evaluated": f_tests,
            "piotroski_breakdown": f_breakdown,
            "beneish_m_score": round(m_score, 2) if m_score is not None else None,
            "beneish_breakdown": m_breakdown,
            "altman_z_score": round(z_score, 2) if z_score is not None else None,
            "altman_zone": ("Unknown" if z_score is None else
                            "Safe" if z_score > 2.99 else ("Distress" if z_score < 1.81 else "Grey")),
            "sloan_accrual_ratio": round(accrual_ratio, 4) if accrual_ratio is not None else None,
            "earnings_quality": ("Unknown" if accrual_ratio is None or m_score is None else
                                 "High" if accrual_ratio < 0.05 and m_score < BENEISH_THRESHOLD else "Low"),
            "short_float_pct": round(short_pct * 100, 2) if short_pct else None,
            "recommendation": recommendation
        }

    def _calc_piotroski_f_score(self, fin, bs, cf) -> Tuple[Optional[int], int, Dict[str, Optional[bool]]]:
        """Nine binary tests (Piotroski 2000). Returns (score, tests_with_data, breakdown).
        Score is None if fewer than 7 tests have data."""
        shares_rows = ["Ordinary Shares Number", "Share Issued"]
        ni0, ni1 = _row(fin, "Net Income", 0), _row(fin, "Net Income", 1)
        cfo0 = _row(cf, "Operating Cash Flow", 0)
        ta0, ta1, ta2 = _row(bs, "Total Assets", 0), _row(bs, "Total Assets", 1), _row(bs, "Total Assets", 2)
        ltd0, ltd1 = _row(bs, "Long Term Debt", 0), _row(bs, "Long Term Debt", 1)
        ca0, ca1 = _row(bs, "Current Assets", 0), _row(bs, "Current Assets", 1)
        cl0, cl1 = _row(bs, "Current Liabilities", 0), _row(bs, "Current Liabilities", 1)
        sh0, sh1 = _row(bs, shares_rows, 0), _row(bs, shares_rows, 1)
        gp0, gp1 = _row(fin, "Gross Profit", 0), _row(fin, "Gross Profit", 1)
        rev0, rev1 = _row(fin, "Total Revenue", 0), _row(fin, "Total Revenue", 1)

        # Ratios use beginning-of-year assets where available
        prior_ta1 = ta2 if ta2 is not None else ta1
        roa0, roa1 = _div(ni0, ta1), _div(ni1, prior_ta1)
        lev0, lev1 = _div(ltd0, ta0), _div(ltd1, ta1)
        cr0, cr1 = _div(ca0, cl0), _div(ca1, cl1)
        gm0, gm1 = _div(gp0, rev0), _div(gp1, rev1)
        at0, at1 = _div(rev0, ta1), _div(rev1, prior_ta1)

        def cmp(a, b, fn):
            return None if a is None or b is None else bool(fn(a, b))

        breakdown = {
            "positive_net_income": None if ni0 is None else ni0 > 0,
            "positive_operating_cash_flow": None if cfo0 is None else cfo0 > 0,
            "roa_improved": cmp(roa0, roa1, lambda a, b: a > b),
            "cash_flow_exceeds_net_income": cmp(cfo0, ni0, lambda a, b: a > b),
            "leverage_decreased": cmp(lev0, lev1, lambda a, b: a <= b),
            "current_ratio_improved": cmp(cr0, cr1, lambda a, b: a > b),
            "no_share_dilution": cmp(sh0, sh1, lambda a, b: a <= b),
            "gross_margin_improved": cmp(gm0, gm1, lambda a, b: a > b),
            "asset_turnover_improved": cmp(at0, at1, lambda a, b: a > b),
        }
        evaluated = [v for v in breakdown.values() if v is not None]
        if len(evaluated) < 7:
            return None, len(evaluated), breakdown
        return sum(evaluated), len(evaluated), breakdown

    def _calc_beneish_m_score(self, fin, bs, cf) -> Tuple[Optional[float], Dict[str, Any]]:
        """Beneish (1999) 8-variable M-Score. None if any input is missing."""
        missing = {"threshold": BENEISH_THRESHOLD, "manipulation_risk": "Unknown", "missing_inputs": True}
        dep_rows = ["Depreciation And Amortization", "Depreciation Amortization Depletion"]
        ar_rows = ["Accounts Receivable", "Receivables"]
        ni_rows = ["Net Income From Continuing Operation Net Minority Interest", "Net Income"]

        rev0, rev1 = _row(fin, "Total Revenue", 0), _row(fin, "Total Revenue", 1)
        ar0, ar1 = _row(bs, ar_rows, 0), _row(bs, ar_rows, 1)
        gp0, gp1 = _row(fin, "Gross Profit", 0), _row(fin, "Gross Profit", 1)
        ca0, ca1 = _row(bs, "Current Assets", 0), _row(bs, "Current Assets", 1)
        ppe0, ppe1 = _row(bs, "Net PPE", 0), _row(bs, "Net PPE", 1)
        ta0, ta1 = _row(bs, "Total Assets", 0), _row(bs, "Total Assets", 1)
        dep0 = _row(cf, dep_rows, 0)
        dep1 = _row(cf, dep_rows, 1)
        sga0, sga1 = _row(fin, "Selling General And Administration", 0), _row(fin, "Selling General And Administration", 1)
        cl0, cl1 = _row(bs, "Current Liabilities", 0), _row(bs, "Current Liabilities", 1)
        ltd0, ltd1 = _row(bs, "Long Term Debt", 0), _row(bs, "Long Term Debt", 1)
        ni0 = _row(fin, ni_rows, 0)
        cfo0 = _row(cf, "Operating Cash Flow", 0)

        required = [rev0, rev1, ar0, ar1, gp0, gp1, ca0, ca1, ppe0, ppe1, ta0, ta1,
                    dep0, dep1, sga0, sga1, cl0, cl1, ni0, cfo0]
        if any(v is None for v in required):
            return None, missing
        # The model's ratios are meaningless for pre-revenue firms or negative gross margins
        if rev1 < 10_000_000 or gp0 <= 0 or gp1 <= 0:
            return None, {**missing, "missing_inputs": False, "not_applicable": "pre-revenue or negative gross margin"}
        # A company with no long-term debt reports no row; that is a real zero
        ltd0, ltd1 = ltd0 or 0.0, ltd1 or 0.0

        try:
            dsri = (ar0 / rev0) / (ar1 / rev1)
            gmi = (gp1 / rev1) / (gp0 / rev0)
            aqi = (1 - (ca0 + ppe0) / ta0) / (1 - (ca1 + ppe1) / ta1)
            sgi = rev0 / rev1
            depi = (dep1 / (dep1 + ppe1)) / (dep0 / (dep0 + ppe0))
            sgai = (sga0 / rev0) / (sga1 / rev1)
            lvgi = ((cl0 + ltd0) / ta0) / ((cl1 + ltd1) / ta1)
            tata = (ni0 - cfo0) / ta0
        except ZeroDivisionError:
            return None, missing

        m = (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
             + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
        return float(m), {
            "DSRI": round(dsri, 3), "GMI": round(gmi, 3), "AQI": round(aqi, 3), "SGI": round(sgi, 3),
            "DEPI": round(depi, 3), "SGAI": round(sgai, 3), "LVGI": round(lvgi, 3), "TATA": round(tata, 4),
            "manipulation_risk": "High" if m > BENEISH_THRESHOLD else "Low",
            "threshold": BENEISH_THRESHOLD
        }

    def _calc_altman_z_score(self, fin, bs, market_cap: Optional[float]) -> Optional[float]:
        """Altman (1968) Z-Score. None if any input is missing."""
        ta = _row(bs, "Total Assets")
        tl = _row(bs, "Total Liabilities Net Minority Interest")
        wc = _row(bs, "Working Capital")
        if wc is None:
            ca, cl = _row(bs, "Current Assets"), _row(bs, "Current Liabilities")
            wc = ca - cl if ca is not None and cl is not None else None
        re_ = _row(bs, "Retained Earnings")
        ebit = _row(fin, "EBIT")
        rev = _row(fin, "Total Revenue")
        if any(v is None for v in (ta, tl, wc, re_, ebit, rev, market_cap)) or not ta or not tl:
            return None
        return float(1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta + 0.6 * market_cap / tl + 1.0 * rev / ta)

    def _calc_accruals_ratio(self, fin, bs, cf) -> Optional[float]:
        """Sloan accruals: (net income - operating cash flow) / average total assets."""
        ni = _row(fin, "Net Income")
        cfo = _row(cf, "Operating Cash Flow")
        ta0, ta1 = _row(bs, "Total Assets", 0), _row(bs, "Total Assets", 1)
        if ni is None or cfo is None or ta0 is None:
            return None
        avg_ta = (ta0 + ta1) / 2 if ta1 is not None else ta0
        return _div(ni - cfo, avg_ta)

forensic_agent = ForensicQuantAgent()
