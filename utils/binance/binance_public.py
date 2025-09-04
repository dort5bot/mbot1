"""Binance Public API endpoints."""

import pandas as pd
from typing import Any, Dict, List, Optional, Union

from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAPIError

class BinancePublicAPI:
    """Binance Public API işlemleri."""
    
    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker):
        self.http = http_client
        self.circuit_breaker = circuit_breaker

    async def get_server_time(self) -> Dict[str, Any]:
        """Sunucu zamanını getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/time"
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting server time: {e}")

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Exchange bilgilerini getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/exchangeInfo"
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting exchange info: {e}")

    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        """Sembol fiyatını getir."""
        try:
            symbol = symbol.upper().strip()
            if not symbol:
                raise ValueError("Symbol cannot be empty")
                
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/ticker/price", 
                {"symbol": symbol}
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting symbol price for {symbol}: {e}")

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Order book verisini getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/depth",
                {"symbol": symbol.upper(), "limit": limit}
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting order book for {symbol}: {e}")

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Son trade'leri getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/trades",
                {"symbol": symbol.upper(), "limit": limit}
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting recent trades for {symbol}: {e}")

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Union[str, float, int]]]:
        """Kline verisini getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/klines",
                {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting klines for {symbol}: {e}")

    async def get_24h_ticker(self, symbol: str) -> Dict[str, Any]:
        """24 saatlik ticker verisini getir."""
        try:
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/ticker/24hr",
                {"symbol": symbol.upper()}
            )
        except Exception as e:
            raise BinanceAPIError(f"Error getting 24h ticker for {symbol}: {e}")

    async def get_all_symbols(self) -> List[str]:
        """Tüm sembol listesini getir."""
        try:
            data = await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/exchangeInfo"
            )
            return [s["symbol"] for s in data["symbols"]]
        except Exception as e:
            raise BinanceAPIError(f"Error getting all symbols: {e}")