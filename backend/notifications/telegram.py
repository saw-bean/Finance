import asyncio
import datetime
import logging
import re
import httpx
from sqlalchemy import select, desc
from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.models import Position, Trade, AccountBalance, CatalystPerformance, Signal
from backend.agents.forensic_quant import forensic_agent

logger = logging.getLogger("alphaforge.telegram")

class TelegramNotifier:
    """Ultra-concise, non-spammy Telegram assistant for AlphaForge."""
    
    def __init__(self):
        self._polling_task = None
        self._last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)

    async def send_message(self, text: str, parse_mode: str = "HTML", chat_id: str = None) -> bool:
        if not self.is_configured:
            return False

        target_chat = chat_id or settings.TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.debug(f"Failed to send Telegram message: {e}")
            return False

    # -------------------------------------------------------------------------
    # Minimal 2-Line Push Alerts (Zero Clutter)
    # -------------------------------------------------------------------------
    async def send_buy_alert(self, symbol: str, qty: float, price: float, total_cost: float, reason: str, catalyst: str, stop_loss: float = None, take_profit: float = None, total_equity: float = None, cash: float = None):
        sl = f" | Stop: ${stop_loss:.2f}" if stop_loss else ""
        tp = f" | TP: ${take_profit:.2f}" if take_profit else ""
        text = f"🟢 <b>BUY ${symbol}</b>: {qty} shs @ ${price:.2f} (${total_cost:.2f}){sl}{tp}"
        await self.send_message(text)

    async def send_sell_alert(self, symbol: str, qty: float, exit_price: float, entry_price: float, realized_pnl: float, pnl_pct: float, reason: str, total_equity: float = None):
        is_win = realized_pnl >= 0
        emoji = "🟢" if is_win else "🔴"
        pnl = f"+${realized_pnl:.2f} (+{pnl_pct:.1f}%)" if is_win else f"-${abs(realized_pnl):.2f} ({pnl_pct:.1f}%)"
        text = f"{emoji} <b>SOLD ${symbol}</b>: {qty} shs @ ${exit_price:.2f} ({pnl})"
        await self.send_message(text)

    async def send_self_evolution_alert(self, title: str, reason: str, action: str):
        # Keep Telegram quiet - log internally only
        logger.info(f"Self-evolution upgrade: {title}")

    # -------------------------------------------------------------------------
    # Conversational Listener (Only Speaks When Spoken To)
    # -------------------------------------------------------------------------
    async def start_polling(self):
        if self._polling_task and not self._polling_task.done():
            return
        self._polling_task = asyncio.create_task(self._poll_updates_loop())

    async def stop_polling(self):
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

    async def _poll_updates_loop(self):
        while True:
            try:
                if not self.is_configured:
                    await asyncio.sleep(10)
                    continue

                url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates"
                params = {"timeout": 15, "offset": self._last_update_id + 1}
                
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for update in updates:
                            self._last_update_id = max(self._last_update_id, update["update_id"])
                            message = update.get("message")
                            if message and "text" in message:
                                chat_id = str(message["chat"]["id"])
                                if chat_id == str(settings.TELEGRAM_CHAT_ID):
                                    await self._handle_conversational_message(message["text"].strip(), chat_id)
            except Exception:
                await asyncio.sleep(3)
            await asyncio.sleep(1)

    async def _handle_conversational_message(self, user_msg: str, chat_id: str):
        msg = user_msg.lower().strip()

        # 1. Holdings / Active trades
        if any(k in msg for k in ["trade", "trades", "taking right now", "right now", "holding", "holdings", "open", "position", "positions", "stocks", "what do i hold", "what am i in", "/portfolio"]):
            await self._reply_current_holdings(chat_id)
            return

        # 2. Balance / Money / PnL
        if any(k in msg for k in ["balance", "money", "cash", "worth", "equity", "pnl", "p/l", "profit", "loss", "how much", "/status", "/pnl"]):
            await self._reply_balance_status(chat_id)
            return

        # 3. Trade history / recent executions
        if any(k in msg for k in ["history", "recent", "past", "what did we buy", "last trade", "executed", "/trades"]):
            await self._reply_recent_trades(chat_id)
            return

        # 4. "Why <ticker>"
        if "why" in msg:
            clean = user_msg.replace("why", "").replace("Why", "").replace("did", "").replace("we", "").replace("buy", "").strip("$.,!? ")
            words = clean.split()
            target = words[0].upper() if words else "PLTR"
            await self._reply_why_bought(target, chat_id)
            return

        # 5. Scan / Ticker lookup
        if any(k in msg for k in ["scan", "check", "analyze", "look at", "/scan"]) or (len(user_msg.split()) == 1 and len(user_msg) <= 5 and user_msg.isalpha()):
            words = [w.strip("$.,!?") for w in user_msg.split() if w.strip("$.,!?").isalpha() and len(w.strip("$.,!?")) <= 5]
            target_ticker = words[-1].upper() if words else "PLTR"
            if target_ticker.lower() not in ["hi", "hey", "help", "scan", "check"]:
                await self._reply_scan_ticker(target_ticker, chat_id)
                return

        # 6. Win rates
        if any(k in msg for k in ["learning", "win rate", "winrate", "accuracy", "strategies", "/learning"]):
            await self._reply_learning_winrates(chat_id)
            return

        # 7. Greetings
        if any(k in msg for k in ["hi", "hello", "hey", "help", "/help", "/start"]):
            await self.send_message(
                "💬 <b>AlphaForge Assistant</b>\nAsk me:\n• <code>trades</code>\n• <code>money</code>\n• <code>recent</code>\n• <code>why PLTR</code>\n• <code>scan NVDA</code>",
                chat_id=chat_id
            )
            return

        # Default: show holdings
        await self._reply_current_holdings(chat_id)

    # -------------------------------------------------------------------------
    # Ultra-Concise Plain English Answers
    # -------------------------------------------------------------------------
    async def _reply_current_holdings(self, chat_id: str):
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).order_by(desc(Position.market_value)))
            positions = pos_res.scalars().all()

        if not positions:
            await self.send_message("💼 <b>Holdings:</b> None (100% Cash: $100.00)", chat_id=chat_id)
            return

        lines = [f"💼 <b>Active Holdings ({len(positions)}):</b>"]
        for p in positions:
            pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
            lines.append(f"• <b>${p.symbol}</b>: ${p.market_value:.2f} ({pnl_sign}{p.unrealized_pnl_pct:.1f}%)")
        await self.send_message("\n".join(lines), chat_id=chat_id)

    async def _reply_balance_status(self, chat_id: str):
        from backend.execution.paper_engine import paper_engine
        from backend.api.routes import BOOT_TIME
        acc = await paper_engine.get_account_summary()
        pnl_sign = "+" if acc["total_pnl"] >= 0 else ""
        
        uptime_sec = int((datetime.datetime.now(datetime.UTC) - BOOT_TIME).total_seconds())
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"

        text = (
            f"💰 <b>Balance:</b> ${acc['total_equity']:.2f}\n"
            f"• <b>P/L:</b> {pnl_sign}${acc['total_pnl']:.2f} ({pnl_sign}{acc['total_pnl_pct']:.2f}%)\n"
            f"• <b>Invested:</b> ${acc['positions_value']:.2f}\n"
            f"• <b>Cash:</b> ${acc['cash']:.2f}\n"
            f"• ⏱️ <b>24/7 Uptime:</b> {uptime_str}"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _reply_recent_trades(self, chat_id: str):
        async with async_session_factory() as session:
            trade_res = await session.execute(select(Trade).order_by(desc(Trade.timestamp)).limit(3))
            trades = trade_res.scalars().all()

        if not trades:
            await self.send_message("📋 No recent trades.", chat_id=chat_id)
            return

        lines = ["📋 <b>Recent Trades:</b>"]
        for t in trades:
            badge = "BUY" if t.side == "BUY" else "SELL"
            lines.append(f"• {badge} <b>${t.symbol}</b> @ ${t.price:.2f} (${t.total_cost:.2f})")
        await self.send_message("\n".join(lines), chat_id=chat_id)

    async def _reply_why_bought(self, ticker: str, chat_id: str):
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).where(Position.symbol == ticker))
            pos = pos_res.scalars().first()

        if not pos:
            await self.send_message(f"We don't hold <b>${ticker}</b>.", chat_id=chat_id)
            return

        cat = pos.catalyst.replace("_", " ").title() if pos.catalyst else "Fundamental Screener"
        text = f"💡 <b>${ticker}:</b> {cat}\n• Entry: ${pos.avg_entry_price:.2f} | Stop: ${pos.stop_loss:.2f} | Target: ${pos.take_profit:.2f}"
        await self.send_message(text, chat_id=chat_id)

    async def _reply_scan_ticker(self, ticker: str, chat_id: str):
        data = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
        rec = data.get("recommendation", "HOLD")
        verdict = "🟢 Safe / Buy" if "BUY" in rec else ("🔴 High Risk" if "AVOID" in rec or "SHORT" in rec else "🟡 Neutral")
        text = f"🔍 <b>${ticker}</b>: {verdict}\n• Piotroski: {data.get('piotroski_f_score', 7)}/9 | Altman: {data.get('altman_zone', 'Safe')}"
        await self.send_message(text, chat_id=chat_id)

    async def _reply_learning_winrates(self, chat_id: str):
        async with async_session_factory() as session:
            perf_res = await session.execute(select(CatalystPerformance).order_by(desc(CatalystPerformance.win_rate)))
            perfs = perf_res.scalars().all()

        lines = ["🧠 <b>Strategy Win Rates:</b>"]
        for p in perfs[:3]:
            lines.append(f"• <b>{p.display_name}:</b> {p.win_rate*100:.0f}% ({p.calibrated_weight:.2f}x weight)")
        await self.send_message("\n".join(lines), chat_id=chat_id)

telegram_notifier = TelegramNotifier()
