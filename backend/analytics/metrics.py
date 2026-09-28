"""Fund performance and risk metrics computed from the paper book.

Daily returns come from the last equity snapshot of each day (the first day is measured against
initial capital). The risk-free rate is the 13-week T-bill yield (^IRX); the benchmark is SPY.
Statistics that need a longer history are returned but flagged in ``warnings``.
"""
import asyncio
import datetime
import math
import time
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import select, text

from backend.config import settings
from backend.db.models import Trade, Position, CashLedger, AccountBalance
from backend.db.session import async_session_factory
from backend.market.data import BENCHMARK, daily_closes

TRADING_DAYS = 252
MIN_DAYS_FOR_ANNUALIZED = 20

_cache: Dict = {"at": 0.0, "value": None}
CACHE_SEC = 60


def _r(x, n=4):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), n)


async def _daily_equity() -> pd.Series:
    async with async_session_factory() as session:
        rows = (await session.execute(text(
            "SELECT timestamp, total_equity FROM portfolio_snapshots WHERE id IN "
            "(SELECT MAX(id) FROM portfolio_snapshots GROUP BY date(timestamp)) ORDER BY timestamp"
        ))).all()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows]).normalize()
    return pd.Series([float(r[1]) for r in rows], index=idx)


def return_stats(equity: pd.Series, initial: float, bench: Optional[pd.Series], rf_annual: float) -> Dict:
    """Pure function over a daily equity series; separated for testing."""
    out: Dict = {}
    if equity.empty:
        return out
    full = pd.concat([pd.Series([initial], index=[equity.index[0] - pd.Timedelta(days=1)]), equity])
    rets = full.pct_change().dropna()
    n = len(rets)
    rf_d = (1 + rf_annual) ** (1 / TRADING_DAYS) - 1
    total = equity.iloc[-1] / initial - 1

    out["days"] = n
    out["total_return"] = _r(total)
    out["annualized_return"] = _r((1 + total) ** (TRADING_DAYS / n) - 1) if n >= MIN_DAYS_FOR_ANNUALIZED else None
    if n >= 2:
        vol = rets.std(ddof=1)
        excess = rets - rf_d
        downside = np.sqrt((np.minimum(excess, 0) ** 2).mean())
        out["annualized_volatility"] = _r(vol * math.sqrt(TRADING_DAYS))
        out["sharpe_ratio"] = _r(excess.mean() / vol * math.sqrt(TRADING_DAYS)) if vol > 0 else None
        out["sortino_ratio"] = _r(excess.mean() / downside * math.sqrt(TRADING_DAYS)) if downside > 0 else None
    peak = full.cummax()
    dd = full / peak - 1
    out["max_drawdown"] = _r(-dd.min())
    out["current_drawdown"] = _r(-dd.iloc[-1])
    longest, run = 0, 0
    for v in dd.values:
        run = run + 1 if v < 0 else 0
        longest = max(longest, run)
    out["max_drawdown_duration_days"] = longest
    if out.get("annualized_return") is not None and out["max_drawdown"]:
        out["calmar_ratio"] = _r(out["annualized_return"] / out["max_drawdown"])
    out["best_day"] = _r(rets.max())
    out["worst_day"] = _r(rets.min())
    out["positive_days_pct"] = _r((rets > 0).mean())
    if n >= MIN_DAYS_FOR_ANNUALIZED:
        cutoff = np.percentile(rets, 5)
        out["var_95_1d"] = _r(-cutoff)
        out["cvar_95_1d"] = _r(-rets[rets <= cutoff].mean())

    if bench is not None and len(bench):
        b = bench.pct_change().reindex(rets.index).dropna()
        pair = pd.concat([rets, b], axis=1, join="inner").dropna()
        pair.columns = ["p", "b"]
        bench_total = (1 + b).prod() - 1 if len(b) else None
        out["benchmark_return"] = _r(bench_total)
        out["excess_return"] = _r(total - bench_total) if bench_total is not None else None
        if len(pair) >= 5 and pair["b"].var() > 0:
            beta = pair["p"].cov(pair["b"]) / pair["b"].var()
            alpha_d = (pair["p"] - rf_d).mean() - beta * (pair["b"] - rf_d).mean()
            active = pair["p"] - pair["b"]
            te = active.std(ddof=1) * math.sqrt(TRADING_DAYS)
            out["beta"] = _r(beta)
            out["alpha_annualized"] = _r(alpha_d * TRADING_DAYS)
            out["correlation"] = _r(pair["p"].corr(pair["b"]))
            out["tracking_error"] = _r(te)
            out["information_ratio"] = _r(active.mean() * TRADING_DAYS / te) if te > 0 else None
    return out


