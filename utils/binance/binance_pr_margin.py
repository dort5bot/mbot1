# utils/binance/binance_pr_margin.py
"""
MarginClient: Margin account & order endpoints (sapi margin).
Margin account endpoints (/sapi/v1/margin/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class MarginClient(BinancePrivateBase):
    """Margin trading operations."""

    async def get_account_info(self) -> Dict[str, Any]:
        """GET /sapi/v1/margin/account"""
        try:
            await self._require_keys()
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/margin/account", signed=True)
        except Exception as e:
            logger.exception("Error getting margin account info")
            raise BinanceAPIError(f"Error getting margin account info: {e}")

    async def create_order(self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """POST /sapi/v1/margin/order"""
        try:
            params: Dict[str, Any] = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
            if price is not None:
                params["price"] = price
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/margin/order", params=params, signed=True)
        except Exception as e:
            logger.exception("Error creating margin order")
            raise BinanceAPIError(f"Error creating margin order for {symbol}: {e}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/margin/openOrders"""
        try:
            params = {"symbol": symbol.upper()} if symbol else {}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/margin/openOrders", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting margin open orders")
            raise BinanceAPIError(f"Error getting margin open orders: {e}")
