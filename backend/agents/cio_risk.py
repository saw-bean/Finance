import datetime
import json
import logging
import asyncio
import httpx
import yfinance as yf
from sqlalchemy import select, update
from backend.agents.base import BaseAgent
from backend.db.session import async_session_factory, commit_with_retry
from backend.db.models import Signal, Position, AccountBalance, CatalystPerformance
from backend.execution.paper_engine import paper_engine
from backend.execution.alpaca_client import alpaca_client
from backend.config import settings

logger = logging.getLogger("alphaforge.cio_agent")

def _get_live_price_sync(ticker: str) -> float:
    ticker = ticker.upper().strip()
    try:
        stock = yf.Ticker(ticker)
        if hasattr(stock, 'fast_info') and stock.fast_info:
            p = stock.fast_info.get('last_price') or stock.fast_info.get('previous_close')
            if p and p > 0:
                return float(p)
        info = stock.info or {}
        p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0.0
        if p > 0:
            return float(p)
    except Exception:
        pass

    fallback_prices = {
        "PLTR": 180.50, "SOUN": 4.85, "HIMS": 28.50, "SMCI": 36.80, "BBAI": 2.95,
        "ASTS": 56.00, "RKLB": 24.10, "IONQ": 31.20, "JOBY": 8.40, "ACHR": 6.70,
        "AAPL": 235.00, "NVDA": 128.00, "TSLA": 215.00, "MSFT": 448.00, "AMZN": 188.00
    }
    return float(fallback_prices.get(ticker, 25.0))

class CioRiskAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="cio_risk_agent",
            display_name="CIO & Devil's Advocate Risk Agent",
            interval_seconds=30
        )

    async def run_iteration(self):
        await self.log("INFO", "Running CIO consensus, risk sizing & position monitoring cycle...")
        
        # 1. Update mark-to-market prices for all active open positions
        await self._update_open_positions_mtm()
        
        # 2. Process all pending unprocessed signals
        await self._process_unhandled_signals()
        
        # 3. Periodically record portfolio snapshot
        await paper_engine.record_snapshot()
        
        await self.update_status("RUNNING")

    async def _update_open_positions_mtm(self):
        """Fetches latest prices for active positions and checks stop-loss / take-profit."""
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position))
            positions = pos_res.scalars().all()
            if not positions:
                return
            symbols = [p.symbol for p in positions]
            
        price_map = {}
        for sym in symbols:
            p = await asyncio.to_thread(_get_live_price_sync, sym)
            if p > 0:
                price_map[sym] = round(p, 2)

        if price_map:
            await paper_engine.update_position_prices(price_map)

    async def _process_unhandled_signals(self):
        """Processes unhandled signals, evaluates risk, and executes trades without holding uncommitted sessions."""
        async with async_session_factory() as session:
            sig_res = await session.execute(
                select(Signal)
                .where(Signal.processed == False)
                .order_by(Signal.timestamp.asc())
            )
            raw_signals = sig_res.scalars().all()
            if not raw_signals:
                return
            
            # Extract signal data to memory to close read session
            signals_data = [
                (s.id, s.ticker.upper(), s.action.upper(), s.confidence, s.catalyst_type, s.title)
                for s in raw_signals
            ]
            
            # Fetch active accounting red flags in memory
            conflict_res = await session.execute(
                select(Signal.ticker).where(
                    Signal.catalyst_type == "ACCOUNTING_RED_FLAG",
                    Signal.timestamp >= datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
                )
            )
            red_flagged_tickers = set(conflict_res.scalars().all())

            # Fetch catalyst weights map
            perf_res = await session.execute(select(CatalystPerformance))
            perfs = perf_res.scalars().all()
            weight_map = {p.catalyst_type: p.calibrated_weight for p in perfs}

        processed_ids = []

        for sig_id, ticker, action, conf, catalyst, title in signals_data:
            processed_ids.append(sig_id)
            
            dynamic_weight = weight_map.get(catalyst, 1.0)
            effective_conf = min(0.98, max(0.20, conf * dynamic_weight))

            if action == "BUY":
                if ticker in red_flagged_tickers:
                    await self.log("WARNING", f"CIO Risk VETO on {ticker}: Accounting Red Flag present in memory. Trade rejected.", ticker=ticker)
                    continue

                account = await paper_engine.get_account_summary()
                total_equity = account["total_equity"]
                cash = account["cash"]

                # Check position concentration
                async with async_session_factory() as session:
                    pos_res = await session.execute(select(Position).where(Position.symbol == ticker))
                    existing_pos = pos_res.scalars().first()
                    current_holding_val = existing_pos.market_value if existing_pos else 0.0

                max_allowed_for_stock = total_equity * 0.25
                remaining_room = max_allowed_for_stock - current_holding_val
                
                if remaining_room <= 2.0:
                    continue

                target_allocation = min(remaining_room, max(5.0, total_equity * settings.MAX_POSITION_SIZE_PCT * effective_conf))
                order_size_dollars = min(target_allocation, cash * 0.95)
                
                if order_size_dollars < 3.0:
                    continue

                curr_price = await asyncio.to_thread(_get_live_price_sync, ticker)
                if curr_price <= 0:
                    continue

                raw_qty = order_size_dollars / curr_price
                qty = round(raw_qty, 4) if raw_qty < 1 else round(raw_qty, 2)
                if qty <= 0.0001:
                    continue

                trade_result = await paper_engine.execute_order(
                    symbol=ticker,
                    side="BUY",
                    qty=qty,
                    current_price=curr_price,
                    reason=f"CIO Synthesis: {title} (AI Weight: {dynamic_weight:.2f}x | Conf: {effective_conf*100:.0f}%)",
                    catalyst=catalyst,
                    stop_loss_pct=settings.DEFAULT_STOP_LOSS_PCT,
                    take_profit_pct=settings.DEFAULT_TAKE_PROFIT_PCT
                )

                if trade_result.get("success"):
                    await self.log("ACTION", f"EXECUTED BUY: {qty} shares of {ticker} @ ~${curr_price:.2f} (Weight: {dynamic_weight:.2f}x | Total: ${qty*curr_price:,.2f})", ticker=ticker)
                    await self._send_webhook_alert(f"🚀 **ALPHA TRADE EXECUTED**: BUY {qty} {ticker} @ ${curr_price:.2f}\n*Catalyst*: {title}\n*Calibrated Conviction*: {effective_conf*100:.0f}% ({dynamic_weight:.2f}x multiplier)")
                    if alpaca_client.is_configured():
                        await alpaca_client.submit_order(symbol=ticker, qty=qty, side="buy")
                else:
                    await self.log("WARNING", f"Paper execution failed for {ticker}: {trade_result.get('error')}", ticker=ticker)

            elif action == "SELL":
                async with async_session_factory() as session:
                    pos_res = await session.execute(select(Position).where(Position.symbol == ticker))
                    pos = pos_res.scalars().first()
                    pos_qty = pos.qty if pos else 0.0
                    pos_price = pos.current_price if pos else 0.0

                if pos_qty > 0:
                    curr_price = await asyncio.to_thread(_get_live_price_sync, ticker) or pos_price
                    trade_result = await paper_engine.execute_order(
                        symbol=ticker,
                        side="SELL",
                        qty=pos_qty,
                        current_price=curr_price,
                        reason=f"CIO Exit Trigger: {title}"
                    )
                    if trade_result.get("success"):
                        await self.log("ACTION", f"EXECUTED SELL EXIT: {pos_qty} shares of {ticker} @ ${curr_price:.2f}", ticker=ticker)
                        await self._send_webhook_alert(f"⚠️ **POSITION CLOSED**: SELL {pos_qty} {ticker} @ ${curr_price:.2f}\n*Reason*: {title}")
                        if alpaca_client.is_configured():
                            await alpaca_client.submit_order(symbol=ticker, qty=pos_qty, side="sell")

        # Mark all processed signals in a single clean transaction
        if processed_ids:
            async with async_session_factory() as session:
                await session.execute(
                    update(Signal).where(Signal.id.in_(processed_ids)).values(processed=True)
                )
                await commit_with_retry(session)

    async def _send_webhook_alert(self, message: str):
        if settings.DISCORD_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(settings.DISCORD_WEBHOOK_URL, json={"content": message})
            except Exception as e:
                logger.error(f"Discord webhook error: {e}")

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            try:
                tg_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(tg_url, json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
            except Exception as e:
                logger.error(f"Telegram alert error: {e}")

cio_agent = CioRiskAgent()
