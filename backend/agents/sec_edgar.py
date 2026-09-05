import re
import xml.etree.ElementTree as ET
import httpx
import logging
from typing import Dict, Any, List
from backend.agents.base import BaseAgent
from backend.config import settings

logger = logging.getLogger("alphaforge.sec_agent")

class SecEdgarAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="sec_edgar_agent",
            display_name="SEC EDGAR & Footnote Sniper",
            interval_seconds=settings.POLLING_INTERVAL_SEC_EDGAR
        )
        self.seen_accession_numbers = set()
        self.headers = {
            "User-Agent": settings.SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov"
        }

    async def run_iteration(self):
        await self.log("INFO", "Polling SEC EDGAR live feed for Form 4, 8-K, and 13D filings...")
        
        # Ingest SEC EDGAR Atom/RSS latest filings feed
        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=40&output=atom"
        
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=self.headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    await self.log("WARNING", f"SEC EDGAR feed returned HTTP {resp.status_code}")
                    return
                
                content = resp.text
                entries = self._parse_atom_feed(content)
                
                processed_count = 0
                for entry in entries:
                    acc_num = entry.get("accession_number")
                    if not acc_num or acc_num in self.seen_accession_numbers:
                        continue
                    
                    self.seen_accession_numbers.add(acc_num)
                    processed_count += 1
                    
                    form_type = entry.get("form_type", "").upper()
                    ticker = entry.get("ticker", "")
                    title = entry.get("title", "")
                    
                    if "4" in form_type:
                        # Insider transaction
                        await self._process_form_4(entry)
                    elif "8-K" in form_type:
                        # Material Event
                        await self._process_form_8k(entry)
                    elif "13D" in form_type or "13G" in form_type:
                        # Activist / Institutional ownership >5%
                        await self._process_form_13(entry)

                await self.log("INFO", f"Processed {processed_count} new SEC EDGAR filings. Total tracked: {len(self.seen_accession_numbers)}")
                await self.update_status("RUNNING", stats={"tracked_filings": len(self.seen_accession_numbers), "last_batch_count": processed_count})

        except Exception as e:
            logger.error(f"Error fetching SEC EDGAR feed: {e}")
            await self.log("ERROR", f"SEC EDGAR polling error: {str(e)}")

    def _parse_atom_feed(self, xml_text: str) -> List[Dict[str, Any]]:
        entries = []
        try:
            # Strip namespaces for simple parsing
            xml_clean = re.sub(r'xmlns(:\w+)?="[^"]+"', '', xml_text)
            root = ET.fromstring(xml_clean)
            
            for entry in root.findall("entry"):
                title_elem = entry.find("title")
                title = title_elem.text if title_elem is not None else ""
                
                link_elem = entry.find("link")
                link = link_elem.get("href") if link_elem is not None else ""
                
                summary_elem = entry.find("summary")
                summary = summary_elem.text if summary_elem is not None else ""
                
                # Extract Form Type and Company / Ticker
                # Title format: "4 - Company Name (0001234567) (Issuer)" or "8-K - XYZ CORP (0001234567) (Filer)"
                form_type = ""
                company_name = ""
                cik = ""
                
                m = re.match(r'^([A-Z0-9\-\/]+)\s*-\s*(.*?)\s*\((\d+)\)', title)
                if m:
                    form_type = m.group(1).strip()
                    company_name = m.group(2).strip()
                    cik = m.group(3).strip()
                
                # Extract Accession Number from link
                acc_num = ""
                acc_m = re.search(r'accession-number=(\d{10}-\d{2}-\d{6})', link)
                if not acc_m:
                    acc_m = re.search(r'(\d{10}\d{2}\d{6})', link)
                if acc_m:
                    acc_num = acc_m.group(1)
                else:
                    acc_num = link

                # Infer ticker if available or use clean company name / CIK
                ticker_m = re.search(r'\(([A-Z]{1,5})\)', title)
                ticker = ticker_m.group(1) if ticker_m else ""
                if not ticker and company_name:
                    # Rough ticker estimate or use first word for demonstration
                    parts = company_name.split()
                    if parts and len(parts[0]) <= 5 and parts[0].isalpha():
                        ticker = parts[0].upper()
                    else:
                        ticker = f"CIK{cik[-4:]}" if cik else "UNKN"

                entries.append({
                    "title": title,
                    "link": link,
                    "form_type": form_type,
                    "company_name": company_name,
                    "cik": cik,
                    "ticker": ticker,
                    "summary": summary,
                    "accession_number": acc_num
                })
        except Exception as e:
            logger.error(f"Error parsing SEC Atom XML: {e}")
        return entries

    async def _process_form_4(self, entry: Dict[str, Any]):
        """Evaluates Form 4 filings for open-market insider purchases."""
        title = entry["title"]
        summary = entry["summary"]
        ticker = entry["ticker"]
        company = entry["company_name"]
        
        # Check for open market purchase keywords
        is_purchase = any(k in summary.lower() or k in title.lower() for k in ["purchase", "bought", "acquisition", "code p", "open market"])
        
        # Generate Alpha Signal if insider buying is detected
        if is_purchase or "4" in entry["form_type"]:
            confidence = 0.85 if "officer" in summary.lower() or "director" in summary.lower() or "chief" in summary.lower() else 0.75
            
            # Detect Pre-Market / Overnight timing (4 PM - 9:30 AM ET)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            is_premarket = now_utc.hour < 13 or (now_utc.hour == 13 and now_utc.minute < 30) or now_utc.hour >= 20
            if is_premarket:
                confidence = min(0.95, confidence + 0.05)

            await self.emit_signal(
                ticker=ticker,
                catalyst_type="SEC_FORM4_CLUSTER_BUY",
                action="BUY",
                confidence=confidence,
                title=f"Form 4 Insider Accumulation: {company}" + (" [Pre-Market Setup]" if is_premarket else ""),
                summary=f"C-level / Director open-market insider accumulation detected in SEC EDGAR filing. Title: {title}",
                metadata={
                    "company_name": company,
                    "cik": entry["cik"],
                    "form_type": entry["form_type"],
                    "filing_url": entry["link"],
                    "is_premarket_catalyst": is_premarket
                }
            )

    async def _process_form_8k(self, entry: Dict[str, Any]):
        """Evaluates Form 8-K material events."""
        title = entry["title"]
        summary = entry["summary"]
        ticker = entry["ticker"]
        company = entry["company_name"]
        
        # Check for key 8-K material catalysts
        is_merger_or_contract = any(k in summary.lower() for k in ["item 1.01", "definitive agreement", "material contract", "acquisition", "partnership"])
        is_auditor_change = any(k in summary.lower() for k in ["item 4.01", "certifying accountant", "resignation of auditor"])
        
        if is_merger_or_contract:
            await self.emit_signal(
                ticker=ticker,
                catalyst_type="SEC_8K_MATERIAL_AGREEMENT",
                action="BUY",
                confidence=0.78,
                title=f"Form 8-K Material Agreement: {company}",
                summary=f"Material definitive contract / strategic agreement disclosed in Item 1.01 of 8-K.",
                metadata={"filing_url": entry["link"], "company_name": company}
            )
        elif is_auditor_change:
            await self.emit_signal(
                ticker=ticker,
                catalyst_type="ACCOUNTING_RED_FLAG",
                action="SELL",
                confidence=0.88,
                title=f"Form 8-K Auditor Departure / Accounting Disagreement: {company}",
                summary=f"Sudden change or resignation in certifying accountant (Item 4.01). High forensic risk factor.",
                metadata={"filing_url": entry["link"], "company_name": company}
            )

    async def _process_form_13(self, entry: Dict[str, Any]):
        """Evaluates Schedule 13D/G activist stake building."""
        ticker = entry["ticker"]
        company = entry["company_name"]
        is_13d = "13D" in entry["form_type"]
        
        catalyst = "ACTIVIST_STAKE_13D" if is_13d else "INSTITUTIONAL_ACCUMULATION_13G"
        confidence = 0.82 if is_13d else 0.65
        
        await self.emit_signal(
            ticker=ticker,
            catalyst_type=catalyst,
            action="BUY",
            confidence=confidence,
            title=f"Beneficial Ownership Filing ({entry['form_type']}): {company}",
            summary=f"Activist/Institutional investor acquired >5% stake in {company}.",
            metadata={"filing_url": entry["link"], "company_name": company}
        )

sec_agent = SecEdgarAgent()
