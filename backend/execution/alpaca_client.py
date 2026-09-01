import logging
import httpx
from typing import Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger("alphaforge.alpaca")

class AlpacaClient:
    def __init__(self):
        self.api_key = settings.ALPACA_API_KEY
        self.secret_key = settings.ALPACA_SECRET_KEY
        self.base_url = settings.ALPACA_BASE_URL
        self.enabled = bool(self.api_key and self.secret_key)
        
    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key or "",
            "APCA-API-SECRET-KEY": self.secret_key or "",
            "Content-Type": "application/json"
        }

    async def get_account(self) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/v2/account", headers=self._get_headers())
                if res.status_code == 200:
                    return res.json()
                logger.error(f"Alpaca get_account failed: {res.status_code} - {res.text}")
                return None
        except Exception as e:
            logger.error(f"Alpaca API connection error: {e}")
            return None

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = "market", time_in_force: str = "day") -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        try:
            payload = {
                "symbol": symbol.upper(),
                "qty": str(qty),
                "side": side.lower(),
                "type": order_type.lower(),
                "time_in_force": time_in_force.lower()
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{self.base_url}/v2/orders", json=payload, headers=self._get_headers())
                if res.status_code in (200, 201):
                    return res.json()
                logger.error(f"Alpaca order failed: {res.status_code} - {res.text}")
                return None
        except Exception as e:
            logger.error(f"Alpaca order error: {e}")
            return None

alpaca_client = AlpacaClient()
