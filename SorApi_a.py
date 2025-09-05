"""utils/binance/binance_a.py
Binance API ana aggregator - tek giriş noktası.

Bu modül Binance API'sine erişim için merkezi bir istemci sınıfı sunar.
Alt modülleri birleştirir ve hem public hem private endpointlere
tek sınıf üzerinden erişim imkanı sağlar.

Gerekli bileşenler:
- BinanceHTTPClient (.binance_request)
- CircuitBreaker (.binance_circuit_breaker)
- BinancePublicAPI (.binance_public)
- BinancePrivateAPI (.binance_private)
- BinanceWebSocketManager (.binance_websocket)
- Yardımcı fonksiyonlar/metrikler vb.

Not: Private endpoint wrapper'ları burada eklenmiştir (spot/futures/margin/staking/listenKey).
"""

import os
import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .binance_request import BinanceHTTPClient
from .binance_public import BinancePublicAPI
from .binance_private import BinancePrivateAPI
from .binance_websocket import BinanceWebSocketManager
from .binance_circuit_breaker import CircuitBreaker
from .binance_utils import klines_to_dataframe
from .binance_exceptions import BinanceAPIError
from .binance_metrics import AdvancedMetrics
from config import get_config

LOG = logging.getLogger("binance_a")
LOG.setLevel(logging.INFO)


