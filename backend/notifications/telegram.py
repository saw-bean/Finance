import asyncio
import datetime
import logging
import httpx
from sqlalchemy import select, desc
from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.models import Position, Trade, AccountBalance, CatalystPerformance, Signal
from backend.agents.forensic_quant import forensic_agent

logger = logging.getLogger("alphaforge.telegram")

class TelegramNotifier:
    """Institutional-grade Telegram alert and interactive command engine for AlphaForge."""
    
    def __init__(self):
        self._polling_task = None
        self._last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)

    async def send_message(self, text: str, parse_mode: str = "HTML", chat_id: str = None) -> bool:
        if not self.is_configured:
            logger.debug("Telegram not configured. Skipping alert.")
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
                if res.status_code == 200:
                    logger.info("Telegram notification dispatched successfully.")
                    return True
                else:
                    logger.error(f"Telegram API returned status {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def send_buy_alert(self, symbol: str, qty: float, price: float, total_cost: float, reason: str, catalyst: str, stop_loss: float = None, take_profit: float = None, total_equity: float = None, cash: float = None):
        text = (
            f"🚀 <b>ALPHAFORGE: BUY ORDER EXECUTED</b>\n\n"
            f"<b>Asset:</b> <code>${symbol}</code>\n"
            f"<b>Quantity:</b> <code>{qty} shares</code>\n"
            f"<b>Fill Price:</b> <code>${price:.2f}</code>\n"
            f"<b>Total Cost:</b> <code>${total_cost:,.2f}</code>\n\n"
            f"<b>📊 Catalyst:</b> <i>{catalyst or 'Multi-Agent Consensus'}</i>\n"
            f"<b>💡 Thesis:</b> <i>{reason}</i>\n\n"
        )
        if stop_loss or take_profit:
            text += f"<b>🛡️ Automated Risk Protection:</b>\n"
            if stop_loss:
                text += f"• Stop-Loss (-5%): <code>${stop_loss:.2f}</code>\n"
            if take_profit:
                text += f"• Profit Target (+15%): <code>${take_profit:.2f}</code>\n"
                
        if total_equity is not None and cash is not None:
            text += f"\n<b>💼 Portfolio Status:</b> Equity: <code>${total_equity:.2f}</code> | Cash: <code>${cash:.2f}</code>\n"
        
        text += f"\n<i>AlphaForge Swarm • Public Feeds</i>"
        await self.send_message(text)

    async def send_sell_alert(self, symbol: str, qty: float, exit_price: float, entry_price: float, realized_pnl: float, pnl_pct: float, reason: str, total_equity: float = None):
        is_win = realized_pnl >= 0
        status_emoji = "🟢 <b>PROFIT LOCKED</b>" if is_win else "🔴 <b>STOP-LOSS EXIT</b>"
        
        text = (
            f"⚠️ <b>ALPHAFORGE: POSITION CLOSED</b>\n\n"
            f"{status_emoji}\n"
            f"<b>Asset:</b> <code>${symbol}</code>\n"
            f"<b>Shares Sold:</b> <code>{qty}</code>\n"
            f"<b>Exit Price:</b> <code>${exit_price:.2f}</code> (Entry: <code>${entry_price:.2f}</code>)\n"
            f"<b>Realized Return:</b> <code>{'+' if is_win else ''}${realized_pnl:.2f} ({'+' if is_win else ''}{pnl_pct:.2f}%)</code>\n\n"
            f"<b>Trigger Rationale:</b> <i>{reason}</i>\n"
        )
        if total_equity is not None:
            text += f"\n<b>💼 Updated Account Equity:</b> <code>${total_equity:.2f}</code>\n"
            
        text += f"\n<i>Autonomous Learning Engine Updating Strategy Win Rates...</i>"
        await self.send_message(text)

    async def send_self_evolution_alert(self, title: str, reason: str, action: str):
        text = (
            f"🛠️ <b>ALPHAFORGE: AUTONOMOUS UPGRADE DEPLOYED</b>\n\n"
            f"<b>New Capability:</b> <code>{title}</code>\n"
            f"<b>Trigger:</b> <i>{reason}</i>\n"
            f"<b>Action Taken:</b> <i>{action}</i>\n\n"
            f"<i>Zero-permission self-evolution active in live swarm.</i>"
        )
        await self.send_message(text)

    # -------------------------------------------------------------------------
    # Interactive Telegram Command Listener
    # -------------------------------------------------------------------------
    async def start_polling(self):
        """Starts background listener for user commands (/status, /pnl, /trades, /scan)."""
        if self._polling_task and not self._polling_task.done():
            return
        self._polling_task = asyncio.create_task(self._poll_updates_loop())
        logger.info("Telegram command listener started.")

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
                                # Only respond to authorized user
                                if chat_id == str(settings.TELEGRAM_CHAT_ID):
                                    await self._handle_command(message["text"].strip(), chat_id)
            except Exception as e:
                logger.debug(f"Telegram polling loop exception: {e}")
                await asyncio.sleep(3)
            await asyncio.sleep(1)

    async def _handle_command(self, cmd_text: str, chat_id: str):
        """Handles incoming interactive Telegram slash commands."""
        parts = cmd_text.split()
        command = parts[0].lower() if parts else ""
        arg = parts[1].upper() if len(parts) > 1 else ""

        if command in ["/status", "/pnl", "/account"]:
            await self._cmd_status(chat_id)
        elif command in ["/portfolio", "/positions", "/holdings"]:
            await self._cmd_portfolio(chat_id)
        elif command in ["/trades", "/history", "/orders"]:
            await self._cmd_trades(chat_id)
        elif command in ["/learning", "/winrates", "/weights"]:
            await self._cmd_learning(chat_id)
        elif command in ["/scan", "/analyze", "/check"]:
            if not arg:
                await self.send_message("🔍 Please specify a ticker to scan. Example: <code>/scan NVDA</code>", chat_id=chat_id)
            else:
                await self._cmd_scan(arg, chat_id)
        elif command in ["/help", "/start", "/commands"]:
            await self._cmd_help(chat_id)
        else:
            await self.send_message(
                f"❓ Unknown command: <code>{command}</code>\nType <b>/help</b> to view all available commands.",
                chat_id=chat_id
            )

    async def _cmd_status(self, chat_id: str):
        from backend.execution.paper_engine import paper_engine
        acc = await paper_engine.get_account_summary()
        
        is_pos = acc["total_pnl"] >= 0
        pnl_sign = "+" if is_pos else ""
        status_emoji = "🟢" if is_pos else "🔴"

        text = (
            f"📊 <b>ALPHAFORGE ACCOUNT STATUS & P/L</b>\n\n"
            f"<b>Total Account Value:</b> <code>${acc['total_equity']:.2f}</code>\n"
            f"<b>Starting Capital:</b> <code>${acc['initial_capital']:.2f}</code>\n\n"
            f"<b>{status_emoji} Net Return:</b> <code>{pnl_sign}${acc['total_pnl']:.2f} ({pnl_sign}{acc['total_pnl_pct']:.2f}%)</code>\n"
            f"<b>💼 Invested Capital:</b> <code>${acc['positions_value']:.2f}</code>\n"
            f"<b>💵 Available Cash:</b> <code>${acc['cash']:.2f}</code>\n"
            f"<b>📈 Active Positions:</b> <code>{acc['open_positions_count']} stocks</code>\n\n"
            f"<i>Type <b>/portfolio</b> to view holdings or <b>/trades</b> for history.</i>"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _cmd_portfolio(self, chat_id: str):
        async with async_session_factory() as session:
            pos_res = await session.execute(select(Position).order_by(desc(Position.market_value)))
            positions = pos_res.scalars().all()

        if not positions:
            await self.send_message("💼 <b>PORTFOLIO EMPTY</b>\nNo open positions. Cash is 100% liquid awaiting catalysts.", chat_id=chat_id)
            return

        text = f"💼 <b>ACTIVE PORTFOLIO HOLDINGS ({len(positions)}):</b>\n\n"
        for p in positions:
            is_pos = p.unrealized_pnl >= 0
            pnl_sign = "+" if is_pos else ""
            text += (
                f"• <b>${p.symbol}</b> ({p.qty:.3f} shs)\n"
                f"  Value: <code>${p.market_value:.2f}</code> (Entry: ${p.avg_entry_price:.2f} | Live: ${p.current_price:.2f})\n"
                f"  P/L: <code>{pnl_sign}${p.unrealized_pnl:.2f} ({pnl_sign}{p.unrealized_pnl_pct:.2f}%)</code>\n"
                f"  SL: <code>${p.stop_loss:.2f}</code> | TP: <code>${p.take_profit:.2f}</code>\n\n"
            )
        text += "<i>AlphaForge Risk Engine Monitoring Prices 24/7</i>"
        await self.send_message(text, chat_id=chat_id)

    async def _cmd_trades(self, chat_id: str):
        async with async_session_factory() as session:
            trade_res = await session.execute(select(Trade).order_by(desc(Trade.timestamp)).limit(6))
            trades = trade_res.scalars().all()

        if not trades:
            await self.send_message("📋 <b>TRADE LEDGER EMPTY</b>\nNo trades executed yet.", chat_id=chat_id)
            return

        text = f"📋 <b>RECENT TRADE EXECUTION LEDGER:</b>\n\n"
        for t in trades:
            side_badge = "🟢 BUY" if t.side == "BUY" else "🔴 SELL"
            pnl_text = f" | PnL: <b>${t.realized_pnl:+.2f}</b>" if t.side == "SELL" else ""
            text += (
                f"• {side_badge} <b>${t.symbol}</b>: {t.qty:.3f} shs @ ${t.price:.2f}\n"
                f"  Total: <code>${t.total_cost:.2f}</code>{pnl_text}\n"
                f"  Reason: <i>{t.reason[:60]}...</i>\n"
                f"  Time: <code>{t.timestamp.strftime('%H:%M:%S UTC')}</code>\n\n"
            )
        await self.send_message(text, chat_id=chat_id)

    async def _cmd_learning(self, chat_id: str):
        async with async_session_factory() as session:
            perf_res = await session.execute(select(CatalystPerformance).order_by(desc(CatalystPerformance.win_rate)))
            perfs = perf_res.scalars().all()

        text = "🧠 <b>AI STRATEGY WIN RATES & DYNAMIC MULTIPLIERS:</b>\n\n"
        for p in perfs:
            text += (
                f"• <b>{p.display_name}</b>\n"
                f"  Win Rate: <code>{p.win_rate*100:.1f}%</code> ({p.wins}W / {p.losses}L)\n"
                f"  AI Conviction Weight: <code>{p.calibrated_weight:.2f}x</code>\n"
                f"  Net PnL: <code>${p.total_pnl:+.2f}</code>\n\n"
            )
        text += "<i>System dynamically sizes up winning strategies and throttles losing ones.</i>"
        await self.send_message(text, chat_id=chat_id)

    async def _cmd_scan(self, ticker: str, chat_id: str):
        await self.send_message(f"🔍 Running real-time fundamental & forensic scan on <b>${ticker}</b>...", chat_id=chat_id)
        data = await asyncio.to_thread(forensic_agent.analyze_ticker, ticker)
        
        if not data or "error" in data:
            await self.send_message(f"❌ Scan failed for ${ticker}: {data.get('error', 'Unable to fetch filings')}", chat_id=chat_id)
            return

        rec = data.get("recommendation", "NEUTRAL")
        verdict_badge = "🟢 <b>STRONG BUY / SAFE</b>" if "BUY" in rec else ("🔴 <b>HIGH RISK / RED FLAG</b>" if "AVOID" in rec or "SHORT" in rec else "🟡 <b>NEUTRAL</b>")

        text = (
            f"📊 <b>FORENSIC SCAN: ${data.get('ticker')} ({data.get('company_name')})</b>\n\n"
            f"<b>Verdict:</b> {verdict_badge}\n"
            f"<b>Current Price:</b> <code>${data.get('current_price', 0):.2f}</code>\n\n"
            f"• <b>Piotroski F-Score:</b> <code>{data.get('piotroski_f_score')}/9</code> ({'Strong Health' if data.get('piotroski_f_score', 0)>=7 else 'Weak'})\n"
            f"• <b>Beneish M-Score:</b> <code>{data.get('beneish_m_score')}</code> ({data.get('earnings_quality')})\n"
            f"• <b>Altman Z-Score:</b> <code>{data.get('altman_z_score')}</code> ({data.get('altman_zone')} Zone)\n"
            f"• <b>Sloan Accrual:</b> <code>{data.get('sloan_accrual_ratio')}%</code>\n\n"
            f"<i>Type <b>/status</b> to return to account overview.</i>"
        )
        await self.send_message(text, chat_id=chat_id)

    async def _cmd_help(self, chat_id: str):
        text = (
            f"🤖 <b>ALPHAFORGE TELEGRAM COMMANDS:</b>\n\n"
            f"• <b>/status</b> or <b>/pnl</b> - View total account equity, cash buffer & P/L\n"
            f"• <b>/portfolio</b> - View all active stock holdings & stop-loss targets\n"
            f"• <b>/trades</b> - View recent execution ledger with prices & reasons\n"
            f"• <b>/learning</b> - View AI strategy win rates & conviction multipliers\n"
            f"• <b>/scan &lt;TICKER&gt;</b> - Run instant forensic scan (e.g. <code>/scan NVDA</code>)\n"
            f"• <b>/help</b> - Show this help menu\n\n"
            f"<i>AlphaForge Swarm • Autonomous Multi-Agent Trading</i>"
        )
        await self.send_message(text, chat_id=chat_id)

telegram_notifier = TelegramNotifier()
