import asyncio
import datetime
import json
import logging
import math
from typing import Dict, List, Optional

from sqlalchemy import select, update

from backend.agents.base import BaseAgent
from backend.agents.forensic_quant import get_live_price, forensic_agent
from backend.config import settings
from backend.db.models import Signal, Position, CatalystPerformance, BossDirective, PortfolioSnapshot
from backend.db.session import async_session_factory, commit_with_retry
from backend.execution.alpaca_client import alpaca_client
from backend.execution.paper_engine import paper_engine, _aware
from backend.market.data import get_quote, is_market_open, NY, Quote

logger = logging.getLogger("alphaforge.cio_agent")

SIGNAL_MAX_AGE = datetime.timedelta(days=3)
OTC_EXCHANGES = {"PNK", "OQB", "OQX", "OEM", "OTC", "OBB", "OTCQB", "OTCQX", "PINK"}
TRADABLE_TYPES = {"EQUITY", "ETF"}


def _get_live_price_sync(ticker: str) -> float:
    return get_live_price(ticker)


async def get_regime() -> Dict:
    """Latest regime published by the regime agent (neutral defaults if none yet)."""
    async with async_session_factory() as session:
        d = (await session.execute(select(BossDirective).where(BossDirective.directive_key == "MARKET_REGIME"))).scalars().first()
    if d and d.value:
        try:
            return json.loads(d.value)
        except ValueError:
            pass
    return {"regime": "UNKNOWN", "risk_multiplier": 0.75, "allow_new_longs": True, "target_beta": 0.6}


