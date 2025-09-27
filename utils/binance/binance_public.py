"""utils/binance/binance_public.py
Binance Public API endpoints.

Bu modül, Binance spot ve futures public endpoint'lerini kapsayan asenkron client'lar sağlar.

"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

# Lokal bağımlılıklar
from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAPIError
from .binance_types import Interval, Symbol

logger = logging.getLogger(__name__)

# Parametre validasyonu için sabitler
VALID_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
VALID_DEPTH_LIMITS = {5, 10, 20, 50, 100, 500, 1000, 5000}
VALID_FUTURES_DEPTH_LIMITS = {5, 10, 20, 50, 100, 500, 1000}


class BaseBinanceAPI:
    """Base class for Binance API clients."""
    
    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        self.http: BinanceHTTPClient = http_client
        self.circuit_breaker: CircuitBreaker = circuit_breaker
        logger.info(f"{self.__class__.__name__} initialized.")

    def _validate_period(self, period: str) -> None:
        """Validate period parameter."""
        if period not in VALID_PERIODS:
            raise ValueError(f"Invalid period {period}, must be one of {VALID_PERIODS}")

    def _validate_depth_limit(self, limit: int, futures: bool = False) -> None:
        """Validate depth limit parameter."""
        valid_limits = VALID_FUTURES_DEPTH_LIMITS if futures else VALID_DEPTH_LIMITS
        if limit not in valid_limits:
            raise ValueError(f"Invalid limit {limit}, must be one of {valid_limits}")

    def _validate_symbol(self, symbol: str) -> str:
        """Validate and clean symbol parameter."""
        symbol_clean = symbol.upper().strip()
        if not symbol_clean:
            raise ValueError("Symbol cannot be empty or whitespace.")
        return symbol_clean


class BinanceSpotPublicAPI(BaseBinanceAPI):
    """
    Binance Spot Public API işlemleri.
    """
    
    _instance: Optional["BinanceSpotPublicAPI"] = None
    _initialized: bool = False
    _lock = asyncio.Lock()

    def __new__(cls, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> "BinanceSpotPublicAPI":
        """Singleton implementasyonu."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(http_client, circuit_breaker)
        return cls._instance

    def _initialize(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        """Internal initialization method."""
        if not self._initialized:
            super().__init__(http_client, circuit_breaker)
            self._initialized = True

    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        """Initialization is handled in __new__ and _initialize."""
        pass

    # -------------------------
    # Basic endpoints
    # -------------------------
    async def ping(self) -> Dict[str, Any]:
        """Ping endpoint to check connectivity."""
        try:
            logger.debug("Pinging Binance Spot API.")
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/ping")
        except Exception as e:
            logger.exception("Ping to Binance Spot API failed.")
            raise BinanceAPIError(f"Error pinging Binance Spot API: {e}")

    async def get_server_time(self) -> Dict[str, Any]:
        """Get server time."""
        try:
            logger.debug("Requesting server time.")
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/time")
        except Exception as e:
            logger.exception("Error getting server time.")
            raise BinanceAPIError(f"Error getting server time: {e}")

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information."""
        try:
            logger.debug("Requesting exchange info.")
            return await self.circuit_breaker.execute(self.http._request, "GET", "/api/v3/exchangeInfo")
        except Exception as e:
            logger.exception("Error getting exchange info.")
            raise BinanceAPIError(f"Error getting exchange info: {e}")

    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        """Get current price for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting symbol price for %s", symbol_clean)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/ticker/price", {"symbol": symbol_clean}
            )
        except Exception as e:
            logger.exception("Error getting symbol price for %s", symbol)
            raise BinanceAPIError(f"Error getting symbol price for {symbol}: {e}")

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book (depth) for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            self._validate_depth_limit(limit, futures=False)
            
            logger.debug("Requesting order book for %s limit=%s", symbol_clean, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/depth", {"symbol": symbol_clean, "limit": limit}
            )
        except Exception as e:
            logger.exception("Error getting order book for %s", symbol)
            raise BinanceAPIError(f"Error getting order book for {symbol}: {e}")

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Get recent trades (public)."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting recent trades for %s limit=%s", symbol_clean, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/trades", {"symbol": symbol_clean, "limit": limit}
            )
        except Exception as e:
            logger.exception("Error getting recent trades for %s", symbol)
            raise BinanceAPIError(f"Error getting recent trades for {symbol}: {e}")

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Union[str, float, int]]]:
        """Get kline/candlestick data."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting klines for %s interval=%s limit=%s", symbol_clean, interval, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/klines", 
                {"symbol": symbol_clean, "interval": interval, "limit": limit}
            )
        except Exception as e:
            logger.exception("Error getting klines for %s", symbol)
            raise BinanceAPIError(f"Error getting klines for {symbol}: {e}")

    async def get_all_24h_tickers(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get 24 hour ticker price change statistics."""
        try:
            params: Dict[str, Any] = {}
            if symbol:
                params["symbol"] = self._validate_symbol(symbol)

            logger.debug("Requesting 24h ticker for symbol=%s", symbol or "ALL")
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/ticker/24hr", params
            )
        except Exception as e:
            logger.exception("Error getting 24h ticker for %s", symbol or "ALL")
            raise BinanceAPIError(f"Error getting 24h ticker for {symbol or 'ALL'}: {e}")

    async def get_all_symbols(self, trading_only: bool = True) -> List[str]:
        """
        Get list of all symbols from exchangeInfo.
        
        Args:
            trading_only: If True, only return symbols with status "TRADING"
        """
        try:
            logger.debug("Requesting all symbols via exchangeInfo.")
            data = await self.get_exchange_info()
            
            if trading_only:
                symbols = [s["symbol"] for s in data.get("symbols", []) 
                          if s.get("status") == "TRADING"]
            else:
                symbols = [s["symbol"] for s in data.get("symbols", [])]
                
            logger.debug("Retrieved %d symbols.", len(symbols))
            return symbols
        except Exception as e:
            logger.exception("Error getting all symbols.")
            raise BinanceAPIError(f"Error getting all symbols: {e}")

    # -------------------------
    # Additional spot endpoints
    # -------------------------
    async def get_book_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get best price/qty on the order book for a symbol or all symbols."""
        try:
            params: Dict[str, Any] = {}
            if symbol:
                params["symbol"] = self._validate_symbol(symbol)
                
            logger.debug("Requesting bookTicker for symbol=%s", symbol)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/ticker/bookTicker", params
            )
        except Exception as e:
            logger.exception("Error getting book ticker for %s", symbol)
            raise BinanceAPIError(f"Error getting book ticker for {symbol or 'ALL'}: {e}")

    async def get_avg_price(self, symbol: str) -> Dict[str, Any]:
        """Get current average price for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting avg price for %s", symbol_clean)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/avgPrice", {"symbol": symbol_clean}
            )
        except Exception as e:
            logger.exception("Error getting avg price for %s", symbol)
            raise BinanceAPIError(f"Error getting avg price for {symbol}: {e}")

    async def get_agg_trades(
        self, symbol: str, from_id: Optional[int] = None, start_time: Optional[int] = None,
        end_time: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get compressed/aggregate trades."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            params: Dict[str, Any] = {"symbol": symbol_clean}
            
            if from_id is not None:
                params["fromId"] = from_id
            if start_time is not None:
                params["startTime"] = start_time
            if end_time is not None:
                params["endTime"] = end_time
            if limit is not None:
                params["limit"] = limit
                
            logger.debug("Requesting agg trades for %s params=%s", symbol_clean, params)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/aggTrades", params
            )
        except Exception as e:
            logger.exception("Error getting agg trades for %s", symbol)
            raise BinanceAPIError(f"Error getting agg trades for {symbol}: {e}")

    async def get_ui_klines(
        self, symbol: str, interval: str = "1m", start_time: Optional[int] = None, 
        end_time: Optional[int] = None, limit: Optional[int] = None
    ) -> Any:
        """Get UI klines."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            params: Dict[str, Any] = {"symbol": symbol_clean, "interval": interval}
            
            if start_time is not None:
                params["startTime"] = start_time
            if end_time is not None:
                params["endTime"] = end_time
            if limit is not None:
                params["limit"] = limit
                
            logger.debug("Requesting ui klines for %s params=%s", symbol_clean, params)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/api/v3/uiKlines", params
            )
        except Exception as e:
            logger.exception("Error getting ui klines for %s", symbol)
            raise BinanceAPIError(f"Error getting ui klines for {symbol}: {e}")

    #
    # BinanceSpotPublicAPI class'ına ek
    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        """Get current price for a symbol - alias for get_symbol_price"""
        return await self.get_symbol_price(symbol)

    async def get_advanced_market_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get advanced market metrics by aggregating multiple endpoints."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting advanced market metrics for %s", symbol_clean)
            
            endpoints = [
                self.get_order_book(symbol_clean, limit=100),
                self.get_klines(symbol_clean, "1h", limit=500),
                self.get_all_24h_tickers(symbol_clean)
            ]
            
            results = await asyncio.gather(*endpoints, return_exceptions=True)
            return self._aggregate_market_metrics(symbol_clean, results)
        except Exception as e:
            logger.exception("Error getting advanced market metrics for %s", symbol)
            raise BinanceAPIError(f"Error getting advanced market metrics for {symbol}: {e}")

    def _aggregate_market_metrics(self, symbol: str, results: List[Any]) -> Dict[str, Any]:
        """Aggregate market metrics from multiple endpoint results."""
        aggregated = {
            "symbol": symbol,
            "timestamp": time.time(),
            "order_book": None,
            "klines": None,
            "ticker_24h": None
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Endpoint %d returned exception: %s", i, result)
                continue
                
            if i == 0:  # order book
                aggregated["order_book"] = result
            elif i == 1:  # klines
                aggregated["klines"] = result
            elif i == 2:  # 24h ticker
                aggregated["ticker_24h"] = result
        
        return aggregated





    # -------------------------
    # Convenience methods
    # -------------------------
    async def symbol_exists(self, symbol: str) -> bool:
        """Check if a symbol exists on the exchange."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Checking if symbol exists: %s", symbol_clean)
            info = await self.get_exchange_info()
            
            for s in info.get("symbols", []):
                if s.get("symbol") == symbol_clean:
                    return True
            return False
        except Exception as e:
            logger.exception("Error checking if symbol exists: %s", symbol)
            raise BinanceAPIError(f"Error checking if symbol exists {symbol}: {e}")

    async def get_all_book_tickers(self) -> List[Dict[str, Any]]:
        """Convenience wrapper to fetch all book tickers."""
        logger.debug("Requesting all book tickers (convenience).")
        result = await self.get_book_ticker(None)
        return result if isinstance(result, list) else [result]


