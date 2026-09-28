import asyncio
import datetime
import logging
import time
from typing import Dict, List

import yfinance as yf

from backend.agents.base import BaseAgent
from backend.market.data import LARGE_CAPS

logger = logging.getLogger("alphaforge.analyst")

LOOKBACK_DAYS = 5


def recent_rating_changes(ticker: str, days: int) -> List[Dict]:
    df = yf.Ticker(ticker).upgrades_downgrades
    if df is None or df.empty:
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    out = []
    for ts, row in df.iterrows():
        when = ts.to_pydatetime().replace(tzinfo=None)
        if when >= cutoff and row.get("Action") in ("up", "down"):
            out.append({"date": when.date().isoformat(), "firm": row.get("Firm"), "action": row.get("Action"),
                        "from": row.get("FromGrade"), "to": row.get("ToGrade")})
    return out


class AnalystRevisionAgent(BaseAgent):
    """
    Sell-side rating changes on S&P 100 names. A lone upgrade is weak evidence, so conviction
    only clears the CIO's bar when several brokers move the same way within 5 days.
    """
    def __init__(self):
        super().__init__(name="analyst_agent", display_name="Analyst Revision Clusters", interval_seconds=7200)

    async def run_iteration(self):
        emitted = 0
        for ticker in LARGE_CAPS:
            try:
                changes = await asyncio.to_thread(recent_rating_changes, ticker, LOOKBACK_DAYS)
            except Exception as e:
                logger.debug(f"ratings fetch failed for {ticker}: {e}")
                continue
            await asyncio.sleep(0.3)  # be gentle with Yahoo
            ups = [c for c in changes if c["action"] == "up"]
            downs = [c for c in changes if c["action"] == "down"]
            net = len(ups) - len(downs)
            if net == 0:
                continue
            action = "BUY" if net > 0 else "SHORT"
            if await self.emitted_recently(ticker, "ANALYST_REVISIONS", days=LOOKBACK_DAYS, action=action):
                continue
            group = ups if net > 0 else downs
            conf = min(0.86, 0.70 + 0.05 * (abs(net) - 1))
            firms = ", ".join(sorted({c["firm"] for c in group if c["firm"]}))
            await self.emit_signal(
                ticker=ticker, catalyst_type="ANALYST_REVISIONS", action=action, confidence=conf,
                title=f"{abs(net)} net {'upgrade' if net > 0 else 'downgrade'}{'s' if abs(net) > 1 else ''} in {LOOKBACK_DAYS} days: {ticker}",
                summary=f"{len(ups)} upgrades vs {len(downs)} downgrades since {group[-1]['date']} ({firms}).",
                metadata={"changes": changes, "horizon_days": 20, "stop_loss_pct": 0.06, "take_profit_pct": 0.12})
            emitted += 1
        await self.log("INFO", f"Scanned rating changes on {len(LARGE_CAPS)} names: {emitted} new signals")
        await self.update_status("RUNNING", stats={"last_emitted": emitted})


analyst_agent = AnalystRevisionAgent()
