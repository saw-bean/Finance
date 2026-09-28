import asyncio
import json
import logging

import numpy as np
from sqlalchemy import select

from backend.agents.base import BaseAgent
from backend.db.models import BossDirective
from backend.db.session import async_session_factory, commit_with_retry
from backend.market.data import BENCHMARK, daily_closes

logger = logging.getLogger("alphaforge.regime")

# risk_multiplier scales every new position; target_beta is what the hedging agent steers to
REGIMES = {
    "RISK_ON":  {"risk_multiplier": 1.00, "allow_new_longs": True,  "target_beta": 0.8},
    "NEUTRAL":  {"risk_multiplier": 0.75, "allow_new_longs": True,  "target_beta": 0.6},
    "RISK_OFF": {"risk_multiplier": 0.50, "allow_new_longs": True,  "target_beta": 0.3},
    "CRISIS":   {"risk_multiplier": 0.25, "allow_new_longs": False, "target_beta": 0.0},
}


class RegimeAgent(BaseAgent):
    """
    Classifies the market from S&P 500 trend, realized volatility, VIX level and VIX term
    structure, and publishes a risk budget the CIO and hedging agent obey. Emits no trades.
    """
    def __init__(self):
        super().__init__(name="regime_agent", display_name="Market Regime Monitor", interval_seconds=900)
        self.current = None

    async def run_iteration(self):
        closes = await asyncio.to_thread(daily_closes, [BENCHMARK, "^VIX", "^VIX3M"])
        if BENCHMARK not in closes or "^VIX" not in closes or len(closes) < 200:
            await self.log("WARNING", "Regime inputs unavailable; keeping previous regime")
            return
        spy = closes[BENCHMARK].dropna()
        sma200 = float(spy.tail(200).mean())
        last = float(spy.iloc[-1])
        rv20 = float(np.log(spy).diff().tail(20).std() * np.sqrt(252))
        vix = float(closes["^VIX"].dropna().iloc[-1])
        vix3m = float(closes["^VIX3M"].dropna().iloc[-1]) if "^VIX3M" in closes and closes["^VIX3M"].notna().any() else None
        term = vix / vix3m if vix3m else None

        if vix > 35 or (term and term > 1.10):
            regime = "CRISIS"
        elif last < sma200 or vix > 25 or (term and term > 1.0):
            regime = "RISK_OFF"
        elif last > sma200 and vix < 18:
            regime = "RISK_ON"
        else:
            regime = "NEUTRAL"

        payload = {"regime": regime, **REGIMES[regime], "spy": round(last, 2), "spy_sma200": round(sma200, 2),
                   "spy_realized_vol_20d": round(rv20, 4), "vix": round(vix, 2),
                   "vix_term_ratio": round(term, 3) if term else None}
        await self._publish(payload)
        if regime != self.current:
            await self.log("ACTION", f"Regime {self.current or 'start'} -> {regime}: SPY {last:.0f} vs 200d {sma200:.0f}, "
                                     f"VIX {vix:.1f}{f', VIX/VIX3M {term:.2f}' if term else ''}, 20d vol {rv20:.0%}")
            self.current = regime
        await self.update_status("RUNNING", stats=payload)

    async def _publish(self, payload):
        async with async_session_factory() as session:
            d = (await session.execute(select(BossDirective).where(BossDirective.directive_key == "MARKET_REGIME"))).scalars().first()
            if not d:
                d = BossDirective(directive_key="MARKET_REGIME", category="REGIME", active=True)
                session.add(d)
            d.value = json.dumps(payload)
            d.description = f"{payload['regime']}: risk x{payload['risk_multiplier']}, target beta {payload['target_beta']}"
            await commit_with_retry(session)


regime_agent = RegimeAgent()
