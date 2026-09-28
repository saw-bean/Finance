import asyncio
import logging

import pandas as pd

from backend.agents.base import BaseAgent
from backend.market.data import LARGE_CAPS, daily_closes, ny_today

logger = logging.getLogger("alphaforge.mean_reversion")


def rsi(series: pd.Series, period: int = 2) -> pd.Series:
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100)


class MeanReversionAgent(BaseAgent):
    """
    Short-term mean reversion (Connors RSI-2) on S&P 100 names, using completed daily bars only.
    Buy a sharp pullback (RSI(2) < 5) in a stock above its 200-day average; short a sharp spike
    (RSI(2) > 95) in one below it. Holds up to 5 days with a tight target.
    """
    def __init__(self):
        super().__init__(name="mean_reversion_agent", display_name="Short-Term Mean Reversion", interval_seconds=1800)

    async def run_iteration(self):
        closes = await asyncio.to_thread(daily_closes, LARGE_CAPS)
        # Drop today's still-forming bar so the signal only uses closed sessions
        if len(closes) and closes.index[-1].date() >= ny_today():
            closes = closes.iloc[:-1]
        closes = closes.dropna(axis=1, thresh=210)
        if len(closes) < 210:
            return

        sma200 = closes.tail(200).mean()
        last = closes.iloc[-1]
        hits = []
        for t in closes.columns:
            r = float(rsi(closes[t].dropna()).iloc[-1])
            if last[t] > sma200[t] and r < 5:
                hits.append((t, "BUY", r))
            elif last[t] < sma200[t] and r > 95:
                hits.append((t, "SHORT", r))

        emitted = 0
        for t, action, r in hits:
            if await self.emitted_recently(t, "MEAN_REVERSION_RSI2", days=1, action=action):
                continue
            await self.emit_signal(
                ticker=t, catalyst_type="MEAN_REVERSION_RSI2", action=action, confidence=0.79,
                title=f"RSI(2) {r:.1f}: {'oversold pullback' if action == 'BUY' else 'overbought spike'} in {t}",
                summary=f"2-day RSI closed at {r:.1f} with price {'above' if action == 'BUY' else 'below'} "
                        f"the 200-day average ({last[t]:.2f} vs {sma200[t]:.2f}). Expect a snap-back within days.",
                metadata={"rsi2": round(r, 2), "close": round(float(last[t]), 2), "sma200": round(float(sma200[t]), 2),
                          "bar_date": closes.index[-1].date().isoformat(),
                          "horizon_days": 5, "stop_loss_pct": 0.06, "take_profit_pct": 0.04})
            emitted += 1

        await self.log("INFO", f"RSI(2) scan on {closes.shape[1]} names (bar {closes.index[-1].date()}): {emitted} new setups")
        await self.update_status("RUNNING", stats={"setups": len(hits), "bar_date": closes.index[-1].date().isoformat()})


mean_reversion_agent = MeanReversionAgent()
