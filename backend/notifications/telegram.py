import logging
import httpx
from backend.config import settings

logger = logging.getLogger("alphaforge.telegram")

class TelegramNotifier:
    """Institutional-grade Telegram alert engine for AlphaForge."""
    
    @property
    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured:
            logger.debug("Telegram not configured. Skipping alert.")
            return False

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info("Telegram trade notification dispatched successfully.")
                    return True
                else:
                    logger.error(f"Telegram API returned status {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def send_buy_alert(self, symbol: str, qty: float, price: float, total_cost: float, reason: str, catalyst: str, stop_loss: float = None, take_profit: float = None, total_equity: float = None, cash: float = None):
        """Sends rich BUY trade execution alert."""
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
        """Sends rich SELL / Exit trade alert."""
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
        """Sends notification when system self-upgrades without permission."""
        text = (
            f"🛠️ <b>ALPHAFORGE: AUTONOMOUS UPGRADE DEPLOYED</b>\n\n"
            f"<b>New Capability:</b> <code>{title}</code>\n"
            f"<b>Trigger:</b> <i>{reason}</i>\n"
            f"<b>Action Taken:</b> <i>{action}</i>\n\n"
            f"<i>Zero-permission self-evolution active in live swarm.</i>"
        )
        await self.send_message(text)

telegram_notifier = TelegramNotifier()
