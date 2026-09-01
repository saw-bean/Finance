import pytest
from backend.agents.sec_edgar import sec_agent

def test_sec_edgar_atom_parser():
    sample_xml = """<?xml version="1.0" encoding="ISO-8859-1" ?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>4 - PALANTIR TECHNOLOGIES INC. (0001321655) (Issuer)</title>
            <link href="https://www.sec.gov/Archives/edgar/data/1321655/000132165526000010/accession-number=0001321655-26-000010"/>
            <summary>Open market purchase of 50000 shares by CEO</summary>
        </entry>
        <entry>
            <title>8-K - XYZ CORP (0001234567) (Filer)</title>
            <link href="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/accession-number=0001234567-26-000001"/>
            <summary>Item 1.01 Entry into a Material Definitive Agreement</summary>
        </entry>
    </feed>
    """
    entries = sec_agent._parse_atom_feed(sample_xml)
    assert len(entries) == 2
    assert entries[0]["form_type"] == "4"
    assert entries[0]["company_name"] == "PALANTIR TECHNOLOGIES INC."
    assert entries[0]["cik"] == "0001321655"
    assert entries[1]["form_type"] == "8-K"
