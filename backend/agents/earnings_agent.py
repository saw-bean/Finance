import asyncio
import datetime
import logging
import re
from typing import Optional, Tuple

import httpx
import yfinance as yf

from backend.agents.base import BaseAgent
from backend.agents.sec_edgar import sec_agent, feed_url
from backend.config import settings

logger = logging.getLogger("alphaforge.earnings")

MIN_SURPRISE = 0.05   # |actual - estimate| / |estimate|


def eps_surprise(ticker: str, filed: datetime.date) -> Optional[Tuple[float, float, float]]:
    """(reported, estimate, surprise) for the earnings release matching an 8-K filed on ``filed``."""
    df = yf.Ticker(ticker).get_earnings_dates(limit=8)
    if df is None:
        return None
    for ts, row in df.iterrows():
        if abs((ts.date() - filed).days) <= 3 and row.notna()[["EPS Estimate", "Reported EPS"]].all():
            est, rep = float(row["EPS Estimate"]), float(row["Reported EPS"])
            return rep, est, (rep - est) / max(abs(est), 0.01)
    return None


class EarningsDriftAgent(BaseAgent):
    """
    Post-earnings announcement drift. Watches EDGAR for 8-K Item 2.02 (Results of Operations)
    filings, looks up the EPS actual vs. consensus for that release, and trades in the direction
    of a surprise of 5% or more, holding ~2 months while the drift plays out.
    """
    def __init__(self):
        super().__init__(name="earnings_agent", display_name="Earnings Surprise Drift", interval_seconds=300)
        self.seen: set = set()

    async def run_iteration(self):
        async with httpx.AsyncClient(timeout=20.0, headers=sec_agent.headers, follow_redirects=True) as client:
            await sec_agent._refresh_ticker_map(client)
            resp = await client.get(feed_url("8-K", 100))
            if resp.status_code != 200:
                await self.log("WARNING", f"EDGAR 8-K feed HTTP {resp.status_code}")
                return
            entries = sec_agent.parse_atom_feed(resp.text)

        releases = [e for e in entries if "2.02" in e["items"] and e["accession_number"] not in self.seen]
        emitted = 0
        for e in releases:
            self.seen.add(e["accession_number"])
            ticker = sec_agent.ticker_for_cik(e["cik"])
            if not ticker or await self.emitted_recently(ticker, "EARNINGS_SURPRISE", days=20):
                continue
            m = re.search(r"Filed:\S*\s*(\d{4}-\d{2}-\d{2})", e["summary"])
            filed = datetime.date.fromisoformat(m.group(1)) if m else datetime.date.today()
            try:
                hit = await asyncio.to_thread(eps_surprise, ticker, filed)
            except Exception as exc:
                logger.debug(f"earnings lookup failed for {ticker}: {exc}")
                continue
            if not hit:
                continue
            rep, est, surprise = hit
            if abs(surprise) < MIN_SURPRISE:
                continue
            action = "BUY" if surprise > 0 else "SHORT"
            await self.emit_signal(
                ticker=ticker, catalyst_type="EARNINGS_SURPRISE", action=action,
                confidence=min(0.90, 0.76 + abs(surprise) * 0.5),
                title=f"EPS {'beat' if surprise > 0 else 'miss'} {surprise:+.0%}: {e['company_name']}",
                summary=f"Reported EPS ${rep:.2f} vs consensus ${est:.2f} ({surprise:+.1%}) in 8-K Item 2.02 filed {filed}.",
                metadata={"reported_eps": rep, "estimated_eps": est, "surprise": round(surprise, 4),
                          "filing_url": e["link"], "accession_number": e["accession_number"],
                          "horizon_days": 60, "stop_loss_pct": 0.08, "take_profit_pct": 0.20})
            emitted += 1

        if releases:
            await self.log("INFO", f"{len(releases)} new earnings releases on EDGAR; {emitted} surprises of {MIN_SURPRISE:.0%}+")
        await self.update_status("RUNNING", stats={"releases_seen": len(self.seen)})


earnings_agent = EarningsDriftAgent()
