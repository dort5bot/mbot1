"""
utils/binance/binance_private.py
--------------------------------
Binance Private API endpoints (API key gerektiren).
Spot Account & Orders
Futures Account
Margin Trading
Staking
ListenKey (User Data Stream)

🔐 Özellikler:
- Sadece Private Endpoint'ler (Spot + Futures + Margin + Staking)
- Async / await uyumlu
- Singleton yapı
- Logging desteği
- PEP8 uyumlu
- Type hints + docstring
"""

import logging
from typing import Any, Dict, List, Optional

from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAPIError, BinanceAuthenticationError

logger = logging.getLogger(__name__)


class BinancePrivateAPI:
    """Binance Private API işlemleri."""

    _instance: Optional["BinancePrivateAPI"] = None

    def __new__(cls, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> "BinancePrivateAPI":
        """Singleton instance döndürür."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.http = http_client
            cls._instance.circuit_breaker = circuit_breaker
            logger.info("✅ BinancePrivateAPI singleton instance created")
        return cls._instance

    async def _require_keys(self) -> None:
        """API key kontrolü yap."""
        if not self.http.api_key or not self.http.secret_key:
            logger.error("❌ Binance API key/secret bulunamadı")
            raise BinanceAuthenticationError("API key and secret required for this endpoint")

    # ------------------------
    # Spot Account & Orders
    # ------------------------
    async def get_account_info(self) -> Dict[str, Any]:
        """Spot hesap bilgilerini getir."""
        try:
            await self._require_keys()
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/account", signed=True
            )
        except Exception as e:
            logger.exception("🚨 Error getting account info")
            raise BinanceAPIError(f"Error getting account info: {e}")

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Hesap bakiyesi getir (varlık belirtilirse sadece o varlığı döndürür)."""
        try:
            await self._require_keys()
            account_info = await self.http._request("GET", "/api/v3/account", signed=True)
            if asset:
                asset = asset.upper()
                for balance in account_info.get("balances", []):
                    if balance.get("asset") == asset:
                        return balance
                return {}
            return account_info
        except Exception as e:
            logger.exception("🚨 Error getting account balance")
            raise BinanceAPIError(f"Error getting account balance: {e}")

    async def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Yeni spot order oluştur."""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
            if price:
                params["price"] = price
            return await self.http._request("POST", "/api/v3/order", params=params, signed=True)
        except Exception as e:
            logger.exception(f"🚨 Error placing spot order for {symbol}")
            raise BinanceAPIError(f"Error placing spot order for {symbol}: {e}")

    async def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Mevcut spot order iptal et."""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {"symbol": symbol.upper()}
            if order_id:
                params["orderId"] = order_id
            if orig_client_order_id:
                params["origClientOrderId"] = orig_client_order_id
            return await self.http._request("DELETE", "/api/v3/order", params=params, signed=True)
        except Exception as e:
            logger.exception(f"🚨 Error canceling spot order for {symbol}")
            raise BinanceAPIError(f"Error canceling spot order for {symbol}: {e}")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Açık spot order'ları getir."""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper()} if symbol else {}
            return await self.http._request("GET", "/api/v3/openOrders", params=params, signed=True)
        except Exception as e:
            logger.exception("🚨 Error getting open orders")
            raise BinanceAPIError(f"Error getting open orders: {e}")

    async def get_order_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Spot order geçmişini getir."""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.http._request("GET", "/api/v3/allOrders", params=params, signed=True)
        except Exception as e:
            logger.exception(f"🚨 Error getting spot order history for {symbol}")
            raise BinanceAPIError(f"Error getting spot order history for {symbol}: {e}")

    # ------------------------
    # Futures Account
    # ------------------------
    async def get_futures_account_info(self) -> Dict[str, Any]:
        """Futures hesap bilgilerini getir."""
        try:
            await self._require_keys()
            return await self.http._request("GET", "/fapi/v2/account", signed=True, futures=True)
        except Exception as e:
            logger.exception("🚨 Error getting futures account info")
            raise BinanceAPIError(f"Error getting futures account info: {e}")

    async def get_futures_positions(self) -> List[Dict[str, Any]]:
        """Futures açık pozisyonları getir."""
        try:
            await self._require_keys()
            return await self.http._request("GET", "/fapi/v2/positionRisk", signed=True, futures=True)
        except Exception as e:
            logger.exception("🚨 Error getting futures positions")
            raise BinanceAPIError(f"Error getting futures positions: {e}")

    async def place_futures_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """Yeni futures order oluştur."""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {
                "symbol": symbol.upper(),
                "side": side,
                "type": type_,
                "quantity": quantity,
                "reduceOnly": reduce_only,
            }
            if price:
                params["price"] = price
            return await self.http._request("POST", "/fapi/v1/order", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception(f"🚨 Error placing futures order for {symbol}")
            raise BinanceAPIError(f"Error placing futures order for {symbol}: {e}")

    async def get_funding_rate(self, symbol: str, limit: int = 1) -> List[Dict[str, Any]]:
        """Funding rate bilgilerini getir."""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.http._request("GET", "/fapi/v1/fundingRate", params=params, signed=True, futures=True)
        except Exception as e:
            logger.exception(f"🚨 Error getting funding rate for {symbol}")
            raise BinanceAPIError(f"Error getting funding rate for {symbol}: {e}")

    # ------------------------
    # Margin Trading
    # ------------------------
    async def get_margin_account_info(self) -> Dict[str, Any]:
        """Margin hesap bilgilerini getir."""
        try:
            await self._require_keys()
            return await self.http._request("GET", "/sapi/v1/margin/account", signed=True)
        except Exception as e:
            logger.exception("🚨 Error getting margin account info")
            raise BinanceAPIError(f"Error getting margin account info: {e}")

    async def place_margin_order(self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Yeni margin order oluştur."""
        try:
            await self._require_keys()
            params: Dict[str, Any] = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
            if price:
                params["price"] = price
            return await self.http._request("POST", "/sapi/v1/margin/order", params=params, signed=True)
        except Exception as e:
            logger.exception(f"🚨 Error placing margin order for {symbol}")
            raise BinanceAPIError(f"Error placing margin order for {symbol}: {e}")

    async def repay_margin_loan(self, asset: str, amount: float) -> Dict[str, Any]:
        """Margin borcu geri öde."""
        try:
            await self._require_keys()
            params = {"asset": asset.upper(), "amount": amount}
            return await self.http._request("POST", "/sapi/v1/margin/repay", params=params, signed=True)
        except Exception as e:
            logger.exception("🚨 Error repaying margin loan")
            raise BinanceAPIError(f"Error repaying margin loan: {e}")

    # ------------------------
    # Staking
    # ------------------------
    async def get_staking_products(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking ürünlerini getir."""
        try:
            await self._require_keys()
            params = {"product": product}
            return await self.http._request("GET", "/sapi/v1/staking/productList", params=params, signed=True)
        except Exception as e:
            logger.exception("🚨 Error getting staking products")
            raise BinanceAPIError(f"Error getting staking products: {e}")

    async def stake_product(self, product: str, product_id: str, amount: float) -> Dict[str, Any]:
        """Staking işlemi yap."""
        try:
            await self._require_keys()
            params = {"product": product, "productId": product_id, "amount": amount}
            return await self.http._request("POST", "/sapi/v1/staking/purchase", params=params, signed=True)
        except Exception as e:
            logger.exception("🚨 Error staking product")
            raise BinanceAPIError(f"Error staking product: {e}")

    async def get_staking_history(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking geçmişini getir."""
        try:
            await self._require_keys()
            params = {"product": product}
            return await self.http._request("GET", "/sapi/v1/staking/stakingRecord", params=params, signed=True)
        except Exception as e:
            logger.exception("🚨 Error getting staking history")
            raise BinanceAPIError(f"Error getting staking history: {e}")

    # ------------------------
    # User Data Stream (ListenKey)
    # ------------------------
    async def create_listen_key(self) -> str:
        """Spot websocket için listenKey oluştur."""
        try:
            await self._require_keys()
            res = await self.http._request("POST", "/api/v3/userDataStream", signed=False)
            return res.get("listenKey")
        except Exception as e:
            logger.exception("🚨 Error creating listenKey")
            raise BinanceAPIError(f"Error creating listenKey: {e}")

    async def keepalive_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey süresini uzat."""
        try:
            await self._require_keys()
            return await self.http._request("PUT", "/api/v3/userDataStream", params={"listenKey": listen_key}, signed=False)
        except Exception as e:
            logger.exception("🚨 Error keeping alive listenKey")
            raise BinanceAPIError(f"Error keeping alive listenKey: {e}")

    async def delete_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey sil."""
        try:
            await self._require_keys()
            return await self.http._request("DELETE", "/api/v3/userDataStream", params={"listenKey": listen_key}, signed=False)
        except Exception as e:
            logger.exception("🚨 Error deleting listenKey")
            raise BinanceAPIError(f"Error deleting listenKey: {e}")
