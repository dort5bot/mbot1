"""utils/binance/binance_a.py"""
"""Binance API ana aggregator - tek giriş noktası."""

import os
import asyncio
import logging
import pandas as pd
from typing import Any, Dict, List, Optional, Callable, Union

from .binance_request import BinanceHTTPClient
from .binance_public import BinancePublicAPI
from .binance_private import BinancePrivateAPI
from .binance_websocket import BinanceWebSocketManager
from .binance_circuit_breaker import CircuitBreaker, SmartCircuitBreaker
from .binance_utils import klines_to_dataframe
from .binance_exceptions import BinanceAPIError
from .binance_metrics import AdvancedMetrics
from ..config import get_config

class BinanceClient:
    """Binance API'sine erişim için ana istemci sınıfı - TÜM ÖNERİLER EKLENDİ"""
    
    _instance = None  # ✅ Singleton pattern - ÖNERİ EKLENDİ
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern - ÖNERİ EKLENDİ"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, 
                 config: Any = None, http_client: Optional[BinanceHTTPClient] = None,
                 circuit_breaker: Optional[CircuitBreaker] = None):
        """Dependency injection support - ÖNERİ EKLENDİ"""
        
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.api_key = api_key
        self.secret_key = secret_key
        self.config = config or get_config()
                     
        
        # HTTP Client
        self.http = BinanceHTTPClient(self.api_key, self.secret_key, self.config)
        
        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=self.config.CIRCUIT_BREAKER_RESET_TIMEOUT,
            name="binance_main"
        )

        # ✅ Dependency Injection - ÖNERİ EKLENDİ
        self.http = http_client or BinanceHTTPClient(self.api_key, self.secret_key, self.config)
        self.circuit_breaker = circuit_breaker or SmartCircuitBreaker(
            failure_threshold=self.config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=self.config.CIRCUIT_BREAKER_RESET_TIMEOUT,
            name="binance_main"
        )
                     
        # API Modülleri
        self.public = BinancePublicAPI(self.http, self.circuit_breaker)
        self.private = BinancePrivateAPI(self.http, self.circuit_breaker)
        
        # WebSocket Manager
        self.ws_manager = BinanceWebSocketManager(self.config)
        
        #self.log = logging.getLogger(__name__)
        #self.log.info("BinanceClient initialized successfully")


            # ✅ Advanced Metrics - ÖNERİ EKLENDİ
        self.advanced_metrics = AdvancedMetrics()
        
        self.log = logging.getLogger(__name__)
        self._validate_config()  # ✅ Config validation - ÖNERİ EKLENDİ
        self.log.info("BinanceClient initialized successfully")
        self._initialized = True

    def _validate_config(self):
        """Config validation - ÖNERİ EKLENDİ"""
        if not self.config.api_key and self._private_methods_required():
            raise ValueError("Private methods için API key gereklidir")
        
        if self.config.MAX_REQUESTS_PER_SECOND > 10:
            self.log.warning("⚠️ Yüksek request limiti - Rate limit riski")
            
        if len(self.config.SCAN_SYMBOLS) > 50:
            self.log.warning("⚠️ Çok fazla symbol - Performance riski")
            
        return True

    def _private_methods_required(self):
        """Private methods gerekli mi kontrol et - ÖNERİ EKLENDİ"""
        # Burada private method kullanımını kontrol eden logic
        return False

    # ✅ HEALTH CHECK - ÖNERİ EKLENDİ
    async def health_check(self) -> Dict[str, Any]:
        """Sistem sağlık durumunu kontrol et."""
        return {
            "http_connected": self.http.client is not None,
            "ws_connections": len(self.ws_manager.connections),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "config_valid": self._validate_config(),
            "metrics": {
                "total_requests": self.advanced_metrics.total_requests,
                "weight_remaining": self.advanced_metrics.weight_limit_remaining
            }
        }

    # ✅ BATCH OPERATIONS - ÖNERİ EKLENDİ
    async def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Any]:
        """Birden fazla symbol fiyatını al."""
        results = {}
        tasks = []
        
        for symbol in symbols:
            if symbol in self.config.SCAN_SYMBOLS:
                tasks.append(self.get_symbol_price(symbol))
        
        # Concurrent execution
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, price in zip(symbols, prices):
            if not isinstance(price, Exception):
                results[symbol] = price
        
        return results

    # ✅ SYMBOL VALIDATION - ÖNERİ EKLENDİ
    def validate_symbol(self, symbol: str) -> bool:
        """Symbol'ün config'de olup olmadığını kontrol et."""
        return symbol.upper() in [s.upper() for s in self.config.SCAN_SYMBOLS]
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    #---------------------
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
            "circuit_breaker": self.circuit_breaker.get_status(),
            "advanced_metrics": self.advanced_metrics.__dict__  # ✅ EKLENDİ
        }