def trade_stats(trades: List[Trade]) -> Dict:
    closes = [t for t in trades if t.side in ("SELL", "COVER")]
    opens = [t for t in trades if t.side in ("BUY", "SHORT")]
    out: Dict = {"closed_trades": len(closes), "opening_trades": len(opens)}
    if not closes:
        return out
    pnl = np.array([t.realized_pnl or 0.0 for t in closes])
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    out["win_rate"] = _r(len(wins) / len(pnl))
    out["gross_profit"] = _r(wins.sum(), 2)
    out["gross_loss"] = _r(losses.sum(), 2)
    out["profit_factor"] = _r(wins.sum() / -losses.sum()) if len(losses) else None
    out["average_win"] = _r(wins.mean(), 4) if len(wins) else None
    out["average_loss"] = _r(losses.mean(), 4) if len(losses) else None
    out["payoff_ratio"] = _r(wins.mean() / -losses.mean()) if len(wins) and len(losses) else None
    out["expectancy_per_trade"] = _r(pnl.mean(), 4)
    for side, label in (("SELL", "long"), ("COVER", "short")):
        sp = np.array([t.realized_pnl or 0.0 for t in closes if t.side == side])
        out[f"{label}_trades"] = int(len(sp))
        out[f"{label}_win_rate"] = _r((sp > 0).mean()) if len(sp) else None

    # Holding period: each close paired with the latest open of the same symbol and direction before it
    holds = []
    for c in closes:
        open_side = "BUY" if c.side == "SELL" else "SHORT"
        prior = [o for o in opens if o.symbol == c.symbol and o.side == open_side and o.timestamp <= c.timestamp]
        if prior:
            holds.append((c.timestamp - max(prior, key=lambda o: o.timestamp).timestamp).total_seconds() / 86400)
    out["average_holding_days"] = _r(sum(holds) / len(holds), 2) if holds else None
    return out


