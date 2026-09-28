import asyncio
import datetime
import logging

from sqlalchemy import select, func

from backend.agents.base import BaseAgent
from backend.agents.cio_risk import get_regime
from backend.db.models import Position, Signal
from backend.db.session import async_session_factory
from backend.execution.paper_engine import paper_engine
from backend.market.data import BENCHMARK, INVERSE_HEDGE, daily_closes, beta, is_market_open

logger = logging.getLogger("alphaforge.hedging")

BAND = 0.15          # tolerate this much beta drift before trading the hedge
MIN_ORDER_WEIGHT = 0.02


class HedgingAgent(BaseAgent):
    """
    Keeps the book's market beta near the regime's target by buying or selling SH (-1x S&P 500).
    Beta per holding is a 120-day regression on SPY; portfolio beta = sum of weight x beta.
    """
    def __init__(self):
        super().__init__(name="hedging_agent", display_name="Beta Hedger", interval_seconds=600)

    async def run_iteration(self):
        if not is_market_open():
            return
        async with async_session_factory() as session:
            positions = (await session.execute(select(Position))).scalars().all()
            pending = (await session.execute(select(func.count(Signal.id)).where(
                Signal.catalyst_type == "BETA_HEDGE", Signal.processed == False))).scalar() or 0
        if pending or not positions:
            return

        account = await paper_engine.get_account_summary()
        equity = account["total_equity"]
        symbols = [p.symbol for p in positions]
        closes = await asyncio.to_thread(daily_closes, symbols + [BENCHMARK, INVERSE_HEDGE])
        rets = closes.pct_change()

        port_beta, unknown = 0.0, []
        for p in positions:
            b = -1.0 if p.symbol == INVERSE_HEDGE else beta(rets, p.symbol)
            if b is None:
                unknown.append(p.symbol)
                b = 1.0  # assume market-like when history is too short
            port_beta += (p.market_value / equity) * b

        regime = await get_regime()
        target = float(regime.get("target_beta", 0.6))
        hedge = next((p for p in positions if p.symbol == INVERSE_HEDGE), None)
        hedge_w = hedge.market_value / equity if hedge else 0.0
        note = f" (assumed beta 1 for {', '.join(unknown)})" if unknown else ""

        if port_beta > target + BAND:
            add_w = port_beta - target
            if add_w >= MIN_ORDER_WEIGHT:
                await self.emit_signal(
                    ticker=INVERSE_HEDGE, catalyst_type="BETA_HEDGE", action="BUY", confidence=0.95,
                    title=f"Hedge: book beta {port_beta:.2f} vs target {target:.2f}",
                    summary=f"Buying SH worth {add_w:.0%} of equity to bring beta toward {target:.2f} ({regime.get('regime')}){note}.",
                    metadata={"target_weight": round(add_w, 4), "portfolio_beta": round(port_beta, 3),
                              "target_beta": target, "stop_loss_pct": 0.5, "take_profit_pct": 5.0})
        elif hedge and port_beta < target - BAND:
            await self.emit_signal(
                ticker=INVERSE_HEDGE, catalyst_type="BETA_HEDGE", action="SELL", confidence=0.95,
                title=f"Unwind hedge: book beta {port_beta:.2f} vs target {target:.2f}",
                summary=f"Selling SH ({hedge_w:.0%} of equity); the book is below its beta target{note}.",
                metadata={"portfolio_beta": round(port_beta, 3), "target_beta": target})

        await self.update_status("RUNNING", stats={"portfolio_beta": round(port_beta, 3), "target_beta": target,
                                                   "hedge_weight": round(hedge_w, 4)})


hedging_agent = HedgingAgent()
