import pytest
from backend.agents.forensic_quant import forensic_agent

def test_analyze_ticker_structure():
    metrics = forensic_agent.analyze_ticker("PLTR")
    assert "ticker" in metrics
    assert metrics["ticker"] == "PLTR"
    assert "piotroski_f_score" in metrics
    assert 0 <= metrics["piotroski_f_score"] <= 9
    assert "beneish_m_score" in metrics
    assert "altman_z_score" in metrics
    assert "altman_zone" in metrics
    assert metrics["altman_zone"] in ("Safe", "Grey", "Distress")
    assert "recommendation" in metrics
    assert metrics["recommendation"] in ("STRONG_BUY", "BUY", "HOLD", "AVOID/SHORT")

def test_beneish_m_score_threshold():
    score, breakdown = forensic_agent._calc_beneish_m_score(None, None, None)
    assert score <= -1.78
    assert breakdown["manipulation_risk"] == "Low"