async def compute_metrics(force: bool = False) -> Dict:
    if not force and _cache["value"] and time.time() - _cache["at"] < CACHE_SEC:
        return _cache["value"]

    async with async_session_factory() as session:
        acc = (await session.execute(select(AccountBalance))).scalars().first()
        trades = (await session.execute(select(Trade).order_by(Trade.timestamp))).scalars().all()
        positions = (await session.execute(select(Position))).scalars().all()
        ledger = (await session.execute(select(CashLedger))).scalars().all()
    initial = acc.initial_capital if acc else settings.PAPER_INITIAL_CASH

    equity = await _daily_equity()
    bench, rf = None, 0.0
    try:
        mkt = await asyncio.to_thread(daily_closes, [BENCHMARK, "^IRX"], "1y")
        if BENCHMARK in mkt:
            bench = mkt[BENCHMARK].dropna().copy()
            idx = pd.to_datetime(bench.index)
            bench.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
            if len(equity):
                bench = bench[bench.index >= equity.index[0] - pd.Timedelta(days=7)]
        if "^IRX" in mkt and mkt["^IRX"].notna().any():
            rf = float(mkt["^IRX"].dropna().iloc[-1]) / 100
    except Exception:
        pass

    long_v = sum(p.market_value for p in positions if p.qty > 0)
    short_v = -sum(p.market_value for p in positions if p.qty < 0)
    cash = acc.cash if acc else initial
    equity_now = cash + long_v - short_v

    fees = sum(t.fees or 0 for t in trades)
    commissions = sum(t.commission or 0 for t in trades)
    spread = sum(t.slippage or 0 for t in trades)
    borrow = -sum(l.amount for l in ledger if l.kind == "BORROW_FEE")
    traded = sum(t.total_cost or 0 for t in trades)
    avg_equity = float(equity.mean()) if len(equity) else equity_now
    n_days = max(1, len(equity))

    # Attribution: realized on closes + unrealized on open positions
    by_cat, by_agent = defaultdict(float), defaultdict(float)
    for t in trades:
        if t.side in ("SELL", "COVER"):
            by_cat[t.catalyst or "UNKNOWN"] += t.realized_pnl or 0
            by_agent[t.agent_name or "manual"] += t.realized_pnl or 0
    for p in positions:
        by_cat[p.catalyst or "UNKNOWN"] += p.unrealized_pnl or 0
        by_agent[p.agent_name or "manual"] += p.unrealized_pnl or 0

    warnings = []
    if len(equity) < MIN_DAYS_FOR_ANNUALIZED:
        warnings.append(f"Only {len(equity)} trading day(s) of history; annualized figures, VaR and ratios "
                        f"are unreliable until at least {MIN_DAYS_FOR_ANNUALIZED}.")
    if settings.ALLOW_SHORTS and equity_now < 2000:
        warnings.append("Real brokers require $2,000 of margin equity before any short sale (FINRA); "
                        "this account shorts in simulation below that level.")
    if any(t.quote_source == "MODELED_SPREAD" for t in trades):
        warnings.append("Some fills used a modeled spread because no live bid/ask was available.")

    curve = []
    if len(equity):
        b0 = None
        for d, v in equity.items():
            bv = None
            if bench is not None:
                prior = bench[bench.index <= d]
                if len(prior):
                    b0 = b0 or float(prior.iloc[-1])
                    bv = round(float(prior.iloc[-1]) / b0 * initial, 4)
            curve.append({"date": d.date().isoformat(), "equity": round(v, 4), "benchmark": bv})

    result = {
        "as_of": datetime.datetime.now(datetime.UTC).isoformat(),
        "initial_capital": initial,
        "equity": round(equity_now, 4),
        "benchmark": BENCHMARK,
        "risk_free_rate": _r(rf),
        "returns": return_stats(equity, initial, bench, rf),
        "trading": trade_stats(trades),
        "exposure": {
            "long_value": _r(long_v, 2), "short_value": _r(short_v, 2), "cash": _r(cash, 2),
            "gross": _r((long_v + short_v) / equity_now) if equity_now > 0 else None,
            "net": _r((long_v - short_v) / equity_now) if equity_now > 0 else None,
            "long_positions": sum(1 for p in positions if p.qty > 0),
            "short_positions": sum(1 for p in positions if p.qty < 0),
        },
        "costs": {
            "commissions": _r(commissions, 4), "regulatory_fees": _r(fees, 4),
            "spread_paid": _r(spread, 4), "borrow_fees": _r(borrow, 4),
            "total": _r(commissions + fees + spread + borrow, 4),
            "total_pct_of_initial": _r((commissions + fees + spread + borrow) / initial) if initial else None,
            "live_quote_fills": sum(1 for t in trades if t.quote_source == "LIVE_QUOTE"),
            "modeled_spread_fills": sum(1 for t in trades if t.quote_source == "MODELED_SPREAD"),
        },
        "turnover": {
            "traded_notional": _r(traded, 2),
            "turnover_multiple": _r(traded / avg_equity) if avg_equity else None,
            "annualized_turnover": _r(traded / avg_equity * TRADING_DAYS / n_days) if avg_equity else None,
        },
        "attribution_by_catalyst": {k: round(v, 4) for k, v in sorted(by_cat.items(), key=lambda kv: kv[1])},
        "attribution_by_agent": {k: round(v, 4) for k, v in sorted(by_agent.items(), key=lambda kv: kv[1])},
        "equity_curve": curve,
        "warnings": warnings,
    }
    _cache.update(at=time.time(), value=result)
    return result