class BinanceFuturesPublicAPI(BaseBinanceAPI):
    """
    Binance Futures Public API işlemleri.
    """
    
    _instance: Optional["BinanceFuturesPublicAPI"] = None
    _initialized: bool = False
    _lock = asyncio.Lock()

    def __new__(cls, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> "BinanceFuturesPublicAPI":
        """Singleton implementasyonu."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(http_client, circuit_breaker)
        return cls._instance

    def _initialize(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        """Internal initialization method."""
        if not self._initialized:
            super().__init__(http_client, circuit_breaker)
            self._initialized = True

    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        """Initialization is handled in __new__ and _initialize."""
        pass

    # -------------------------
    # Futures Basic endpoints
    # -------------------------
    async def ping(self) -> Dict[str, Any]:
        """Ping futures endpoint."""
        try:
            logger.debug("Pinging Binance Futures API.")
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/ping", futures=True
            )
        except Exception as e:
            logger.exception("Ping to Binance Futures API failed.")
            raise BinanceAPIError(f"Error pinging Binance Futures API: {e}")

    async def get_futures_exchange_info(self) -> Dict[str, Any]:
        """Get futures exchange information."""
        try:
            logger.debug("Requesting futures exchange info.")
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/exchangeInfo", futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures exchange info.")
            raise BinanceAPIError(f"Error getting futures exchange info: {e}")

    async def get_futures_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get futures order book (depth) for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            self._validate_depth_limit(limit, futures=True)
            
            logger.debug("Requesting futures order book for %s limit=%s", symbol_clean, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/depth", 
                {"symbol": symbol_clean, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures order book for %s", symbol)
            raise BinanceAPIError(f"Error getting futures order book for {symbol}: {e}")

    async def get_futures_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Union[str, float, int]]]:
        """Get futures kline/candlestick data."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting futures klines for %s interval=%s limit=%s", symbol_clean, interval, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/klines", 
                {"symbol": symbol_clean, "interval": interval, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures klines for %s", symbol)
            raise BinanceAPIError(f"Error getting futures klines for {symbol}: {e}")

    async def get_futures_mark_price(self, symbol: str) -> Dict[str, Any]:
        """Get mark price for a futures symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting futures mark price for %s", symbol_clean)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/premiumIndex", 
                {"symbol": symbol_clean}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures mark price for %s", symbol)
            raise BinanceAPIError(f"Error getting futures mark price for {symbol}: {e}")

    async def get_futures_24hr_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get 24 hour ticker price change statistics for futures."""
        try:
            params: Dict[str, Any] = {}
            if symbol:
                params["symbol"] = self._validate_symbol(symbol)
                
            logger.debug("Requesting futures 24hr ticker for symbol=%s", symbol)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/ticker/24hr", params, futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures 24hr ticker for %s", symbol)
            raise BinanceAPIError(f"Error getting futures 24hr ticker for {symbol or 'ALL'}: {e}")
    
    # -------------------------
    # Futures Advanced endpoints
    # -------------------------
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting funding rate for %s", symbol_clean)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/premiumIndex", 
                {"symbol": symbol_clean}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting funding rate for %s", symbol)
            raise BinanceAPIError(f"Error getting funding rate for {symbol}") from e

    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest data for a symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting open interest for %s", symbol_clean)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/openInterest", 
                {"symbol": symbol_clean}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting open interest for %s", symbol)
            raise BinanceAPIError(f"Error getting open interest for {symbol}: {e}")

    async def get_top_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 30) -> List[Dict[str, Any]]:
        """Get top trader long/short ratio."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            self._validate_period(period)
            
            logger.debug("Requesting top long/short ratio for %s period=%s", symbol_clean, period)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/topLongShortPositionRatio", 
                {"symbol": symbol_clean, "period": period, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting top long/short ratio for %s", symbol)
            raise BinanceAPIError(f"Error getting top long/short ratio for {symbol}: {e}")

    async def get_taker_buy_sell_volume(self, symbol: str, period: str = "5m", limit: int = 30) -> List[Dict[str, Any]]:
        """Get taker buy/sell volume ratio."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            self._validate_period(period)
            
            logger.debug("Requesting taker buy/sell volume for %s period=%s", symbol_clean, period)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/takerBuySellVol", 
                {"symbol": symbol_clean, "period": period, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting taker buy/sell volume for %s", symbol)
            raise BinanceAPIError(f"Error getting taker buy/sell volume for {symbol}: {e}")

    async def get_global_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 30) -> List[Dict[str, Any]]:
        """Get global long/short ratio."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            self._validate_period(period)
            
            logger.debug("Requesting global long/short ratio for %s period=%s", symbol_clean, period)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/globalLongShortAccountRatio", 
                {"symbol": symbol_clean, "period": period, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting global long/short ratio for %s", symbol)
            raise BinanceAPIError(f"Error getting global long/short ratio for {symbol}: {e}")

    async def get_futures_funding_rate_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get funding rate history for a futures symbol."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting futures funding rate history for %s limit=%s", symbol_clean, limit)
            return await self.circuit_breaker.execute(
                self.http._request, "GET", "/fapi/v1/fundingRate", 
                {"symbol": symbol_clean, "limit": limit}, futures=True
            )
        except Exception as e:
            logger.exception("Error getting futures funding rate history for %s", symbol)
            raise BinanceAPIError(f"Error getting futures funding rate history for {symbol}: {e}")

    #
    # BinanceFuturesPublicAPI class'ına eklendi:
    #
    async def get_comprehensive_futures_data(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive futures data including funding, OI, and ratios."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting comprehensive futures data for %s", symbol_clean)
            
            endpoints = [
                self.get_futures_mark_price(symbol_clean),
                self.get_open_interest(symbol_clean),
                self.get_funding_rate(symbol_clean),
                self.get_top_long_short_ratio(symbol_clean, "1h", 1),
                self.get_taker_buy_sell_volume(symbol_clean, "1h", 1)
            ]
            
            results = await asyncio.gather(*endpoints, return_exceptions=True)
            return self._aggregate_futures_data(symbol_clean, results)
        except Exception as e:
            logger.exception("Error getting comprehensive futures data for %s", symbol)
            raise BinanceAPIError(f"Error getting comprehensive futures data for {symbol}: {e}")

    def _aggregate_futures_data(self, symbol: str, results: List[Any]) -> Dict[str, Any]:
        """Aggregate comprehensive futures data."""
        aggregated = {
            "symbol": symbol,
            "timestamp": time.time(),
            "mark_price": None,
            "open_interest": None,
            "funding_rate": None,
            "long_short_ratio": None,
            "taker_volume": None
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Futures endpoint %d returned exception: %s", i, result)
                continue
                
            if i == 0:  # mark price
                aggregated["mark_price"] = result
            elif i == 1:  # open interest
                aggregated["open_interest"] = result
            elif i == 2:  # funding rate
                aggregated["funding_rate"] = result
            elif i == 3:  # long/short ratio
                aggregated["long_short_ratio"] = result[0] if result else None
            elif i == 4:  # taker volume
                aggregated["taker_volume"] = result[0] if result else None
        
        return aggregated




    # -------------------------
    # Convenience methods
    # -------------------------
    async def get_all_futures_symbols(self, trading_only: bool = True) -> List[str]:
        """Get list of all futures symbols from exchangeInfo."""
        try:
            logger.debug("Requesting all futures symbols via exchangeInfo.")
            data = await self.get_futures_exchange_info()
            
            if trading_only:
                symbols = [s["symbol"] for s in data.get("symbols", []) 
                          if s.get("status") == "TRADING"]
            else:
                symbols = [s["symbol"] for s in data.get("symbols", [])]
                
            logger.debug("Retrieved %d futures symbols.", len(symbols))
            return symbols
        except Exception as e:
            logger.exception("Error getting all futures symbols.")
            raise BinanceAPIError(f"Error getting all futures symbols: {e}")

    async def futures_symbol_exists(self, symbol: str) -> bool:
        """Check if a symbol exists on the futures exchange."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Checking if futures symbol exists: %s", symbol_clean)
            info = await self.get_futures_exchange_info()
            
            for s in info.get("symbols", []):
                if s.get("symbol") == symbol_clean:
                    return True
            return False
        except Exception as e:
            logger.exception("Error checking if futures symbol exists: %s", symbol)
            raise BinanceAPIError(f"Error checking if futures symbol exists {symbol}: {e}")

    # -------------------------
    # Advanced Market Analysis Methods
    # -------------------------
    async def get_comprehensive_futures_data(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive futures data including funding, OI, and ratios."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting comprehensive futures data for %s", symbol_clean)
            
            endpoints = [
                self.get_futures_mark_price(symbol_clean),
                self.get_open_interest(symbol_clean),
                self.get_funding_rate(symbol_clean),
                self.get_top_long_short_ratio(symbol_clean, "1h", 1),
                self.get_taker_buy_sell_volume(symbol_clean, "1h", 1)
            ]
            
            results = await asyncio.gather(*endpoints, return_exceptions=True)
            return self._aggregate_futures_data(symbol_clean, results)
        except Exception as e:
            logger.exception("Error getting comprehensive futures data for %s", symbol)
            raise BinanceAPIError(f"Error getting comprehensive futures data for {symbol}: {e}")

    def _aggregate_futures_data(self, symbol: str, results: List[Any]) -> Dict[str, Any]:
        """Aggregate comprehensive futures data."""
        aggregated = {
            "symbol": symbol,
            "timestamp": time.time(),
            "mark_price": None,
            "open_interest": None,
            "funding_rate": None,
            "long_short_ratio": None,
            "taker_volume": None
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Futures endpoint %d returned exception: %s", i, result)
                continue
                
            if i == 0:  # mark price
                aggregated["mark_price"] = result
            elif i == 1:  # open interest
                aggregated["open_interest"] = result
            elif i == 2:  # funding rate
                aggregated["funding_rate"] = result
            elif i == 3:  # long/short ratio
                aggregated["long_short_ratio"] = result[0] if result else None
            elif i == 4:  # taker volume
                aggregated["taker_volume"] = result[0] if result else None
        
        return aggregated


# Backward compatibility - mevcut kodu bozmamak için
class BinanceSpotPublicAPICompat(BinanceSpotPublicAPI):
    """
    Backward compatibility class - tüm endpoint'leri tek class'ta sunar.
    """
    
    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        super().__init__(http_client, circuit_breaker)
        self.futures = BinanceFuturesPublicAPI(http_client, circuit_breaker)
        
    # Mevcut advanced methods'ları koru
    async def get_advanced_market_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get advanced market metrics by aggregating multiple endpoints."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting advanced market metrics for %s", symbol_clean)
            
            endpoints = [
                self.get_order_book(symbol_clean, limit=100),
                self.get_klines(symbol_clean, "1h", limit=500),
                self.get_all_24h_tickers(symbol_clean),
                self.futures.get_funding_rate(symbol_clean)
            ]
            
            results = await asyncio.gather(*endpoints, return_exceptions=True)
            return self._aggregate_market_metrics(symbol_clean, results)
        except Exception as e:
            logger.exception("Error getting advanced market metrics for %s", symbol)
            raise BinanceAPIError(f"Error getting advanced market metrics for {symbol}: {e}")

    async def get_multi_timeframe_analysis(self, symbol: str) -> Dict[str, Any]:
        """Multi-timeframe analysis for technical analysis."""
        try:
            symbol_clean = self._validate_symbol(symbol)
            logger.debug("Requesting multi-timeframe analysis for %s", symbol_clean)
            
            timeframes = ["15m", "1h", "4h", "1d", "1w"]
            tasks = [self.get_klines(symbol_clean, tf, limit=200) for tf in timeframes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return self._analyze_multi_timeframe(symbol_clean, results, timeframes)
        except Exception as e:
            logger.exception("Error getting multi-timeframe analysis for %s", symbol)
            raise BinanceAPIError(f"Error getting multi-timeframe analysis for {symbol}: {e}")

    def _aggregate_market_metrics(self, symbol: str, results: List[Any]) -> Dict[str, Any]:
        """Aggregate market metrics from multiple endpoint results."""
        aggregated = {
            "symbol": symbol,
            "timestamp": time.time(),
            "order_book": None,
            "klines": None,
            "ticker_24h": None,
            "funding_rate": None
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Endpoint %d returned exception: %s", i, result)
                continue
                
            if i == 0:  # order book
                aggregated["order_book"] = result
            elif i == 1:  # klines
                aggregated["klines"] = result
            elif i == 2:  # 24h ticker
                aggregated["ticker_24h"] = result
            elif i == 3:  # funding rate
                aggregated["funding_rate"] = result
        
        return aggregated

    def _analyze_multi_timeframe(self, symbol: str, results: List[Any], timeframes: List[str]) -> Dict[str, Any]:
        """Analyze multi-timeframe data for technical signals."""
        analysis = {
            "symbol": symbol,
            "timestamp": time.time(),
            "timeframes": {},
            "summary": {}
        }
        
        for i, (tf, result) in enumerate(zip(timeframes, results)):
            if isinstance(result, Exception):
                analysis["timeframes"][tf] = {"error": str(result)}
                continue
                
            if result and len(result) > 0:
                latest_kline = result[-1]
                analysis["timeframes"][tf] = {
                    "open": float(latest_kline[1]),
                    "high": float(latest_kline[2]),
                    "low": float(latest_kline[3]),
                    "close": float(latest_kline[4]),
                    "volume": float(latest_kline[5]),
                    "count": len(result)
                }
        
        return analysis