class BinanceClient:
    """Binance API'sine erişim için ana istemci sınıfı (Singleton)

    Hem public hem private endpoint'lere kolay erişim sağlayan wrapper'lar içerir.
    """

    _instance: Optional["BinanceClient"] = None

    def __new__(cls, *args, **kwargs) -> "BinanceClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        config: Any = None,
        http_client: Optional[BinanceHTTPClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.secret_key = secret_key or os.getenv("BINANCE_API_SECRET")
        self.config = config or get_config()

        # HTTP Client (API key/secret burada set edilebilir)
        self.http = http_client or BinanceHTTPClient(self.api_key, self.secret_key, self.config)

        # Circuit Breaker
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=self.config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=self.config.CIRCUIT_BREAKER_RESET_TIMEOUT,
            name="binance_main",
        )

        # API Modülleri
        self.public = BinancePublicAPI(self.http, self.circuit_breaker)
        self.private = BinancePrivateAPI(self.http, self.circuit_breaker)

        # WebSocket Manager (futures/ws için kullanılabilir)
        self.ws_manager = BinanceWebSocketManager(secret_key=self.secret_key)

        # Ek metrikler
        self.metrics = AdvancedMetrics()

        self._initialized = True
        LOG.info("✅ BinanceClient initialized successfully.")

    # --------------------------
    # PUBLIC WRAPPERS
    # --------------------------
    async def get_server_time(self) -> Dict[str, Any]:
        return await self.public.get_server_time()

    async def ping(self) -> Dict[str, Any]:
        return await self.public.ping()

    async def get_exchange_info(self) -> Dict[str, Any]:
        return await self.public.get_exchange_info()

    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        return await self.public.get_symbol_price(symbol)

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        return await self.public.get_order_book(symbol, limit)

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        return await self.public.get_recent_trades(symbol, limit)

    async def get_klines(
        self, symbol: str, interval: str = "1m", limit: int = 500
    ) -> List[List[Union[str, float, int]]]:
        return await self.public.get_klines(symbol, interval, limit)

    async def get_all_24h_tickers(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return await self.public.get_all_24h_tickers(symbol)

    async def get_all_symbols(self) -> List[str]:
        return await self.public.get_all_symbols()

    async def get_book_ticker(
        self, symbol: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        return await self.public.get_book_ticker(symbol)

    async def get_all_book_tickers(self) -> List[Dict[str, Any]]:
        return await self.public.get_all_book_tickers()

    async def get_avg_price(self, symbol: str) -> Dict[str, Any]:
        return await self.public.get_avg_price(symbol)

    async def get_agg_trades(
        self,
        symbol: str,
        from_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return await self.public.get_agg_trades(symbol, from_id, start_time, end_time, limit)

    async def get_historical_trades(
        self, symbol: str, limit: int = 500, from_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return await self.public.get_historical_trades(symbol, limit, from_id)

    async def get_ui_klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return await self.public.get_ui_klines(symbol, interval, start_time, end_time, limit)

    async def symbol_exists(self, symbol: str) -> bool:
        return await self.public.symbol_exists(symbol)

    # --------------------------
    # PRIVATE WRAPPERS (Spot / Futures / Margin / Staking / ListenKey)
    # --------------------------
    # Spot Account & Orders
    async def get_account_info(self) -> Dict[str, Any]:
        """Spot hesap bilgilerini getir."""
        return await self.private.get_account_info()

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Hesap bakiyesi veya tek varlık bakiyesi getir."""
        return await self.private.get_account_balance(asset)

    async def place_order(
        self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Spot piyasada yeni order oluştur."""
        return await self.private.place_order(symbol, side, type_, quantity, price)

    async def cancel_order(
        self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Spot order iptal et."""
        return await self.private.cancel_order(symbol, order_id, orig_client_order_id)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Açık spot order'ları getir."""
        return await self.private.get_open_orders(symbol)

    async def get_order_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Spot order geçmişini getir."""
        return await self.private.get_order_history(symbol, limit)

    # Futures Account
    async def get_futures_account_info(self) -> Dict[str, Any]:
        """Futures hesap bilgilerini getir (USDT-margined/perpetual)."""
        return await self.private.get_futures_account_info()

    async def get_futures_positions(self) -> List[Dict[str, Any]]:
        """Futures açık pozisyonlarını getir."""
        return await self.private.get_futures_positions()

    async def place_futures_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """Futures piyasada yeni order oluştur."""
        return await self.private.place_futures_order(symbol, side, type_, quantity, price, reduce_only)

    async def get_funding_rate(self, symbol: str, limit: int = 1) -> List[Dict[str, Any]]:
        """Funding rate (kısa dönem geçmişi) bilgilerini getir."""
        return await self.private.get_funding_rate(symbol, limit)

    # Margin Trading
    async def get_margin_account_info(self) -> Dict[str, Any]:
        """Margin hesap bilgilerini getir."""
        return await self.private.get_margin_account_info()

    async def place_margin_order(
        self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Margin piyasada yeni order oluştur."""
        return await self.private.place_margin_order(symbol, side, type_, quantity, price)

    async def repay_margin_loan(self, asset: str, amount: float) -> Dict[str, Any]:
        """Margin borcunu öde."""
        return await self.private.repay_margin_loan(asset, amount)

    # Staking (Savings / Earn benzeri private endpoints)
    async def get_staking_products(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking/earn ürün listesini getir."""
        return await self.private.get_staking_products(product)

    async def stake_product(self, product: str, product_id: str, amount: float) -> Dict[str, Any]:
        """Belirtilen staking ürününe stake yap."""
        return await self.private.stake_product(product, product_id, amount)

    async def get_staking_history(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking geçmiş kayıtlarını getir."""
        return await self.private.get_staking_history(product)

    # User Data Stream (ListenKey)
    async def create_listen_key(self) -> str:
        """Spot için listenKey oluşturur (websocket user data stream)."""
        return await self.private.create_listen_key()

    async def keepalive_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey'i keepalive (uzatma)."""
        return await self.private.keepalive_listen_key(listen_key)

    async def delete_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey siler."""
        return await self.private.delete_listen_key(listen_key)

    # --------------------------
    # Helpers
    # --------------------------
    async def klines_to_df(self, symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
        """Kline verilerini DataFrame'e dönüştürür."""
        klines = await self.get_klines(symbol, interval, limit)
        return klines_to_dataframe(klines)

    # --------------------------
    # Convenience / helper wrappers - future additions
    # --------------------------
    # #future: buraya pozisyon özetleri, PnL hesapları, aggregated metrics vb. eklenebilir.
    # Örnek:
    # async def get_account_overview(self) -> Dict[str, Any]:
    #     """Spot + Futures + Margin üzerinden bir hesap özeti döndürür (farketmelere dikkat)."""
    #     spot = await self.get_account_info()
    #     futures = await self.get_futures_account_info()
    #     margin = await self.get_margin_account_info()
    #     # ...aggregate ve normalize et
    #     return {"spot": spot, "futures": futures, "margin": margin}


🟥
Üstki ana aggregator koda uygun şekilde aşağıdaki kodları düzenle 
Gerekirse açıklama ekle (#future...)
async uyumlu + PEP8 + type hints + docstring + async yapı + singleton + logging olacak biçimde 
Tam kodu ver

🟥
utils/binance/binance_utils.py
utils/binance/binance_types.py
utils/binance/binance_constants.py
utils/binance/binance_exceptions.py
utils/binance/binance_circuit_breaker.py
utils/binance/binance_metrics.py
utils/binance/binance_request.py
utils/binance/binance_websocket.py
utils/binance/init.py
🟨🟨
utils/binance/binance_utils.py

"""Binance yardımcı fonksiyonlar."""

import pandas as pd
from typing import List, Any, Union

def klines_to_dataframe(klines: List[List[Any]]) -> pd.DataFrame:
    """Kline verisini pandas DataFrame'e dönüştür."""
    try:
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    
    except Exception as e:
        # Fallback: boş DataFrame döndür
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

utils/binance/binance_types.py

"""
utils/binance/binance_types.py
Binance API type definitions."""

"""utils/binance/binance_types.py - Type definitions for Binance API."""

from typing import TypedDict, Literal, Union, List, Dict, Any

# 📊 Response Types
class TickerData(TypedDict):
    symbol: str
    price: str
    timestamp: int

class KlineData(TypedDict):
    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int

class OrderBookData(TypedDict):
    bids: List[List[str]]
    asks: List[List[str]]
    lastUpdateId: int

# 🎯 Order Types
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT", "MARKET", "STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"]
OrderStatus = Literal["NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"]

class OrderData(TypedDict):
    symbol: str
    orderId: int
    side: OrderSide
    type: OrderType
    status: OrderStatus
    price: str
    quantity: str
    executedQty: str
    cummulativeQuoteQty: str
    timeInForce: str
    time: int
    updateTime: int

# 📈 Account Types
class BalanceData(TypedDict):
    asset: str
    free: str
    locked: str

class AccountData(TypedDict):
    makerCommission: int
    takerCommission: int
    buyerCommission: int
    sellerCommission: int
    canTrade: bool
    canWithdraw: bool
    canDeposit: bool
    updateTime: int
    accountType: str
    balances: List[BalanceData]

utils/binance/binance_constants.py
"""Binance API sabitleri ve enum tanımları."""

from enum import Enum

class RequestPriority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

# API Endpoint'leri
BASE_URL = "https://api.binance.com"
FAPI_URL = "https://fapi.binance.com"
WS_BASE_URL = "wss://stream.binance.com:9443/ws"

# Public Endpoints
SERVER_TIME = "/api/v3/time"
EXCHANGE_INFO = "/api/v3/exchangeInfo"
TICKER_PRICE = "/api/v3/ticker/price"
TICKER_24HR = "/api/v3/ticker/24hr"
DEPTH = "/api/v3/depth"
TRADES = "/api/v3/trades"
AGG_TRADES = "/api/v3/aggTrades"
KLINES = "/api/v3/klines"
HISTORICAL_TRADES = "/api/v3/historicalTrades"

# Private Endpoints
ACCOUNT_INFO = "/api/v3/account"
ORDER = "/api/v3/order"
USER_DATA_STREAM = "/api/v3/userDataStream"

# Futures Endpoints
FUTURES_POSITION_RISK = "/fapi/v2/positionRisk"
FUTURES_FUNDING_RATE = "/fapi/v1/fundingRate"


utils/binance/binance_exceptions.py

"""Binance API özel exception sınıfları."""

class BinanceAPIError(Exception):
    """Binance API hataları için base exception."""
    pass

class BinanceRequestError(BinanceAPIError):
    """API istek hataları."""
    pass

class BinanceWebSocketError(BinanceAPIError):
    """WebSocket bağlantı hataları."""
    pass

class BinanceAuthenticationError(BinanceAPIError):
    """Kimlik doğrulama hataları."""
    pass

class BinanceRateLimitError(BinanceAPIError):
    """Rate limit hataları."""
    pass

class BinanceCircuitBreakerError(BinanceAPIError):
    """Circuit breaker hataları."""
    pass

utils/binance/binance_circuit_breaker.py


"""
utils/binance/binance_circuit_breaker.py
Circuit breaker pattern implementation for Binance API."""
"""utils/binance/binance_circuit_breaker.py - Circuit breaker pattern."""

import time
import logging
from typing import Any, Callable, Dict, Optional
from .binance_constants import CircuitState
from .binance_exceptions import BinanceCircuitBreakerError

class CircuitBreaker:
    """Devre kesici deseni - TEMEL"""
    # ... mevcut kod ...
    
class SmartCircuitBreaker(CircuitBreaker):
    """Akıllı circuit breaker - ÖNERİ EKLENDİ"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_func = None
        self.metrics = []
        
    async def execute_with_fallback(self, func: Callable, fallback_func: Callable, *args, **kwargs):
        """Fallback fonksiyonu ile execute - ÖNERİ EKLENDİ"""
        try:
            return await self.execute(func, *args, **kwargs)
        except Exception as e:
            self.log.warning(f"Circuit open, fallback kullanılıyor: {e}")
            try:
                return await fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                self.log.error(f"Fallback de başarısız: {fallback_error}")
                raise
    
    def add_metrics(self, success: bool, response_time: float, endpoint: str):
        """Metrik ekle - ÖNERİ EKLENDİ"""
        self.metrics.append({
            "success": success,
            "response_time": response_time,
            "endpoint": endpoint,
            "timestamp": time.time()
        })
        # Son 100 metriği tut
        if len(self.metrics) > 100:
            self.metrics.pop(0)

utils/binance/binance_metrics.py


"""
utils/binance/binance_metrics.py
Binance API metrik sınıfları.
# PEP8 + type hints + docstring + async yapı + singleton + logging + Async Yapı olacak
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import time


@dataclass
class RequestMetrics:
    total_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limited_requests: int = 0
    avg_response_time: float = 0.0
    last_request_time: float = 0.0

    def update_response_time(self, response_time: float) -> None:
        """Yeni bir response süresi ekle ve ortalamayı güncelle."""
        if self.total_requests > 0:
            # Hareketli ortalama
            self.avg_response_time = (
                (self.avg_response_time * (self.total_requests - 1)) + response_time
            ) / self.total_requests
        else:
            self.avg_response_time = response_time
        self.last_request_time = time.time()


@dataclass
class WSMetrics:
    total_connections: int = 0
    failed_connections: int = 0
    messages_received: int = 0
    reconnections: int = 0
    avg_message_rate: float = 0.0
    _message_timestamps: List[float] = field(default_factory=list, repr=False)

    def add_message(self, timestamp: float = None) -> None:
        """Yeni mesaj geldiğinde çağır. Ortalama mesaj hızını günceller."""
        if timestamp is None:
            timestamp = time.time()
        self.messages_received += 1
        self._message_timestamps.append(timestamp)
        # Son 1000 mesajı tut
        if len(self._message_timestamps) > 1000:
            self._message_timestamps.pop(0)
        self.update_message_rate()

    def update_message_rate(self) -> None:
        """Son N mesaj zamanına göre ortalama mesaj hızını güncelle."""
        ts = self._message_timestamps
        if len(ts) > 1:
            interval = max(ts[-1] - ts[0], 1e-6)
            self.avg_message_rate = len(ts) / interval
        else:
            self.avg_message_rate = 0.0


@dataclass
class AdvancedMetrics(RequestMetrics):
    """Gelişmiş metrikler - Weight, endpoint, IP limitleri ve recent errors"""
    weight_usage: int = 0
    weight_limit_remaining: int = 1200
    ip_rate_limit_remaining: int = 1200
    order_rate_limit_remaining: int = 10
    endpoint_usage: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)

    def update_weight_usage(self, endpoint: str, weight: int) -> None:
        """Weight kullanımını güncelle."""
        self.weight_usage += weight
        self.weight_limit_remaining -= weight
        self.endpoint_usage[endpoint] = self.endpoint_usage.get(endpoint, 0) + 1

    def add_error(self, endpoint: str, error: str, status_code: int = None) -> None:
        """Hata ekle ve son 10 hatayı sakla."""
        self.recent_errors.append({
            "endpoint": endpoint,
            "error": error,
            "status_code": status_code,
            "timestamp": time.time()
        })
        if len(self.recent_errors) > 10:
            self.recent_errors.pop(0)
          
utils/binance/binance_request.py
"""Binance HTTP request mekanizması."""

import os
import time
import json
import asyncio
import random
import hmac
import hashlib
import httpx
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlencode
from aiolimiter import AsyncLimiter

from .binance_constants import RequestPriority
from .binance_metrics import RequestMetrics
from .binance_exceptions import BinanceRequestError, BinanceRateLimitError

class BinanceHTTPClient:
    """Binance HTTP API istemcisi için gelişmiş yönetim sınıfı."""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, config: Any = None) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.config = config
        self._last_request = 0
        self.client = None
        self.limiter = AsyncLimiter(config.LIMITER_RATE, config.LIMITER_PERIOD)
        self.log = logging.getLogger(__name__)

        # Concurrency control
        self.semaphores = {
            RequestPriority.HIGH: asyncio.Semaphore(config.CONCURRENCY),
            RequestPriority.NORMAL: asyncio.Semaphore(config.CONCURRENCY),
            RequestPriority.LOW: asyncio.Semaphore(config.CONCURRENCY // 2),
        }

        # Cache system
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._last_cache_cleanup = time.time()

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / config.MAX_REQUESTS_PER_SECOND

        # Metrics
        self.metrics = RequestMetrics()
        self.request_times: List[float] = []

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            base_url=self.config.BASE_URL,
            timeout=self.config.REQUEST_TIMEOUT,
            limits=httpx.Limits(
                max_connections=self.config.MAX_CONNECTIONS,
                max_keepalive_connections=self.config.MAX_KEEPALIVE_CONNECTIONS,
                keepalive_expiry=300
            ),
            http2=True,
            verify=True,
            cert=os.getenv("SSL_CERT_PATH")
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _cleanup_cache(self) -> None:
        """Süresi dolmuş önbellek girdilerini temizle."""
        current_time = time.time()
        if current_time - self._last_cache_cleanup < self.config.CACHE_CLEANUP_INTERVAL:
            return

        expired_keys = [key for key, (ts, _) in self._cache.items()
                        if current_time - ts > self.config.BINANCE_TICKER_TTL]

        for key in expired_keys:
            del self._cache[key]

        # Cache boyutu sınırlaması
        if len(self._cache) > 1000:
            oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[:100]
            for key in oldest_keys:
                del self._cache[key]

        self._last_cache_cleanup = current_time

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False,
        max_retries: Optional[int] = None,
        priority: RequestPriority = RequestPriority.NORMAL,
    ) -> Any:
        """Ana HTTP request methodu."""
        if self.client is None:
            raise BinanceRequestError("HTTP client not initialized")

        try:
            if max_retries is None:
                max_retries = self.config.DEFAULT_RETRY_ATTEMPTS

            # Rate limiting
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)

            self.last_request_time = time.time()
            self.metrics.total_requests += 1

            # Base URL ve headers
            base_url = self.config.FAPI_URL if futures else self.config.BASE_URL
            headers = {}
            params = params or {}

            # Signed request
            if signed:
                if not self.api_key or not self.secret_key:
                    raise BinanceAuthenticationError("API key and secret key required for signed requests")
                signed_params = dict(params)
                signed_params["timestamp"] = int(time.time() * 1000)
                query = urlencode(signed_params)
                signature = hmac.new(self.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
                signed_params["signature"] = signature
                params = signed_params
                headers["X-MBX-APIKEY"] = self.api_key
            elif self.api_key:
                headers["X-MBX-APIKEY"] = self.api_key

            # Cache cleanup
            if time.time() - self._last_cache_cleanup > self.config.CACHE_CLEANUP_INTERVAL:
                self._cleanup_cache()

            # Cache kontrolü
            cache_key = f"{method}:{base_url}{path}:{json.dumps(params, sort_keys=True) if params else ''}"
            ttl = getattr(self.config, "BINANCE_TICKER_TTL", 0)

            if ttl > 0 and cache_key in self._cache:
                ts_cache, data = self._cache[cache_key]
                if time.time() - ts_cache < ttl:
                    self.metrics.cache_hits += 1
                    return data
                else:
                    self.metrics.cache_misses += 1
                    del self._cache[cache_key]

            # Retry loop
            attempt = 0
            last_exception = None
            start_time = time.time()

            while attempt < max_retries:
                attempt += 1
                try:
                    async with self.limiter:
                        async with self.semaphores[priority]:
                            r = await self.client.request(method, path, params=params, headers=headers)

                    if r.status_code == 200:
                        data = r.json()
                        if ttl > 0:
                            self._cache[cache_key] = (time.time(), data)

                        response_time = time.time() - start_time
                        self.request_times.append(response_time)
                        if len(self.request_times) > 100:
                            self.request_times.pop(0)

                        self.metrics.avg_response_time = sum(self.request_times) / len(self.request_times)
                        self.metrics.last_request_time = time.time()
                        return data

                    if r.status_code == 429:
                        self.metrics.rate_limited_requests += 1
                        retry_after = int(r.headers.get("Retry-After", 1))
                        delay = min(2 ** attempt, 60) + retry_after
                        self.log.warning(f"Rate limited for {path}. Sleeping {delay}s")
                        await asyncio.sleep(delay)
                        continue

                    r.raise_for_status()

                except httpx.HTTPStatusError as e:
                    if e.response is not None and e.response.status_code >= 500:
                        delay = min(2 ** attempt, 30)
                        self.log.warning(f"Server error {e.response.status_code} for {path}, retrying")
                        await asyncio.sleep(delay)
                        last_exception = e
                        continue
                    else:
                        self.metrics.failed_requests += 1
                        self.log.error(f"HTTP error for {path}: {e}")
                        raise BinanceRequestError(f"HTTP error: {e}")

                except (httpx.RequestError, asyncio.TimeoutError) as e:
                    last_exception = e
                    self.metrics.failed_requests += 1
                    delay = min(2 ** attempt, 60) + random.uniform(0, 0.3)
                    self.log.error(f"Request error for {path}: {e}, retrying")
                    await asyncio.sleep(delay)

            raise last_exception or BinanceRequestError(f"Max retries ({max_retries}) exceeded for {path}")

        except Exception as e:
            self.log.error(f"Request failed for {method} {path}: {str(e)}")
            raise

    async def close(self) -> None:
        """HTTP client'ı temiz bir şekilde kapat."""
        if self.client:
            try:
                await self.client.aclose()
                self.client = None
                self.log.info("HTTP client closed successfully")
            except Exception as e:
                self.log.error(f"Error closing HTTP client: {e}")
              


utils/binance/binance_websocket.py
"""Binance WebSocket yönetimi."""

import asyncio
import json
import time
import logging
from typing import Any, Dict, List, Callable, Set
from collections import defaultdict
from contextlib import asynccontextmanager
import websockets

from .binance_metrics import WSMetrics
from .binance_exceptions import BinanceWebSocketError

class BinanceWebSocketManager:
    """Binance WebSocket bağlantılarını yöneten sınıf."""
    
    def __init__(self, config: Any):
        self.config = config
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.metrics = WSMetrics()
        self._running = True
        self._message_times: List[float] = []
        self._tasks: Set[asyncio.Task] = set()
        self.log = logging.getLogger(__name__)
        self.log.info("WebSocket Manager initialized")

    @asynccontextmanager
    async def websocket_connection(self, stream_name: str):
        """WebSocket bağlantısı için context manager."""
        try:
            url = f"wss://stream.binance.com:9443/ws/{stream_name}"
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                yield ws
        except Exception as e:
            self.metrics.failed_connections += 1
            self.log.error(f"WebSocket connection failed for {stream_name}: {e}")
            raise BinanceWebSocketError(f"WebSocket connection failed: {e}")

    async def _listen_stream(self, stream_name: str) -> None:
        """WebSocket döngüsü."""
        while self._running:
            try:
                async with self.websocket_connection(stream_name) as ws:
                    self.connections[stream_name] = ws
                    self.log.info(f"WS connected: {stream_name}")
                    self.metrics.total_connections += 1
                    
                    async for msg in ws:
                        self.metrics.messages_received += 1
                        self._message_times.append(time.time())
                        
                        if len(self._message_times) > 100:
                            self._message_times.pop(0)
                        
                        try:
                            data = json.loads(msg)
                        except Exception as e:
                            self.log.error(f"Failed to parse WS message ({stream_name}): {e}")
                            continue
                        
                        for cb in list(self.callbacks.get(stream_name, [])):
                            try:
                                if asyncio.iscoroutinefunction(cb):
                                    await cb(data)
                                else:
                                    cb(data)
                            except Exception as e:
                                self.log.error(f"Callback error for {stream_name}: {e}")
            
            except Exception as e:
                self.metrics.failed_connections += 1
                self.log.warning(f"WS reconnect {stream_name} in {self.config.WS_RECONNECT_DELAY}s: {e}")
                await asyncio.sleep(self.config.WS_RECONNECT_DELAY)

    async def subscribe(self, stream_name: str, callback: Callable[[Any], Any]) -> None:
        """Yeni bir WebSocket stream'ine subscribe ol."""
        if stream_name not in self.connections:
            await self._create_connection(stream_name)
        self.callbacks[stream_name].append(callback)
        self.log.info(f"Subscribed to {stream_name}")

    async def _create_connection(self, stream_name: str) -> None:
        """Yeni WebSocket bağlantısı oluştur."""
        try:
            async with self.websocket_connection(stream_name) as ws:
                self.connections[stream_name] = ws
                self.metrics.total_connections += 1
                
                task = asyncio.create_task(self._listen_stream(stream_name))
                self._tasks.add(task)
                task.add_done_callback(lambda t: self._tasks.discard(t))
                self.log.info(f"WebSocket connection created for {stream_name}")
                
        except Exception as e:
            self.metrics.failed_connections += 1
            self.log.error(f"Failed to create WS connection for {stream_name}: {e}")
            raise BinanceWebSocketError(f"Failed to create connection: {e}")

    async def close_all(self) -> None:
        """Tüm bağlantıları temiz bir şekilde kapat."""
        self._running = False
        for stream_name, ws in self.connections.items():
            try:
                await ws.close()
                self.log.info(f"Closed WebSocket connection for {stream_name}")
            except Exception as e:
                self.log.error(f"Error closing WebSocket for {stream_name}: {e}")
        self.connections.clear()
        self.callbacks.clear()
        
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        self.log.info("All WebSocket connections closed")

    def get_metrics(self) -> WSMetrics:
        """WebSocket metriklerini getir."""
        if self._message_times:
            interval = max(self._message_times[-1] - self._message_times[0], 1)
            self.metrics.avg_message_rate = len(self._message_times) / interval
        return self.metrics

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all()


utils/binance/init
"""utils/binance/__init__.py - Public exports."""

from .binance_a import BinanceClient
from .binance_types import TickerData, KlineData, OrderData, BalanceData, AccountData
from .binance_exceptions import (
    BinanceAPIError, BinanceRequestError, BinanceWebSocketError,
    BinanceAuthenticationError, BinanceRateLimitError, BinanceCircuitBreakerError
)
from .binance_metrics import RequestMetrics, WSMetrics, AdvancedMetrics
from .binance_circuit_breaker import CircuitBreaker, SmartCircuitBreaker

__all__ = [
    'BinanceClient',
    'TickerData', 'KlineData', 'OrderData', 'BalanceData', 'AccountData',
    'BinanceAPIError', 'BinanceRequestError', 'BinanceWebSocketError',
    'BinanceAuthenticationError', 'BinanceRateLimitError', 'BinanceCircuitBreakerError',
    'RequestMetrics', 'WSMetrics', 'AdvancedMetrics',
    'CircuitBreaker', 'SmartCircuitBreaker'
]

