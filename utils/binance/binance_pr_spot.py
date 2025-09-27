# utils/binance/binance_pr_spot.py
"""
SpotClient: Spot account and order endpoints (signed).
Endpoints mirror Binance API v3 /api/v3/*
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class SpotClient(BinancePrivateBase):
    """Spot account & order operations."""

    async def get_account_info(self) -> Dict[str, Any]:
        """GET /api/v3/account"""
        try:
            await self._require_keys()
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/account", signed=True)
        except Exception as e:
            logger.exception("Error getting spot account info")
            raise BinanceAPIError(f"Error getting spot account info: {e}")

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Return full account info or specific asset balance."""
        try:
            info = await self.get_account_info()
            if asset:
                asset = asset.upper()
                for balance in info.get("balances", []):
                    if balance.get("asset") == asset:
                        return balance
                return {}
            return info
        except Exception as e:
            logger.exception("Error getting spot account balance")
            raise BinanceAPIError(f"Error getting spot account balance: {e}")

    async def place_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        stop_price: Optional[float] = None,
        new_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v3/order"""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
            if price is not None:
                params["price"] = price
            if time_in_force:
                params["timeInForce"] = time_in_force
            if stop_price is not None:
                params["stopPrice"] = stop_price
            if new_client_order_id:
                params["newClientOrderId"] = new_client_order_id
            return await self.circuit_breaker.execute(self.http._request, "POST", "/api/v3/order", params=params, signed=True)
        except Exception as e:
            logger.exception("Error placing spot order")
            raise BinanceAPIError(f"Error placing spot order for {symbol}: {e}")

    async def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """DELETE /api/v3/order"""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper()}
            if order_id:
                params["orderId"] = order_id
            if orig_client_order_id:
                params["origClientOrderId"] = orig_client_order_id
            return await self.circuit_breaker.execute(self.http._request, "DELETE", "/api/v3/order", params=params, signed=True)
        except Exception as e:
            logger.exception("Error canceling spot order")
            raise BinanceAPIError(f"Error canceling spot order for {symbol}: {e}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /api/v3/openOrders"""
        try:
            params = {"symbol": symbol.upper()} if symbol else {}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/openOrders", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting open spot orders")
            raise BinanceAPIError(f"Error getting open spot orders: {e}")

    async def get_order_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """GET /api/v3/allOrders"""
        try:
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/allOrders", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting spot order history")
            raise BinanceAPIError(f"Error getting spot order history for {symbol}: {e}")

    async def get_my_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """GET /api/v3/myTrades"""
        try:
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/myTrades", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting spot trades")
            raise BinanceAPIError(f"Error getting trades for {symbol}: {e}")
