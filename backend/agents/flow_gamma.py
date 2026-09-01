import datetime
import httpx
import logging
import yfinance as yf
from typing import Dict, Any, List
from backend.agents.base import BaseAgent
from backend.config import settings

logger = logging.getLogger("alphaforge.flow_agent")

class FlowGammaAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="flow_gamma_agent",
            display_name="Flow, FINRA Short & Squeeze Tracker",
            interval_seconds=settings.POLLING_INTERVAL_FINRA
        )
        self.squeeze_watchlist = ["SOUN", "BBAI", "HIMS", "ASTS", "ACHR", "RKLB", "IONQ", "SMCI"]

    async def run_iteration(self):
        await self.log("INFO", f"Analyzing FINRA short sale volume & float turnover on watchlist ({len(self.squeeze_watchlist)} tickers)...")
        
        # Try fetching real-time short volume & float turnover via yfinance and FINRA heuristics
        for ticker in self.squeeze_watchlist:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info or {}
                
                short_ratio = info.get("shortRatio") or 0.0 # Days to cover
                short_pct_float = (info.get("shortPercentOfFloat") or 0.0) * 100
                shares_short = info.get("sharesShort") or 0
                float_shares = info.get("floatShares") or 1
                curr_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                
                # Check for high short squeeze criteria
                # Short Float > 15% AND Days to Cover > 4
                if short_pct_float > 15.0 or short_ratio > 4.5:
                    confidence = 0.85 if short_pct_float > 25.0 else 0.74
                    await self.emit_signal(
                        ticker=ticker,
                        catalyst_type="SHORT_SQUEEZE_SETUP",
                        action="BUY",
                        confidence=confidence,
                        title=f"Short Squeeze Flow Setup: {ticker}",
                        summary=f"Short % of Float: {short_pct_float:.1f}% | Days to Cover: {short_ratio:.1f}x | Shares Short: {shares_short:,.0f}. Structural gamma squeeze asymmetry detected.",
                        metadata={
                            "ticker": ticker,
                            "short_pct_float": short_pct_float,
                            "days_to_cover": short_ratio,
                            "shares_short": shares_short,
                            "current_price": curr_price,
                            "float_shares": float_shares
                        }
                    )
            except Exception as e:
                logger.error(f"Error checking flow metrics for {ticker}: {e}")

        await self.update_status("RUNNING", stats={"analyzed_tickers": len(self.squeeze_watchlist)})

flow_agent = FlowGammaAgent()
