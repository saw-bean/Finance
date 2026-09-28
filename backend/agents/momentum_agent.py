import asyncio
import logging

from backend.agents.base import BaseAgent
from backend.market.data import LARGE_CAPS, BENCHMARK, daily_closes

logger = logging.getLogger("alphaforge.momentum")

TOP_N = 5


class MomentumAgent(BaseAgent):
    """
    Cross-sectional 12-1 month momentum on S&P 100 names (Jegadeesh & Titman).
    Weekly: long the 5 strongest names that are above their 200-day average, short the 5 weakest
    that are below it. Positions are held ~a month and refreshed while they stay in the tails.
    """
    def __init__(self):
        super().__init__(name="momentum_agent", display_name="Cross-Sectional Momentum", interval_seconds=3600)

    async def run_iteration(self):
        closes = await asyncio.to_thread(daily_closes, LARGE_CAPS + [BENCHMARK])
        closes = closes[[c for c in LARGE_CAPS if c in closes]].dropna(axis=1, thresh=253)
        if len(closes) < 253 or closes.shape[1] < 20:
            await self.log("WARNING", f"Not enough price history ({len(closes)} rows, {closes.shape[1]} names)")
            return

        # 12-month return skipping the most recent month (short-term reversal contaminates it)
        mom = (closes.iloc[-22] / closes.iloc[-253] - 1).dropna().sort_values()
        sma200 = closes.tail(200).mean()
        last = closes.iloc[-1]

        winners = [t for t in reversed(mom.index) if last[t] > sma200[t]][:TOP_N]
        losers = [t for t in mom.index if last[t] < sma200[t]][:TOP_N]
        emitted = 0
        for rank, t in enumerate(winners, 1):
            emitted += await self._emit(t, "BUY", mom[t], rank, len(mom))
        for rank, t in enumerate(losers, 1):
            emitted += await self._emit(t, "SHORT", mom[t], len(mom) - rank + 1, len(mom))

        await self.log("INFO", f"Momentum ranks: top {', '.join(winners)} | bottom {', '.join(losers)} ({emitted} new signals)")
        await self.update_status("RUNNING", stats={"universe": int(len(mom)), "longs": winners, "shorts": losers})

    async def _emit(self, ticker: str, action: str, ret: float, rank: int, n: int) -> int:
        if await self.emitted_recently(ticker, "MOMENTUM_12_1", days=6, action=action):
            return 0
        await self.emit_signal(
            ticker=ticker, catalyst_type="MOMENTUM_12_1", action=action, confidence=0.80,
            title=f"12-1 momentum rank {rank}/{n}: {ticker} {ret:+.0%}",
            summary=f"12-month return excluding the last month is {ret:+.1%} (rank {rank} of {n}); "
                    f"price is {'above' if action == 'BUY' else 'below'} its 200-day average.",
            metadata={"return_12_1": round(float(ret), 4), "rank": rank, "universe": n,
                      "horizon_days": 30, "stop_loss_pct": 0.08, "take_profit_pct": 0.25})
        return 1


momentum_agent = MomentumAgent()
