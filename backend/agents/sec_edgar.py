import asyncio
import datetime
import re
import time
import xml.etree.ElementTree as ET
import httpx
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func
from backend.agents.base import BaseAgent
from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.models import Signal

logger = logging.getLogger("alphaforge.sec_agent")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# "4 - GigaCloud Technology Inc (0001857816) (Issuer)"
# "SCHEDULE 13D/A - ADURO CLEAN TECHNOLOGIES INC. (0001863934) (Subject)"
TITLE_RE = re.compile(r'^(.+?) - (.*) \((\d{10})\) \(([^)]+)\)\s*$')
ACC_RE = re.compile(r'accession-number=(\d{10}-\d{2}-\d{6})')
ITEM_RE = re.compile(r'Item (\d\.\d{2})')

MIN_INSIDER_BUY_USD = 50_000.0
MAX_FORM4_FETCHES_PER_RUN = 40


def feed_url(form: str, count: int) -> str:
    return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
            f"&type={form}&owner=include&start=0&count={count}&output=atom")


class SecEdgarAgent(BaseAgent):
    """
    Polls SEC EDGAR's live filing feeds and emits signals only from facts in the filings:
    - Form 4: parses the ownership XML and counts open-market purchases (code P) by officers/directors.
    - 8-K: reads the Item numbers EDGAR lists for the filing.
    - Schedule 13D: new activist stakes (Subject company side only).
    Filings whose company has no listed ticker are skipped.
    """
    def __init__(self):
        super().__init__(
            name="sec_edgar_agent",
            display_name="SEC EDGAR Filings Agent",
            interval_seconds=settings.POLLING_INTERVAL_SEC_EDGAR
        )
        self.seen_accession_numbers: set = set()
        self._cik_to_ticker: Dict[int, str] = {}
        self._ticker_map_loaded_at = 0.0

    @property
    def headers(self) -> Dict[str, str]:
        # SEC requires a descriptive User-Agent with contact info
        return {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    async def run_iteration(self):
        await self.log("INFO", "Polling SEC EDGAR feeds for Form 4, 8-K and Schedule 13D filings...")

        async with httpx.AsyncClient(timeout=20.0, headers=self.headers, follow_redirects=True) as client:
            await self._refresh_ticker_map(client)

            form4 = await self._fetch_feed(client, "4", 100)
            eightk = await self._fetch_feed(client, "8-K", 40)
            thirteen_d = await self._fetch_feed(client, "SCHEDULE%2013D", 40)

            new_count = 0
            form4_fetches = 0

            # Form 4: each filing appears twice (Reporting + Issuer); use the Issuer entry
            for entry in form4:
                if entry["role"] != "Issuer" or entry["accession_number"] in self.seen_accession_numbers:
                    continue
                if form4_fetches >= MAX_FORM4_FETCHES_PER_RUN:
                    continue  # left unseen so the next run picks it up
                self._mark_seen(entry)
                new_count += 1
                form4_fetches += 1
                await self._process_form_4(client, entry)
                await asyncio.sleep(0.15)  # stay well under SEC's 10 req/s limit

            for entry in eightk:
                if entry["role"] not in ("Filer", "Subject") or not self._mark_seen(entry):
                    continue
                new_count += 1
                await self._process_form_8k(entry)

            for entry in thirteen_d:
                # Only the Subject company side; skip amendments
                if entry["role"] != "Subject" or entry["form_type"].endswith("/A") or not self._mark_seen(entry):
                    continue
                new_count += 1
                await self._process_form_13d(entry)

        await self.log("INFO", f"Processed {new_count} new SEC filings. Total tracked: {len(self.seen_accession_numbers)}")
        await self.update_status("RUNNING", stats={
            "tracked_filings": len(self.seen_accession_numbers),
            "last_batch_count": new_count,
            "ticker_map_size": len(self._cik_to_ticker)
        })

    def _mark_seen(self, entry: Dict[str, Any]) -> bool:
        """Returns True if the filing is new (and records it as seen)."""
        acc = entry["accession_number"]
        if not acc or acc in self.seen_accession_numbers:
            return False
        self.seen_accession_numbers.add(acc)
        return True

    async def _refresh_ticker_map(self, client: httpx.AsyncClient):
        if self._cik_to_ticker and time.time() - self._ticker_map_loaded_at < 86400:
            return
        try:
            resp = await client.get(TICKER_MAP_URL)
            resp.raise_for_status()
            data = resp.json()
            # A CIK can list several securities (common, warrants, preferred); the file lists the
            # primary one first, so keep the first ticker seen for each CIK.
            mapping: Dict[int, str] = {}
            for v in data.values():
                mapping.setdefault(int(v["cik_str"]), v["ticker"].upper())
            self._cik_to_ticker = mapping
            self._ticker_map_loaded_at = time.time()
        except Exception as e:
            logger.error(f"Failed to load SEC CIK->ticker map: {e}")

    def ticker_for_cik(self, cik: str) -> Optional[str]:
        try:
            return self._cik_to_ticker.get(int(cik))
        except (TypeError, ValueError):
            return None

    async def _fetch_feed(self, client: httpx.AsyncClient, form: str, count: int) -> List[Dict[str, Any]]:
        try:
            resp = await client.get(feed_url(form, count))
            if resp.status_code != 200:
                await self.log("WARNING", f"SEC EDGAR feed ({form}) returned HTTP {resp.status_code}")
                return []
            return self.parse_atom_feed(resp.text)
        except Exception as e:
            logger.error(f"Error fetching SEC feed {form}: {e}")
            await self.log("ERROR", f"SEC EDGAR feed ({form}) error: {type(e).__name__} {e}")
            return []

    @staticmethod
    def parse_atom_feed(xml_text: str) -> List[Dict[str, Any]]:
        entries = []
        try:
            xml_clean = re.sub(r'xmlns(:\w+)?="[^"]+"', '', xml_text)
            root = ET.fromstring(xml_clean)
            for entry in root.findall("entry"):
                title = (entry.findtext("title") or "").strip()
                m = TITLE_RE.match(title)
                if not m:
                    continue
                link_elem = entry.find("link")
                link = link_elem.get("href") if link_elem is not None else ""
                acc_m = ACC_RE.search(entry.findtext("id") or "")
                summary = entry.findtext("summary") or ""
                entries.append({
                    "title": title,
                    "form_type": m.group(1).strip().upper(),
                    "company_name": m.group(2).strip(),
                    "cik": m.group(3),
                    "role": m.group(4).strip(),
                    "link": link,
                    "summary": summary,
                    "items": ITEM_RE.findall(summary),
                    "accession_number": acc_m.group(1) if acc_m else ""
                })
        except Exception as e:
            logger.error(f"Error parsing SEC Atom XML: {e}")
        return entries

    async def _fetch_form4_xml(self, client: httpx.AsyncClient, entry: Dict[str, Any]) -> Optional[str]:
        # .../data/<cik>/<acc-no-dashes>/<acc>-index.htm -> same folder /index.json
        folder = entry["link"].rsplit("/", 1)[0]
        resp = await client.get(f"{folder}/index.json")
        resp.raise_for_status()
        names = [i["name"] for i in resp.json().get("directory", {}).get("item", [])]
        xml_names = [n for n in names if n.lower().endswith(".xml")]
        if not xml_names:
            return None
        await asyncio.sleep(0.15)
        xml_resp = await client.get(f"{folder}/{xml_names[0]}")
        xml_resp.raise_for_status()
        return xml_resp.text

    @staticmethod
    def parse_form4_purchases(xml_text: str) -> Dict[str, Any]:
        """Extracts open-market purchases (transaction code P) from a Form 4 ownership XML."""
        root = ET.fromstring(xml_text)
        ticker = (root.findtext("issuer/issuerTradingSymbol") or "").strip().upper()
        owners = []
        is_insider = False
        for ro in root.findall("reportingOwner"):
            rel = ro.find("reportingOwnerRelationship")
            flag = lambda tag: rel is not None and (rel.findtext(tag) or "").strip().lower() in ("1", "true")
            is_dir, is_off = flag("isDirector"), flag("isOfficer")
            is_insider = is_insider or is_dir or is_off
            owners.append({
                "name": (ro.findtext("reportingOwnerId/rptOwnerName") or "").strip(),
                "is_director": is_dir,
                "is_officer": is_off,
                "officer_title": (rel.findtext("officerTitle") or "").strip() if rel is not None else ""
            })

        total_shares = 0.0
        total_value = 0.0
        for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
            code = (tx.findtext("transactionCoding/transactionCode") or "").strip()
            ad = (tx.findtext("transactionAmounts/transactionAcquiredDisposedCode/value") or "").strip()
            if code != "P" or ad != "A":
                continue
            try:
                shares = float(tx.findtext("transactionAmounts/transactionShares/value") or 0)
                price = float(tx.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
            except ValueError:
                continue
            total_shares += shares
            total_value += shares * price

        return {
            "ticker": ticker,
            "owners": owners,
            "is_insider": is_insider,
            "purchase_shares": total_shares,
            "purchase_value": total_value
        }

    async def _process_form_4(self, client: httpx.AsyncClient, entry: Dict[str, Any]):
        try:
            xml_text = await self._fetch_form4_xml(client, entry)
            if not xml_text:
                return
            parsed = self.parse_form4_purchases(xml_text)
        except Exception as e:
            logger.debug(f"Form 4 fetch/parse failed for {entry['accession_number']}: {e}")
            return

        ticker = parsed["ticker"] or self.ticker_for_cik(entry["cik"])
        if not ticker or ticker in ("NONE", "N/A"):
            return
        if not parsed["is_insider"] or parsed["purchase_value"] < MIN_INSIDER_BUY_USD:
            return

        value = parsed["purchase_value"]
        titles = " ".join(o["officer_title"].upper() for o in parsed["owners"])
        is_c_suite = any(t in titles for t in ("CEO", "CHIEF EXECUTIVE", "CFO", "CHIEF FINANCIAL", "PRESIDENT"))

        # Other insider purchases of the same stock in the last 14 days = cluster buy
        since = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=14)
        async with async_session_factory() as session:
            res = await session.execute(
                select(func.count(Signal.id)).where(
                    Signal.ticker == ticker,
                    Signal.catalyst_type == "SEC_FORM4_CLUSTER_BUY",
                    Signal.timestamp >= since
                )
            )
            prior_buys = res.scalar() or 0

        # Rule-based conviction: base + C-suite buyer + size + cluster
        confidence = 0.72
        if is_c_suite:
            confidence += 0.06
        if value >= 250_000:
            confidence += 0.05
        if prior_buys >= 1:
            confidence += 0.07
        confidence = min(confidence, 0.92)

        who = ", ".join(
            o["name"] + (f" ({o['officer_title']})" if o["officer_title"] else (" (Director)" if o["is_director"] else ""))
            for o in parsed["owners"]
        )
        await self.emit_signal(
            ticker=ticker,
            catalyst_type="SEC_FORM4_CLUSTER_BUY",
            action="BUY",
            confidence=confidence,
            title=f"Insider open-market buy ${value:,.0f}: {entry['company_name']}",
            summary=f"{who} bought {parsed['purchase_shares']:,.0f} shares (${value:,.0f}) on the open market. "
                    f"Other insider buys in last 14 days: {prior_buys}.",
            metadata={
                "company_name": entry["company_name"],
                "cik": entry["cik"],
                "accession_number": entry["accession_number"],
                "filing_url": entry["link"],
                "purchase_value": round(value, 2),
                "purchase_shares": parsed["purchase_shares"],
                "owners": parsed["owners"],
                "prior_insider_buys_14d": prior_buys,
                "horizon_days": 60
            }
        )

    async def _process_form_8k(self, entry: Dict[str, Any]):
        ticker = self.ticker_for_cik(entry["cik"])
        if not ticker:
            return
        items = entry["items"]
        meta = {"filing_url": entry["link"], "company_name": entry["company_name"], "items": items,
                "accession_number": entry["accession_number"], "horizon_days": 30}

        if "4.01" in items or "4.02" in items:
            what = "auditor change (Item 4.01)" if "4.01" in items else "non-reliance on prior financials (Item 4.02)"
            await self.emit_signal(
                ticker=ticker,
                catalyst_type="ACCOUNTING_RED_FLAG",
                action="SHORT",
                confidence=0.85,
                title=f"8-K accounting red flag: {entry['company_name']}",
                summary=f"8-K reports {what}.",
                metadata=meta
            )
        elif "1.01" in items:
            # A material agreement is not bullish by itself (could be a loan or lease), so it
            # is recorded below the CIO's execution bar and only informs other signals.
            await self.emit_signal(
                ticker=ticker,
                catalyst_type="SEC_8K_MATERIAL_AGREEMENT",
                action="BUY",
                confidence=0.60,
                title=f"8-K material agreement: {entry['company_name']}",
                summary="8-K Item 1.01: Entry into a Material Definitive Agreement.",
                metadata=meta
            )

    async def _process_form_13d(self, entry: Dict[str, Any]):
        ticker = self.ticker_for_cik(entry["cik"])
        if not ticker:
            return
        await self.emit_signal(
            ticker=ticker,
            catalyst_type="ACTIVIST_STAKE_13D",
            action="BUY",
            confidence=0.80,
            title=f"New Schedule 13D (>5% active stake): {entry['company_name']}",
            summary=f"An investor filed an initial Schedule 13D on {entry['company_name']}, disclosing a >5% stake with possible activist intent.",
            metadata={"filing_url": entry["link"], "company_name": entry["company_name"],
                      "accession_number": entry["accession_number"], "horizon_days": 90}
        )

sec_agent = SecEdgarAgent()
