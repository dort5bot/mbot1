"""utils/binance/binance_a.py"""
"""Binance API ana aggregator - tek giriş noktası."""

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable

from .binance_request import BinanceHTTPClient
from .binance_public import BinancePublicAPI
from .binance_private import BinancePrivateAPI
from .binance_websocket import BinanceWebSocketManager
from .binance_circuit_breaker import CircuitBreaker
from .binance_utils import klines_to_dataframe
from .binance_exceptions import BinanceAPIError

class BinanceClient:
    """Binance API'sine erişim için ana istemci sınıfı."""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, config: Any = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.config = config
        
        # HTTP Client
        self.http = BinanceHTTPClient(self.api_key, self.secret_key, self.config)
        
        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=self.config.CIRCUIT_BREAKER_RESET_TIMEOUT,
            name="binance_main"
        )
        
        # API Modülleri
        self.public = BinancePublicAPI(self.http, self.circuit_breaker)
        self.private = BinancePrivateAPI(self.http, self.circuit_breaker)
        
        # WebSocket Manager
        self.ws_manager = BinanceWebSocketManager(self.config)
        
        self.log = logging.getLogger(__name__)
        self.log.info("BinanceClient initialized successfully")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    # Public API methods
    #---------------------
    async def get_server_time(self) -> Dict[str, Any]:
        return await self.public.get_server_time()

    async def get_exchange_info(self) -> Dict[str, Any]:
        return await self.public.get_exchange_info()

    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        return await self.public.get_symbol_price(symbol)

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        return await self.public.get_order_book(symbol, limit)

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Any]]:
        return await self.public.get_klines(symbol, interval, limit)

    async def get_klines_dataframe(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        klines = await self.public.get_klines(symbol, interval, limit)
        return klines_to_dataframe(klines)

    # Private API methods
    #---------------------
    async def get_account_info(self) -> Dict[str, Any]:
        return await self.private.get_account_info()

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        return await self.private.get_account_balance(asset)

    async def place_order(self, symbol: str, side: str, type_: str,
                         quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        return await self.private.place_order(symbol, side, type_, quantity, price)

    # WebSocket methods
    #---------------------
    async def ws_ticker(self, symbol: str, callback: Callable[[Dict[str, Any]], Any]) -> None:
        stream_name = f"{symbol.lower()}@ticker"
        await self.ws_manager.subscribe(stream_name, callback)

    async def ws_kline(self, symbol: str, interval: str, callback: Callable[[Dict[str, Any]], Any]) -> None:
        stream_name = f"{symbol.lower()}@kline_{interval}"
        await self.ws_manager.subscribe(stream_name, callback)

    async def close(self) -> None:
        """Tüm bağlantıları temiz bir şekilde kapat."""
        try:
            await self.ws_manager.close_all()
            await self.http.close()
            self.log.info("BinanceClient closed successfully")
        except Exception as e:
            self.log.error(f"Error closing BinanceClient: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """İstemci metriklerini getir."""
        return {
            "http": self.http.metrics.__dict__,
            "websocket": self.ws_manager.get_metrics().__dict__,
            "circuit_breaker": self.circuit_breaker.get_status()

        }

