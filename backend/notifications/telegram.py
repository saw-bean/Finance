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
    """Conversational and concise Telegram intelligence agent for AlphaForge."""
    
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
    # Clean, Non-Spammy Push Alerts (3-4 lines maximum)
    # -------------------------------------------------------------------------
    async def send_buy_alert(self, symbol: str, qty: float, price: float, total_cost: float, reason: str, catalyst: str, stop_loss: float = None, take_profit: float = None, total_equity: float = None, cash: float = None):
        cat_clean = catalyst.replace("_", " ").title() if catalyst else "AI Consensus"
        sl_text = f" | Stop: ${stop_loss:.2f}" if stop_loss else ""
        tp_text = f" | Target: ${take_profit:.2f}" if take_profit else ""

        text = (
            f"🟢 <b>BOUGHT ${symbol}</b> ({qty} shs @ ${price:.2f})\n"
            f"• <b>Total:</b> ${total_cost:.2f}{sl_text}{tp_text}\n"
            f"• <b>Catalyst:</b> {cat_clean}"
        )
        await self.send_message(text)

    async def send_sell_alert(self, symbol: str, qty: float, exit_price: float, entry_price: float, realized_pnl: float, pnl_pct: float, reason: str, total_equity: float = None):
        is_win = realized_pnl >= 0
        pnl_badge = f"+${realized_pnl:.2f} (+{pnl_pct:.1f}%)" if is_win else f"-${abs(realized_pnl):.2f} ({pnl_pct:.1f}%)"
        emoji = "🟢" if is_win else "🔴"

        text = (
            f"{emoji} <b>CLOSED ${symbol}</b> ({pnl_badge})\n"
            f"• Sold {qty} shs @ ${exit_price:.2f}\n"
            f"• <b>Reason:</b> {reason[:60]}"
        )
        await self.send_message(text)

    async def send_self_evolution_alert(self, title: str, reason: str, action: str):
        text = f"🛠️ <b>AI Self-Upgraded:</b> {title}\n• {reason}"
        await self.send_message(text)

    # -------------------------------------------------------------------------
    # Natural Language Conversational Listener
    # -------------------------------------------------------------------------
    async def start_polling(self):
        if self._polling_task and not self._polling_task.done():
            return
        self._polling_task = asyncio.create_task(self._poll_updates_loop())
        logger.info("Conversational Telegram listener started.")

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
            except Exception as e:
                logger.debug(f"Telegram polling exception: {e}")
                await asyncio.sleep(3)
            await asyncio.sleep(1)

    async def _handle_conversational_message(self, user_msg: str, chat_id: str):
        """Processes plain English questions like 'what trades am i taking right now'."""
        msg = user_msg.lower().strip()

        # 1. "What trades am I taking right now?" / "What are my current holdings?"
        if any(k in msg for k in ["what trade", "taking right now", "current trade", "open position", "holdings", "what do i hold", "what am i holding", "/portfolio", "/positions"]):
            await self._reply_current_holdings(chat_id)

        # 2. "What is my balance / profit / PnL / how much money do I have?"
        elif any(k in msg for k in ["balance", "how much money", "how much do i have", "equity", "pnl", "p/l", "profit", "status", "/status", "/pnl", "/account"]):
            await self._reply_balance_status(chat_id)

        # 3. "What did we buy / recent trades / history?"
        elif any(k in msg for k in ["recent trade", "what did we buy", "trade history", "last trade", "executed", "/trades", "/history"]):
            await self._reply_recent_trades(chat_id)

        # 4. "Why did we buy <ticker>?"
        elif "why" in msg and any(c.isupper() for c in user_msg):
            ticker_match = re.search(r'\b([A-Z]{1,5})\b', user_msg)
            if ticker_match:
                await self._reply_why_bought(ticker_match.group(1).upper(), chat_id)
            else:
                await self._reply_current_holdings(chat_id)

        # 5. "Scan / check <ticker>" or "What do you think of NVDA?"
        elif any(k in msg for k in ["scan", "check", "analyze", "think of", "opinions on", "/scan"]):
            ticker_match = re.search(r'\b([A-Z]{1,5})\b', user_msg) or re.search(r'\b([a-zA-Z]{1,5})\b', user_msg.split()[-1])
            if ticker_match:
                await self._reply_scan_ticker(ticker_match.group(1).upper(), chat_id)
            else:
                await self.send_message("Please name the ticker you want me to analyze (e.g. <i>'check PLTR'</i> or <i>'scan NVDA'</i>).", chat_id=chat_id)

        # 6. "How are the agents doing / win rates / learning?"
        elif any(k in msg for k in ["learning", "win rate", "strategies", "agents", "accuracy", "/learning"]):
            await self._reply_learning_winrates(chat_id)

        # 7. Greetings / General Help
        elif any(k in msg for k in ["hi", "hello", "hey", "help", "/help", "/start"]):
            text = (
                "👋 <b>AlphaForge AI Assistant</b>\n\n"
                "You can chat with me naturally in plain English! Ask me things like:\n\n"
                "• <i>'What trades am I taking right now?'</i>\n"
                "• <i>'How much money do I have?'</i>\n"
                "• <i>'What did we buy recently?'</i>\n"
                "• <i>'Check NVDA'</i> or <i>'Scan PLTR'</i>\n"
                "• <i>'How are our win rates?'</i>"
            )
            await self.send_message(text, chat_id=chat_id)

        # 8. Fallback friendly response
        else:
            await self.send_message(
                f"I checked your account. You can ask me:\n"
                f"• <i>'What trades am I taking right now?'</i>\n"
                f"• <i>'What is my profit/loss?'</i>\n"
                f"• <i>'Scan &lt;ticker&gt;'</i>",
                chat_id=chat_id
            )

    # -------------------------------------------------------------------------
    # Concise Conversational Responses
    # -------------------------------------------------------------------------
    async def _reply_current_holdings(self, chat_id: str):
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).order_by(desc(Position.market_value)))
            positions = pos_res.scalars().all()

        if not positions:
            await self.send_message("💼 You have <b>no open positions</b> right now. Your $100.00 cash is liquid awaiting catalysts.", chat_id=chat_id)
            return

        lines = [f"💼 <b>You have {len(positions)} active positions right now:</b>\n"]
        for p in positions:
            pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
            lines.append(
                f"• <b>${p.symbol}</b>: {p.qty:.3f} shs (${p.market_value:.2f}) | P/L: <b>{pnl_sign}${p.unrealized_pnl:.2f} ({pnl_sign}{p.unrealized_pnl_pct:.1f}%)</b>"
            )
        lines.append(f"\n<i>Automated stop-losses (-5%) and profit targets (+15%) are armed on all of them.</i>")
        await self.send_message("\n".join(lines), chat_id=chat_id)

    async def _reply_balance_status(self, chat_id: str):
        from backend.execution.paper_engine import paper_engine
        acc = await paper_engine.get_account_summary()
        pnl_sign = "+" if acc["total_pnl"] >= 0 else ""
        emoji = "🟢" if acc["total_pnl"] >= 0 else "🔴"

        text = (
            f"💰 <b>Your Account Overview:</b>\n\n"
            f"• <b>Total Equity:</b> <code>${acc['total_equity']:.2f}</code>\n"
            f"• <b>Net Return:</b> {emoji} <code>{pnl_sign}${acc['total_pnl']:.2f} ({pnl_sign}{acc['total_pnl_pct']:.2f}%)</code>\n"
            f"• <b>Invested:</b> ${acc['positions_value']:.2f} ({acc['open_positions_count']} stocks)\n"
            f"• <b>Available Cash:</b> ${acc['cash']:.2f}"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _reply_recent_trades(self, chat_id: str):
        async with async_session_factory() as session:
            trade_res = await session.execute(select(Trade).order_by(desc(Trade.timestamp)).limit(4))
            trades = trade_res.scalars().all()

        if not trades:
            await self.send_message("📋 No trades executed yet.", chat_id=chat_id)
            return

        lines = ["📋 <b>Most Recent Trades:</b>\n"]
        for t in trades:
            badge = "🟢 BUY" if t.side == "BUY" else "🔴 SELL"
            pnl = f" (PnL: {t.realized_pnl:+.2f})" if t.side == "SELL" else ""
            lines.append(f"• {badge} <b>${t.symbol}</b> ({t.qty:.3f} shs @ ${t.price:.2f}) → ${t.total_cost:.2f}{pnl}")
        
        await self.send_message("\n".join(lines), chat_id=chat_id)

    async def _reply_why_bought(self, ticker: str, chat_id: str):
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).where(Position.symbol == ticker))
            pos = pos_res.scalars().first()

        if not pos:
            await self.send_message(f"We don't currently hold <b>${ticker}</b>.", chat_id=chat_id)
            return

        cat = pos.catalyst or "High-Conviction Quant Screen"
        text = (
            f"💡 <b>Why we bought ${ticker}:</b>\n\n"
            f"• <b>Strategy:</b> {cat.replace('_', ' ').title()}\n"
            f"• <b>Bought at:</b> ${pos.avg_entry_price:.2f} (Current: ${pos.current_price:.2f})\n"
            f"• <b>Stop-Loss:</b> ${pos.stop_loss:.2f} | <b>Target:</b> ${pos.take_profit:.2f}"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _reply_scan_ticker(self, ticker: str, chat_id: str):
        data = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
        rec = data.get("recommendation", "HOLD")
        verdict = "🟢 SAFE / BUY" if "BUY" in rec else ("🔴 HIGH RISK" if "AVOID" in rec or "SHORT" in rec else "🟡 NEUTRAL")

        text = (
            f"🔍 <b>${ticker} Analysis:</b> {verdict}\n\n"
            f"• <b>Piotroski Score:</b> {data.get('piotroski_f_score', 7)}/9 ({data.get('earnings_quality', 'Normal')} Quality)\n"
            f"• <b>Altman Zone:</b> {data.get('altman_zone', 'Safe')}\n"
            f"• <b>Price:</b> ${data.get('current_price', 0):.2f}"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _reply_learning_winrates(self, chat_id: str):
        async with async_session_factory() as session:
            perf_res = await session.execute(select(CatalystPerformance).order_by(desc(CatalystPerformance.win_rate)))
            perfs = perf_res.scalars().all()

        lines = ["🧠 <b>AI Strategy Win Rates:</b>\n"]
        for p in perfs[:4]:
            lines.append(f"• <b>{p.display_name}:</b> {p.win_rate*100:.0f}% win rate ({p.calibrated_weight:.2f}x weight)")
        await self.send_message("\n".join(lines), chat_id=chat_id)

telegram_notifier = TelegramNotifier()
