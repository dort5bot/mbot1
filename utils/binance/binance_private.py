"""Binance Private API endpoints (API key gerektiren)."""

from typing import Any, Dict, List, Optional

from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAPIError, BinanceAuthenticationError

class BinancePrivateAPI:
    """Binance Private API işlemleri."""
    
    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker):
        self.http = http_client
        self.circuit_breaker = circuit_breaker

    async def _require_keys(self) -> None:
        """API key kontrolü yap."""
        if not self.http.api_key or not self.http.secret_key:
            raise BinanceAuthenticationError("API key and secret required for this endpoint")

    async def get_account_info(self) -> Dict[str, Any]:
        """Hesap bilgilerini getir."""
        try:
            await self._require_keys()
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/account", signed=True
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting account info: {e}")

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Hesap bakiyesini getir."""
        try:
            await self._require_keys()
            account_info = await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/account", {}, True
            )

            if asset:
                asset = asset.upper()
                for balance in account_info.get('balances', []):
                    if balance.get('asset') == asset:
                        return balance
                return {}

            return account_info

        except Exception as e:
            raise BinanceAPIError(f"Error getting account balance: {e}")

    async def create_listen_key(self) -> str:
        """Private websocket için listenKey oluşturur."""
        try:
            await self._require_keys()
            res = await self.http._request(
                "POST", "/api/v3/userDataStream", signed=False
            )
            return res.get("listenKey")
        except Exception as e:
            raise BinanceAPIError(f"Error creating listenKey: {e}")

    async def place_order(self, symbol: str, side: str, type_: str,
                         quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Yeni order oluştur."""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
            if price:
                params["price"] = price
            return await self.circuit_breaker.execute(
                self.http._request, "POST", "/api/v3/order", params=params, signed=True
            )
        except Exception as e:
            raise BinanceAPIError(f"Error placing order for {symbol}: {e}")

    async def get_funding_rate(self, symbol: str, limit: int = 1) -> List[Dict[str, Any]]:
        """Funding rate bilgilerini getir."""
        try:
            await self._require_keys()
            params = {"symbol": symbol.upper(), "limit": limit}
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/fundingRate", params=params, futures=True
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting funding rate for {symbol}: {e}")