class CioRiskAgent(BaseAgent):
    """
    Portfolio manager and risk officer for the long/short book.

    Turns agent signals into positions under hard limits: per-name size, sector concentration,
    gross and net exposure, a daily loss circuit breaker, the market regime's risk multiplier,
    shortability rules and forensic/red-flag vetoes. Fills only during the regular session.
    """
    def __init__(self):
        super().__init__(
            name="cio_risk_agent",
            display_name="CIO & Risk Manager",
            interval_seconds=30
        )
        self._last_snapshot = None

    async def run_iteration(self):
        if is_market_open():
            await paper_engine.accrue_borrow_fees()
            await self._update_open_positions_mtm()
            await self._process_unhandled_signals()
        else:
            await self.log("INFO", "Market closed: no fills until the next regular session. Signals remain queued.")
        # Equity only moves in session; off-hours a snapshot every 30 minutes is plenty
        now = datetime.datetime.now(datetime.UTC)
        if is_market_open() or self._last_snapshot is None or now - self._last_snapshot > datetime.timedelta(minutes=30):
            await paper_engine.record_snapshot()
            self._last_snapshot = now
        await self.update_status("RUNNING")

    async def _update_open_positions_mtm(self):
        async with async_session_factory() as session:
            symbols = [p.symbol for p in (await session.execute(select(Position))).scalars().all()]
        if not symbols:
            return
        prices = await asyncio.gather(*[asyncio.to_thread(_get_live_price_sync, s) for s in symbols])
        price_map = {s: p for s, p in zip(symbols, prices) if p > 0}
        if price_map:
            await paper_engine.update_position_prices(price_map)

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    async def _process_unhandled_signals(self):
        now = datetime.datetime.now(datetime.UTC)
        async with async_session_factory() as session:
            raw = (await session.execute(select(Signal).where(Signal.processed == False).order_by(Signal.timestamp.asc()))).scalars().all()
            if not raw:
                return
            expired = {s.id for s in raw if now - _aware(s.timestamp) > SIGNAL_MAX_AGE}
            if expired:
                await session.execute(update(Signal).where(Signal.id.in_(expired)).values(processed=True))
                await commit_with_retry(session)
            fresh = [s for s in raw if s.id not in expired]
            if not fresh:
                return
            signals = [dict(id=s.id, ticker=s.ticker.upper(), action=s.action.upper(), conf=s.confidence,
                            catalyst=s.catalyst_type, title=s.title, agent=s.agent_name,
                            meta=json.loads(s.raw_metadata or "{}")) for s in fresh]
            red_flags = set((await session.execute(select(Signal.ticker).where(
                Signal.catalyst_type == "ACCOUNTING_RED_FLAG", Signal.timestamp >= now - datetime.timedelta(days=7)))).scalars().all())
            weights = {p.catalyst_type: p.calibrated_weight for p in (await session.execute(select(CatalystPerformance))).scalars().all()}

        candidates = []
        for sig in signals:
            held = await self._position(sig["ticker"])
            action = sig["action"]
            # Exits first: a bearish view closes longs, a bullish view closes shorts
            if action in ("SELL", "SHORT") and held and held.qty > 0:
                await self._close(held, "SELL", f"{sig['catalyst']}: {sig['title']}", sig)
            if action in ("BUY", "COVER") and held and held.qty < 0:
                await self._close(held, "COVER", f"{sig['catalyst']}: {sig['title']}", sig)
            if action in ("BUY", "SHORT"):
                w = weights.get(sig["catalyst"], 1.0)
                sig["effective_conf"] = min(0.98, max(0.2, sig["conf"] * w))
                candidates.append(sig)

        if candidates:
            await self._open_positions(candidates, red_flags)

        async with async_session_factory() as session:
            await session.execute(update(Signal).where(Signal.id.in_([s["id"] for s in signals])).values(processed=True))
            await commit_with_retry(session)

    async def _position(self, symbol: str) -> Optional[Position]:
        async with async_session_factory() as session:
            return (await session.execute(select(Position).where(Position.symbol == symbol))).scalars().first()

    async def _close(self, pos: Position, side: str, reason: str, sig: Dict):
        res = await paper_engine.execute_order(symbol=pos.symbol, side=side, qty=abs(pos.qty), reason=f"Exit on {reason}",
                                               agent_name=sig.get("agent") or self.name)
        if res.get("success"):
            await self.log("ACTION", f"{side} {abs(pos.qty)} {pos.symbol} @ ${res['fill_price']:.2f} ({reason[:80]})", ticker=pos.symbol)
            if alpaca_client.is_configured():
                await alpaca_client.submit_order(symbol=pos.symbol, qty=abs(pos.qty), side="sell" if side == "SELL" else "buy")
        else:
            await self.log("WARNING", f"{side} {pos.symbol} failed: {res.get('error')}", ticker=pos.symbol)

    # ------------------------------------------------------------------
    # Entries under risk limits
    # ------------------------------------------------------------------

    async def _start_of_day_equity(self) -> Optional[float]:
        sod = datetime.datetime.now(NY).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(datetime.timezone.utc)
        async with async_session_factory() as session:
            snap = (await session.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.timestamp >= sod.replace(tzinfo=None))
                                          .order_by(PortfolioSnapshot.timestamp.asc()).limit(1))).scalars().first()
        return snap.total_equity if snap else None

    async def _open_positions(self, candidates: List[Dict], red_flags: set):
        account = await paper_engine.get_account_summary()
        equity = account["total_equity"]
        if equity <= 0:
            return

        sod = await self._start_of_day_equity()
        if sod and equity < sod * (1 - settings.MAX_DAILY_DRAWDOWN_PCT):
            await self.log("WARNING", f"Daily loss limit hit (equity ${equity:.2f} vs ${sod:.2f} at open). No new entries today.")
            return

        regime = await get_regime()
        mult = float(regime.get("risk_multiplier", 0.75))
        candidates.sort(key=lambda c: c["effective_conf"], reverse=True)

        for c in candidates:
            ticker, action, meta = c["ticker"], c["action"], c["meta"]
            is_hedge = c["catalyst"] == "BETA_HEDGE"
            going_long = action == "BUY"

            if action == "SHORT" and not settings.ALLOW_SHORTS:
                continue
            if not is_hedge:
                if c["effective_conf"] < settings.MIN_CONFIDENCE:
                    await self.log("INFO", f"Skip {action} {ticker}: conviction {c['effective_conf']:.0%} < {settings.MIN_CONFIDENCE:.0%}", ticker=ticker)
                    continue
                if going_long and not regime.get("allow_new_longs", True):
                    await self.log("INFO", f"Skip BUY {ticker}: regime {regime.get('regime')} blocks new longs", ticker=ticker)
                    continue
                if going_long and ticker in red_flags:
                    await self.log("WARNING", f"VETO BUY {ticker}: accounting red flag in last 7 days", ticker=ticker)
                    continue
                if meta.get("bull_bear_debate", {}).get("verdict") == ("BEAR_DOMINANT" if going_long else "BULL_DOMINANT"):
                    await self.log("WARNING", f"VETO {action} {ticker}: headlines point the other way", ticker=ticker)
                    continue

            held = await self._position(ticker)
            if held and ((held.qty > 0) == going_long) and not is_hedge:
                await self._extend_horizon(held, meta.get("horizon_days"))
                continue

            q: Optional[Quote] = await asyncio.to_thread(get_quote, ticker)
            if not q:
                continue
            problem = self._listing_problem(q, action)
            if problem:
                await self.log("INFO", f"Skip {action} {ticker}: {problem}", ticker=ticker)
                continue

            if going_long and not is_hedge and c["catalyst"] != "FORENSIC_HIGH_QUALITY" and q.quote_type == "EQUITY":
                verdict = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
                if verdict.get("recommendation") == "AVOID/SHORT":
                    await self.log("WARNING", f"VETO BUY {ticker}: forensic screen says AVOID "
                                              f"(Piotroski {verdict.get('piotroski_f_score')}, Beneish {verdict.get('beneish_m_score')})", ticker=ticker)
                    continue

            # Size: hedges ask for an exact weight; everything else scales with conviction and regime
            if is_hedge:
                target_value = equity * float(meta.get("target_weight", 0))
            else:
                target_value = equity * settings.MAX_POSITION_SIZE_PCT * c["effective_conf"] * mult
            price = q.ask if going_long else q.bid
            qty = round(target_value / price, 4) if going_long else math.floor(target_value / price)
            if (going_long and qty * price < 1.0) or (not going_long and qty < 1):
                unit = "dollar" if going_long else f"share (${price:.2f})"
                await self.log("INFO", f"Skip {action} {ticker}: ${target_value:.2f} target is below one {unit}", ticker=ticker)
                continue

            limit_msg = await self._limit_breach(q, qty * price, going_long, equity, is_hedge)
            if limit_msg:
                await self.log("INFO", f"Skip {action} {ticker}: {limit_msg}", ticker=ticker)
                continue

            res = await paper_engine.execute_order(
                symbol=ticker, side=action, qty=qty, quote=q, agent_name=c.get("agent") or "",
                reason=f"{c['catalyst']} entry: {c['title']} (conf {c['effective_conf']*100:.0f}%)",
                catalyst=c["catalyst"], stop_loss_pct=meta.get("stop_loss_pct"),
                take_profit_pct=meta.get("take_profit_pct"), horizon_days=meta.get("horizon_days"))
            if res.get("success"):
                await self.log("ACTION", f"{action} {qty} {ticker} @ ${res['fill_price']:.2f} "
                                         f"({q.source}, spread {q.spread_bps:.1f} bps, fees ${res['fees']:.2f})", ticker=ticker)
                if alpaca_client.is_configured():
                    await alpaca_client.submit_order(symbol=ticker, qty=qty, side="buy" if going_long else "sell")
            else:
                await self.log("WARNING", f"{action} {ticker} rejected: {res.get('error')}", ticker=ticker)

    @staticmethod
    def _listing_problem(q: Quote, action: str) -> Optional[str]:
        if q.exchange and q.exchange.upper() in OTC_EXCHANGES:
            return f"over-the-counter listing ({q.exchange})"
        if q.quote_type and q.quote_type.upper() not in TRADABLE_TYPES:
            return f"not a stock or ETF ({q.quote_type})"
        if action == "BUY" and q.last < settings.MIN_LONG_PRICE:
            return f"price ${q.last:.4f} under ${settings.MIN_LONG_PRICE:.2f}"
        if action == "SHORT" and q.last < settings.MIN_SHORT_PRICE:
            return f"price ${q.last:.2f} under ${settings.MIN_SHORT_PRICE:.2f}; not borrowable"
        return None

    async def _limit_breach(self, q: Quote, order_value: float, going_long: bool,
                            equity: float, is_hedge: bool) -> Optional[str]:
        async with async_session_factory() as session:
            positions = (await session.execute(select(Position))).scalars().all()
        long_v = sum(p.market_value for p in positions if p.qty > 0)
        short_v = -sum(p.market_value for p in positions if p.qty < 0)
        gross = (long_v + short_v + order_value) / equity
        net = (long_v - short_v + (order_value if going_long else -order_value)) / equity
        if gross > settings.MAX_GROSS_EXPOSURE:
            return f"gross exposure would be {gross:.0%} (max {settings.MAX_GROSS_EXPOSURE:.0%})"
        if going_long and not is_hedge and net > settings.MAX_NET_EXPOSURE:
            return f"net exposure would be {net:.0%} (max {settings.MAX_NET_EXPOSURE:.0%})"
        if not going_long and net < settings.MIN_NET_EXPOSURE:
            return f"net exposure would be {net:.0%} (min {settings.MIN_NET_EXPOSURE:.0%})"
        if not is_hedge and q.sector:
            sector_v = sum(abs(p.market_value) for p in positions if p.sector == q.sector) + order_value
            if sector_v / equity > settings.MAX_SECTOR_PCT:
                return f"{q.sector} would be {sector_v / equity:.0%} of equity (max {settings.MAX_SECTOR_PCT:.0%})"
        return None

    async def _extend_horizon(self, pos: Position, horizon_days):
        if not horizon_days:
            return
        new_exit = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=float(horizon_days))
        async with async_session_factory() as session:
            p = (await session.execute(select(Position).where(Position.symbol == pos.symbol))).scalars().first()
            if p and (p.exit_by is None or _aware(p.exit_by) < new_exit):
                p.exit_by = new_exit
                await commit_with_retry(session)


cio_agent = CioRiskAgent()
