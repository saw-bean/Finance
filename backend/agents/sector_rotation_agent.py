import asyncio
import logging

from backend.agents.base import BaseAgent
from backend.market.data import SECTOR_ETFS, daily_closes

logger = logging.getLogger("alphaforge.sector_rotation")


class SectorRotationAgent(BaseAgent):
    """
    Relative-strength rotation across the 11 SPDR sector ETFs. Weekly: long the two sectors with
    the best 3-/6-month blended return (if in an uptrend), short the two worst (if in a downtrend).
    """
    def __init__(self):
        super().__init__(name="sector_rotation_agent", display_name="Sector Rotation", interval_seconds=3600)

    async def run_iteration(self):
        etfs = list(SECTOR_ETFS)
        closes = await asyncio.to_thread(daily_closes, etfs)
        closes = closes.dropna(axis=1, thresh=200)
        if len(closes) < 200:
            return
        score = (0.5 * (closes.iloc[-1] / closes.iloc[-64] - 1) + 0.5 * (closes.iloc[-1] / closes.iloc[-127] - 1)).sort_values()
        sma200 = closes.tail(200).mean()
        last = closes.iloc[-1]

        leaders = [t for t in reversed(score.index) if last[t] > sma200[t]][:2]
        laggards = [t for t in score.index if last[t] < sma200[t]][:2]
        for t in leaders:
            await self._emit(t, "BUY", score[t])
        for t in laggards:
            await self._emit(t, "SHORT", score[t])

        ranking = ", ".join(f"{t} {score[t]:+.1%}" for t in reversed(score.index))
        await self.log("INFO", f"Sector strength: {ranking}")
        await self.update_status("RUNNING", stats={"leaders": leaders, "laggards": laggards})

    async def _emit(self, etf: str, action: str, score: float):
        if await self.emitted_recently(etf, "SECTOR_ROTATION", days=6, action=action):
            return
        await self.emit_signal(
            ticker=etf, catalyst_type="SECTOR_ROTATION", action=action, confidence=0.80,
            title=f"{SECTOR_ETFS[etf]} sector {'leading' if action == 'BUY' else 'lagging'} ({etf} {score:+.1%})",
            summary=f"Blended 3/6-month return {score:+.1%}, {'top' if action == 'BUY' else 'bottom'} two of 11 sectors, "
                    f"trend {'up' if action == 'BUY' else 'down'} vs 200-day average.",
            metadata={"sector": SECTOR_ETFS[etf], "score": round(float(score), 4),
                      "horizon_days": 30, "stop_loss_pct": 0.07, "take_profit_pct": 0.20})


sector_rotation_agent = SectorRotationAgent()
