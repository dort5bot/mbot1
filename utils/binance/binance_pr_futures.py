# utils/binance/binance_pr_futures.py
"""
FuturesClient: Binance USDT-M Coin-M futures endpoints (fapi).
Implements account info, positions, order placement/cancel, leverage changes, income history.
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class FuturesClient(BinancePrivateBase):
    """Futures (fapi) operations."""

    async def get_account_info(self) -> Dict[str, Any]:
        """GET /fapi/v2/account"""
        try:
            await self._require_keys()
            return await self.circuit_breaker.execute(self.http._request, "GET", "/fapi/v2/account", signed=True, futures=True)
        except Exception as e:
            logger.exception("Error getting futures account info")
            raise BinanceAPIError(f"Error getting futures account info: {e}")

    async def get_balance(self) -> List[Dict[str, Any]]:
        """Return futures balances (assets list from account info)."""
        try:
            info = await self.get_account_info()
            return info.get("assets", [])
        except Exception as e:
            logger.exception("Error getting futures balance")
            raise BinanceAPIError(f"Error getting futures balance: {e}")

    async def get_positions(self) -> List[Dict[str, Any]]:
        """GET /fapi/v2/positionRisk"""
        try:
            return await self.circuit_breaker.execute(self.http._request, "GET", "/fapi/v2/positionRisk", signed=True, futures=True)
        except Exception as e:
            logger.exception("Error getting futures positions")
            raise BinanceAPIError(f"Error getting futures positions: {e}")

    async def place_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: Optional[str] = None,
        stop_price: Optional[float] = None,
        new_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /fapi/v1/order"""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {
                "symbol": symbol.upper(),
                "side": side,
                "type": type_,
                "quantity": quantity,
                "reduceOnly": "true" if reduce_only else "false",
            }
            if price is not None:
                params["price"] = price
            if time_in_force:
                params["timeInForce"] = time_in_force
            if stop_price is not None:
                params["stopPrice"] = stop_price
            if new_client_order_id:
                params["newClientOrderId"] = new_client_order_id
            return await self.circuit_breaker.execute(self.http._request, "POST", "/fapi/v1/order", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error placing futures order")
            raise BinanceAPIError(f"Error placing futures order for {symbol}: {e}")

    async def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """DELETE /fapi/v1/order"""
        try:
            params = {"symbol": symbol.upper()}
            if order_id:
                params["orderId"] = order_id
            if orig_client_order_id:
                params["origClientOrderId"] = orig_client_order_id
            return await self.circuit_breaker.execute(self.http._request, "DELETE", "/fapi/v1/order", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error canceling futures order")
            raise BinanceAPIError(f"Error canceling futures order for {symbol}: {e}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /fapi/v1/openOrders"""
        try:
            params = {"symbol": symbol.upper()} if symbol else {}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/fapi/v1/openOrders", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error getting futures open orders")
            raise BinanceAPIError(f"Error getting futures open orders: {e}")

    async def get_order_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """GET /fapi/v1/allOrders"""
        try:
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/fapi/v1/allOrders", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error getting futures order history")
            raise BinanceAPIError(f"Error getting futures order history for {symbol}: {e}")

    async def get_income_history(self, symbol: Optional[str] = None, income_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """GET /fapi/v1/income"""
        try:
            params = {"limit": limit}
            if symbol:
                params["symbol"] = symbol.upper()
            if income_type:
                params["incomeType"] = income_type
            return await self.circuit_breaker.execute(self.http._request, "GET", "/fapi/v1/income", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error getting futures income history")
            raise BinanceAPIError(f"Error getting futures income history: {e}")

    async def change_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """POST /fapi/v1/leverage"""
        try:
            params = {"symbol": symbol.upper(), "leverage": leverage}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/fapi/v1/leverage", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error changing futures leverage")
            raise BinanceAPIError(f"Error changing leverage for {symbol}: {e}")

    async def change_margin_type(self, symbol: str, margin_type: str) -> Dict[str, Any]:
        """POST /fapi/v1/marginType"""
        try:
            params = {"symbol": symbol.upper(), "marginType": margin_type.upper()}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/fapi/v1/marginType", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error changing futures margin type")
            raise BinanceAPIError(f"Error changing margin type for {symbol}: {e}")

    async def set_position_mode(self, dual_side_position: bool) -> Dict[str, Any]:
        """POST /fapi/v1/positionSide/dual"""
        try:
            params = {"dualSidePosition": "true" if dual_side_position else "false"}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/fapi/v1/positionSide/dual", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception("Error setting futures position mode")
            raise BinanceAPIError("Error setting futures position mode")
