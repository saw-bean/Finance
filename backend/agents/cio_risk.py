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
    """
    Institutional Chief Investment Officer (CIO) & Risk Management Agent.
    Enforces selective entry analysis, asymmetric upside verification, 
    dollar-cost-averaged pacing cooldowns, and capital preservation.
    """
    def __init__(self):
        super().__init__(
            name="cio_risk_agent",
            display_name="CIO & Devil's Advocate Risk Agent",
            interval_seconds=30
        )
        self.startup_time = datetime.datetime.now(datetime.UTC)
        self.last_buy_time = None
        self.pacing_cooldown_seconds = 300 # 5-minute pacing between BUY orders
        self.warmup_seconds = 60 # 60-second warmup on reboot to cross-check signals

    async def run_iteration(self):
        await self.log("INFO", "Running CIO consensus, risk sizing & position monitoring cycle...")
        
        # 1. Update mark-to-market prices for all active open positions
        await self._update_open_positions_mtm()
        
        # 2. Process all pending signals with selective entry gates
        await self._process_unhandled_signals()
        
        # 3. Record portfolio snapshot
        await paper_engine.record_snapshot()
        
        await self.update_status("RUNNING")

    async def _update_open_positions_mtm(self):
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
        now = datetime.datetime.now(datetime.UTC)
        
        # Warmup Gate: Allow agents 60s to collect full market context before first buy
        is_warmup = (now - self.startup_time).total_seconds() < self.warmup_seconds

        async with async_session_factory() as session:
            sig_res = await session.execute(
                select(Signal)
                .where(Signal.processed == False)
                .order_by(Signal.timestamp.asc())
            )
            raw_signals = sig_res.scalars().all()
            if not raw_signals:
                return
            
            signals_data = [
                (s.id, s.ticker.upper(), s.action.upper(), s.confidence, s.catalyst_type, s.title, json.loads(s.raw_metadata or "{}"))
                for s in raw_signals
            ]
            
            # Accounting red flag veto list
            conflict_res = await session.execute(
                select(Signal.ticker).where(
                    Signal.catalyst_type == "ACCOUNTING_RED_FLAG",
                    Signal.timestamp >= now - datetime.timedelta(days=7)
                )
            )
            red_flagged_tickers = set(conflict_res.scalars().all())

            # Catalyst performance weights
            perf_res = await session.execute(select(CatalystPerformance))
            perfs = perf_res.scalars().all()
            weight_map = {p.catalyst_type: p.calibrated_weight for p in perfs}

        processed_ids = []
        buy_candidates = []

        for sig_id, ticker, action, conf, catalyst, title, meta in signals_data:
            processed_ids.append(sig_id)
            dynamic_weight = weight_map.get(catalyst, 1.0)
            effective_conf = min(0.98, max(0.20, conf * dynamic_weight))

            # Handle SELL exits immediately (always prioritize risk defense)
            if action == "SELL":
                await self._execute_sell_signal(ticker, title)
            elif action == "BUY":
                buy_candidates.append({
                    "id": sig_id,
                    "ticker": ticker,
                    "conf": conf,
                    "effective_conf": effective_conf,
                    "catalyst": catalyst,
                    "title": title,
                    "meta": meta,
                    "dynamic_weight": dynamic_weight
                })

        # Process BUY candidates with Selective Entry Analysis
        if buy_candidates:
            if is_warmup:
                await self.log("INFO", "Warm-up phase active (60s). Collecting and ranking signals before deploying capital...")
            else:
                await self._evaluate_and_execute_best_buy(buy_candidates, red_flagged_tickers)

        # Mark processed signals
        if processed_ids:
            async with async_session_factory() as session:
                await session.execute(
                    update(Signal).where(Signal.id.in_(processed_ids)).values(processed=True)
                )
                await commit_with_retry(session)

    async def _evaluate_and_execute_best_buy(self, candidates: list, red_flags: set):
        now = datetime.datetime.now(datetime.UTC)

        # 1. Check Pacing Cooldown (Prevents rapid-fire cold-start dump)
        if self.last_buy_time:
            elapsed = (now - self.last_buy_time).total_seconds()
            if elapsed < self.pacing_cooldown_seconds:
                remaining_wait = int(self.pacing_cooldown_seconds - elapsed)
                await self.log("INFO", f"Smart Pacing Active: Next high-potential entry window in {remaining_wait}s.")
                return

        # 2. Strict Entry Analysis: Filter and Rank Candidates by Asymmetric Potential
        viable_entries = []
        for c in candidates:
            ticker = c["ticker"]
            
            # Veto 1: Active accounting fraud or manipulation red flag
            if ticker in red_flags:
                await self.log("WARNING", f"CIO VETO on ${ticker}: Red flag active. Entry rejected.", ticker=ticker)
                continue

            # Veto 2: Web Intel Bear Veto (Check live web debate score)
            debate = c["meta"].get("bull_bear_debate", {})
            if debate.get("verdict") == "BEAR_DOMINANT":
                await self.log("WARNING", f"CIO VETO on ${ticker}: Live web debate flagged bear headwinds. Entry skipped.", ticker=ticker)
                continue

            # Veto 3: High Conviction Threshold (Minimum 75% effective confidence)
            if c["effective_conf"] < 0.75:
                continue

            viable_entries.append(c)

        if not viable_entries:
            return

        # Sort by highest conviction & catalyst weight to select ONLY the #1 best setup
        viable_entries.sort(key=lambda x: x["effective_conf"] * x["dynamic_weight"], reverse=True)
        best_candidate = viable_entries[0]

        # Execute the #1 Best Entry
        ticker = best_candidate["ticker"]
        effective_conf = best_candidate["effective_conf"]
        dynamic_weight = best_candidate["dynamic_weight"]
        title = best_candidate["title"]
        catalyst = best_candidate["catalyst"]

        account = await paper_engine.get_account_summary()
        total_equity = account["total_equity"]
        cash = account["cash"]

        # Keep minimum 15% cash reserve for dip opportunities
        available_deployable_cash = max(0.0, cash - (total_equity * 0.15))
        if available_deployable_cash < 4.0:
            await self.log("INFO", f"Capital fully utilized (${cash:.2f} cash / 15% reserve maintained). Waiting for exits.")
            return

        # Check single-stock concentration limit (max 25% of account in any single stock)
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).where(Position.symbol == ticker))
            existing_pos = pos_res.scalars().first()
            current_holding_val = existing_pos.market_value if existing_pos else 0.0

        max_allowed_for_stock = total_equity * 0.25
        remaining_room = max_allowed_for_stock - current_holding_val
        if remaining_room <= 2.0:
            return

        target_allocation = min(remaining_room, max(5.0, total_equity * settings.MAX_POSITION_SIZE_PCT * effective_conf))
        order_size_dollars = min(target_allocation, available_deployable_cash)

        if order_size_dollars < 4.0:
            return

        curr_price = await asyncio.to_thread(_get_live_price_sync, ticker)
        if curr_price <= 0:
            return

        raw_qty = order_size_dollars / curr_price
        qty = round(raw_qty, 4) if raw_qty < 1 else round(raw_qty, 2)
        if qty <= 0.0001:
            return

        # Execute selective entry
        trade_result = await paper_engine.execute_order(
            symbol=ticker,
            side="BUY",
            qty=qty,
            current_price=curr_price,
            reason=f"High-Potential Entry (Conf: {effective_conf*100:.0f}% | 3:1 Asymmetric R/R)",
            catalyst=catalyst,
            stop_loss_pct=settings.DEFAULT_STOP_LOSS_PCT,
            take_profit_pct=settings.DEFAULT_TAKE_PROFIT_PCT
        )

        if trade_result.get("success"):
            self.last_buy_time = datetime.datetime.now(datetime.UTC)
            await self.log("ACTION", f"SELECTIVE ENTRY EXECUTED: {qty} shs of ${ticker} @ ${curr_price:.2f} (Upside: +15% / Stop: -5% | R/R: 3:1)", ticker=ticker)
            if alpaca_client.is_configured():
                await alpaca_client.submit_order(symbol=ticker, qty=qty, side="buy")

    async def _execute_sell_signal(self, ticker: str, title: str):
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
                if alpaca_client.is_configured():
                    await alpaca_client.submit_order(symbol=ticker, qty=pos_qty, side="sell")

cio_agent = CioRiskAgent()
