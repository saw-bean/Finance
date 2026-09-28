import asyncio
import datetime
import json
import yfinance as yf
import httpx
import logging
from typing import Dict, Any, List
from backend.agents.base import BaseAgent
from backend.config import settings
from sqlalchemy import select, func
from backend.db.session import async_session_factory
from backend.db.models import Signal

MAX_AWARD_AGE_DAYS = 7
MIN_AWARD_TO_MCAP = 0.005  # award must be at least 0.5% of market cap


def _market_cap(ticker: str):
    try:
        return yf.Ticker(ticker).fast_info.get("market_cap")
    except Exception:
        return None

logger = logging.getLogger("alphaforge.contract_agent")

class ContractCatalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="contract_catalyst_agent",
            display_name="Gov & Defense Contract Catalyst Agent",
            interval_seconds=settings.POLLING_INTERVAL_CONTRACTS
        )
        self.seen_award_ids = set()
        self.recipient_ticker_map = {
            "PALANTIR": "PLTR",
            "ROCKET LAB": "RKLB",
            "KRATOS": "KTOS",
            "AEROVIRONMENT": "AVAV",
            "ARCHER AVIATION": "ACHR",
            "JOBY AVIATION": "JOBY",
            "AST SPACEMOBILE": "ASTS",
            "BIGBEAR": "BBAI",
            "BOEING": "BA",
            "LOCKHEED": "LMT",
            "NORTHROP": "NOC",
            "GENERAL DYNAMICS": "GD",
            "RAYTHEON": "RTX",
            "L3HARRIS": "LHX",
            "LEIDOS": "LDOS"
        }

    async def run_iteration(self):
        await self.log("INFO", "Polling USASpending.gov public award API for high-impact defense and tech contracts...")
        
        today = datetime.date.today()
        url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        payload = {
            "filters": {
                "time_period": [{"start_date": (today - datetime.timedelta(days=30)).isoformat(), "end_date": today.isoformat()}],
                "award_type_codes": ["A", "B", "C", "D"],
                "award_amounts": [{"lower_bound": 10000000}],
                "recipient_search_text": list(self.recipient_ticker_map.keys())
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Awarding Agency",
                "Description",
                "Base Obligation Date"
            ],
            "limit": 50,
            "page": 1,
            "sort": "Base Obligation Date",
            "order": "desc"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    new_awards_count = 0
                    
                    for award in results:
                        award_id = award.get("Award ID")
                        if not award_id or award_id in self.seen_award_ids:
                            continue
                        
                        self.seen_award_ids.add(award_id)

                        # Only fresh awards are catalysts; older ones are already priced in
                        try:
                            action_date = datetime.date.fromisoformat((award.get("Base Obligation Date") or "")[:10])
                        except ValueError:
                            continue
                        if (datetime.date.today() - action_date).days > MAX_AWARD_AGE_DAYS:
                            continue
                        recipient = (award.get("Recipient Name") or "").upper()
                        amount = award.get("Award Amount") or 0.0
                        agency = award.get("Awarding Agency") or "U.S. Government"
                        desc = award.get("Description") or "Federal Contract Award"
                        
                        # Match ticker
                        matched_ticker = None
                        for key_name, ticker in self.recipient_ticker_map.items():
                            if key_name in recipient:
                                matched_ticker = ticker
                                break
                                
                        if matched_ticker and not await self._already_signalled(award_id):
                            # Materiality: an award only moves a stock if it is large relative to the company
                            market_cap = await asyncio.to_thread(_market_cap, matched_ticker)
                            if not market_cap:
                                continue
                            ratio = amount / market_cap
                            if ratio < MIN_AWARD_TO_MCAP:
                                continue
                            new_awards_count += 1
                            confidence = min(0.90, 0.72 + ratio * 4)
                            await self.emit_signal(
                                ticker=matched_ticker,
                                catalyst_type="GOV_CONTRACT_AWARD",
                                action="BUY",
                                confidence=confidence,
                                title=f"US Federal Award (${amount/1e6:.1f}M): {recipient}",
                                summary=f"{agency} awarded ${amount:,.0f} to {recipient} ({ratio*100:.2f}% of market cap). Scope: {desc[:180]}",
                                metadata={
                                    "award_id": award_id,
                                    "amount": amount,
                                    "agency": agency,
                                    "recipient": recipient,
                                    "description": desc,
                                    "action_date": action_date.isoformat(),
                                    "market_cap": market_cap,
                                    "award_to_market_cap": round(ratio, 5)
                                }
                            )

                    await self.log("INFO", f"USASpending poll complete. Matched {new_awards_count} targeted contractor awards.")
                    await self.update_status("RUNNING", stats={"tracked_awards": len(self.seen_award_ids), "latest_matches": new_awards_count})
                else:
                    await self.log("WARNING", f"USASpending API returned HTTP {resp.status_code}; no awards this run.")

        except Exception as e:
            logger.error(f"Error checking USASpending feed: {e}")
            await self.log("ERROR", f"USASpending API error: {e}")

    async def _already_signalled(self, award_id: str) -> bool:
        """Survives restarts: the in-memory seen set is empty after a reboot."""
        async with async_session_factory() as session:
            res = await session.execute(
                select(func.count(Signal.id)).where(
                    Signal.catalyst_type == "GOV_CONTRACT_AWARD",
                    Signal.raw_metadata.contains(f'"award_id": {json.dumps(award_id)}')
                )
            )
            return (res.scalar() or 0) > 0

contract_agent = ContractCatalystAgent()
