from backend.agents.sec_edgar import sec_agent, SecEdgarAgent

FEED = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>4 - GigaCloud Technology Inc (0001857816) (Issuer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1857816/000204503426000009/0002045034-26-000009-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-09-25 &lt;b&gt;AccNo:&lt;/b&gt; 0002045034-26-000009</summary>
<id>urn:tag:sec.gov,2008:accession-number=0002045034-26-000009</id>
</entry>
<entry>
<title>8-K - XYZ CORP (0001234567) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/0001234567-26-000001-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-09-25 &lt;br&gt;Item 1.01: Entry into a Material Definitive Agreement &lt;br&gt;Item 9.01: Financial Statements and Exhibits</summary>
<id>urn:tag:sec.gov,2008:accession-number=0001234567-26-000001</id>
</entry>
<entry>
<title>SCHEDULE 13D/A - ADURO CLEAN TECHNOLOGIES INC. (0001863934) (Subject)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/x-index.htm"/>
<summary type="html">x</summary>
<id>urn:tag:sec.gov,2008:accession-number=0001863934-26-000002</id>
</entry>
</feed>
"""

FORM4_TEMPLATE = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerCik>0001857816</issuerCik><issuerName>GigaCloud</issuerName><issuerTradingSymbol>GCT</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>1</rptOwnerCik><rptOwnerName>Jane Doe</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>CODE</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>2000</value></transactionShares>
        <transactionPricePerShare><value>50.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>AD</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_atom_parser_reads_form_role_items_and_accession():
    entries = SecEdgarAgent.parse_atom_feed(FEED)
    assert len(entries) == 3
    f4, eightk, sc13d = entries
    assert (f4["form_type"], f4["company_name"], f4["cik"], f4["role"]) == ("4", "GigaCloud Technology Inc", "0001857816", "Issuer")
    assert f4["accession_number"] == "0002045034-26-000009"
    assert eightk["items"] == ["1.01", "9.01"]
    assert sc13d["form_type"] == "SCHEDULE 13D/A" and sc13d["role"] == "Subject"


def test_form4_open_market_purchase_is_counted():
    xml = FORM4_TEMPLATE.replace("CODE", "P").replace("AD", "A")
    parsed = SecEdgarAgent.parse_form4_purchases(xml)
    assert parsed["ticker"] == "GCT"
    assert parsed["is_insider"]
    assert parsed["purchase_value"] == 100_000.0


def test_form4_sale_is_not_a_purchase():
    xml = FORM4_TEMPLATE.replace("CODE", "S").replace("AD", "D")
    parsed = SecEdgarAgent.parse_form4_purchases(xml)
    assert parsed["purchase_value"] == 0.0


def test_form4_grant_is_not_a_purchase():
    # Code A = award/grant from the company, not an open-market buy
    xml = FORM4_TEMPLATE.replace("CODE", "A").replace("AD", "A")
    assert SecEdgarAgent.parse_form4_purchases(xml)["purchase_value"] == 0.0


def test_unknown_cik_has_no_ticker():
    assert sec_agent.ticker_for_cik("0000000001") is None
