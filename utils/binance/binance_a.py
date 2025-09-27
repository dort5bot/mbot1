# utils/binance/binance_a.py
"""
v4
Binance API Aggregator
--------------------------------------------------
Tüm Binance API endpoint'lerine tek bir noktadan erişim sağlar.

🔧 ÖZELLİKLER:
- Gelişmiş caching, retry, rate limiting mekanizmaları
- Singleton pattern + context manager desteği
- Tüm yeni private client'ler entegre (spot, futures, margin, staking, savings, mining, subaccount, userstream, asset)
- Kapsamlı hata yönetimi ve monitoring
- Parallel data fetching ve advanced analytics
# Öneri: Global instance'ı kaldırın, class-based kullanın

🔒 GÜVENLİK POLİTİKASI:
- API key'ler asla tam olarak loglanmaz
- Secret key'ler hiçbir zaman loglanmaz
- Sensitive data'lar sadece debug modunda kısmen gösterilir
- Production'da debug logging kapalı olmalıdır

"""

import logging
import asyncio
import json
from typing import Optional, AsyncContextManager, Dict, Any, List, Set, Union, Callable
from contextlib import asynccontextmanager
from pydantic import BaseSettings, validator
from datetime import datetime
from functools import wraps
import time

# Relative imports for same package
from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAPIError, BinanceCircuitBreakerError

# Public API'ler
from .binance_public import BinanceSpotPublicAPI, BinanceFuturesPublicAPI

# Private Client'ler
from .binance_pr_spot import SpotClient
from .binance_pr_futures import FuturesClient
from .binance_pr_margin import MarginClient
from .binance_pr_staking import StakingClient
from .binance_pr_savings import SavingsClient
from .binance_pr_mining import MiningClient
from .binance_pr_subaccount import SubAccountClient
from .binance_pr_userstream import UserStreamClient
from .binance_pr_asset import AssetClient

logger = logging.getLogger(__name__)


# -----------------------------
# Utility Classes (Cache, Retry)
# -----------------------------

def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator for API calls with exponential backoff and jitter."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            retries = 0
            last_exception = None
            
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    last_exception = e
                    
                    if retries >= max_retries:
                        logger.error(f"❌ {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    wait_time = delay * (backoff ** (retries - 1)) * (0.5 + 0.5 * time.time() % 1)
                    logger.warning(
                        f"⚠️ {func.__name__} failed (attempt {retries}/{max_retries}), "
                        f"retrying in {wait_time:.2f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
            
            raise last_exception if last_exception else Exception("Unknown error in retry mechanism")
        return wrapper
    return decorator


def structured_log(level: str, message: str, **kwargs):
    """JSON formatında structured logging"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "module": __name__,
        **kwargs
    }
    
    if level == "ERROR":
        logger.error(json.dumps(log_entry))
    elif level == "WARNING":
        logger.warning(json.dumps(log_entry))
    else:
        logger.info(json.dumps(log_entry))

def monitor_performance(func):
    """Performance monitoring decorator"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            duration = time.time() - start_time
            
            # Slow request logging
            if duration > 2.0:  # 2 seconds threshold
                logger.warning(f"🐌 Slow {func.__name__}: {duration:.3f}s")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


async def rotate_api_key(self, new_key: str, new_secret: str) -> None:
    """Güvenli API key rotation"""
    # Validate new keys first
    if len(new_key) < 20:
        raise ValueError("Invalid API key format")
    
    # Update HTTP client
    await self.http.update_credentials(new_key, new_secret)
    
    # Update config
    self._config['api_key'] = new_key
    self._config['api_secret'] = new_secret
    
    logger.info("✅ API keys rotated successfully")


def _scrub_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Loglardan sensitive data temizleme"""
    sensitive_fields = {'apiKey', 'secretKey', 'signature', 'timestamp'}
    scrubbed = data.copy()
    
    for field in sensitive_fields:
        if field in scrubbed:
            scrubbed[field] = '***'
    
    return scrubbed


class Cache:
    """Thread-safe caching mechanism with TTL and automatic cleanup."""
    
    def __init__(self, ttl: int = 60, max_size: Optional[int] = None):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get data from cache with TTL validation."""
        async with self._lock:
            entry = self._cache.get(key)
            current_time = time.time()
            
            if entry:
                if current_time - entry['timestamp'] < self._ttl:
                    self._hits += 1
                    return entry['data']
                else:
                    del self._cache[key]
                    self._evictions += 1
                    logger.debug(f"♻️ Cache entry expired: {key}")
            
            self._misses += 1
            return None
    
    async def set(self, key: str, data: Any) -> None:
        """Store data in cache with timestamp."""
        async with self._lock:
            if self._max_size and len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._evictions += 1
                logger.debug(f"♻️ Cache evicted oldest entry: {oldest_key}")
            
            self._cache[key] = {
                'data': data,
                'timestamp': time.time()
            }
            logger.debug(f"💾 Cache stored: {key}")
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            logger.info("🧹 Cache cleared completely")
    
    async def cleanup(self) -> None:
        """Remove expired entries from cache."""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time - entry['timestamp'] >= self._ttl
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self._evictions += 1
            
            if expired_keys:
                logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            'size': len(self._cache),
            'hits': self._hits,
            'misses': self._misses,
            'evictions': self._evictions,
            'hit_ratio': self._hits / total if total > 0 else 0
        }


class BinanceConfig(BaseSettings):
    """Type-safe configuration using pydantic"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://api.binance.com"
    fapi_url: str = "https://fapi.binance.com"
    requests_per_second: int = 10
    cache_ttl: int = 30
    max_cache_size: int = 1000
    failure_threshold: int = 5
    reset_timeout: int = 60
    testnet: bool = False
    
    @validator('requests_per_second')
    def validate_rate_limit(cls, v):
        if v > 50:
            raise ValueError('Rate limit exceeds Binance TOS')
        return v
    
    class Config:
        env_prefix = 'BINANCE_'



class OptimizedCache(Cache):
    """Memory optimized cache with size limits"""
    def __init__(self, ttl: int = 60, max_size: Optional[int] = None, max_memory_mb: int = 100):
        super().__init__(ttl, max_size)
        self._max_memory_mb = max_memory_mb
        self._current_memory = 0
        
    async def set(self, key: str, data: Any) -> None:
        # Estimate memory usage
        data_size = self._estimate_size(data)
        
        async with self._lock:
            # Check memory limits
            if self._current_memory + data_size > self._max_memory_mb * 1024 * 1024:
                await self._evict_oldest()
            
            await super().set(key, data)
            self._current_memory += data_size
    
    def _estimate_size(self, obj: Any) -> int:
        """Basit memory estimation"""
        return len(str(obj).encode('utf-8'))



# -----------------------------
# Public Aggregator (Yeni Yapı)
# -----------------------------

class BinancePublic:
    """Public API aggregator (no API key required)."""
    
    def __init__(self, http: BinanceHTTPClient, breaker: CircuitBreaker) -> None:
        self.spot = BinanceSpotPublicAPI(http, breaker)
        self.futures = BinanceFuturesPublicAPI(http, breaker)


# -----------------------------
# Private Aggregator (Yeni Yapı)
# -----------------------------

class BinancePrivate:
    """Private API aggregator (API key + secret required)."""
    
    def __init__(self, http: BinanceHTTPClient, breaker: CircuitBreaker) -> None:
        self.spot = SpotClient(http, breaker)
        self.futures = FuturesClient(http, breaker)
        self.margin = MarginClient(http, breaker)
        self.staking = StakingClient(http, breaker)
        self.savings = SavingsClient(http, breaker)
        self.mining = MiningClient(http, breaker)
        self.subaccount = SubAccountClient(http, breaker)
        self.userstream = UserStreamClient(http, breaker)
        self.asset = AssetClient(http, breaker)


# -----------------------------
# Main Aggregator Class
# -----------------------------
# class-based kullanılacak
class BinanceAPI(AsyncContextManager):
    """Geliştirilmiş Binance API aggregator - Tüm yeni client'ler entegre"""
    _instance: Optional["BinanceAPI"] = None
    _initialization_lock = asyncio.Lock()
    

        
    # Global fonksiyonları class method'larına dönüştürme
    @classmethod
    async def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> "BinanceAPI":
        """Get or create singleton instance."""
        if cls._instance is None:
            if config:
                cls._instance = await cls.create_from_config(config)
            else:
                raise RuntimeError("Config required for first initialization")
        return cls._instance
        

    
    @classmethod
    async def create_from_config(cls, config: Dict[str, Any]) -> "BinanceAPI":
        """Config'den BinanceAPI instance'ı oluşturur."""
        async with cls._initialization_lock:
            if cls._instance is None:
                try:
                    http_client = BinanceHTTPClient(
                        api_key=config.get("api_key"),
                        secret_key=config.get("api_secret"),
                        base_url=config.get("base_url"),
                        fapi_url=config.get("fapi_url"),
                        config={
                            "requests_per_second": config.get("requests_per_second", 10)
                        }
                    )
                    
                    circuit_breaker = CircuitBreaker(
                        failure_threshold=config.get("failure_threshold", 5),
                        reset_timeout=config.get("reset_timeout", 60)
                    )
                    
                    cls._instance = cls.__new__(cls)
                    await cls._instance._initialize(
                        http_client=http_client,
                        circuit_breaker=circuit_breaker,
                        cache_ttl=config.get("cache_ttl", 30),
                        cache_max_size=config.get("max_cache_size", 1000),
                        config=config
                    )
                    
                    # ✅ GÜVENLİ LOGGING - BURAYA EKLENECEK
                    logger.info("✅ BinanceAPI config-based instance created successfully")
                    api_key = config.get("api_key")
                    if api_key:
                        logger.info(f"✅ Using API key: {api_key[:8]}...")
                    if config.get("testnet"):
                        logger.info("🔧 Testnet mode enabled")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create BinanceAPI from config: {e}")
                    raise RuntimeError(f"BinanceAPI config initialization failed: {e}")
            
            return cls._instance
    
    @classmethod
    async def create(cls, 
                    http_client: BinanceHTTPClient, 
                    circuit_breaker: CircuitBreaker, 
                    cache_ttl: int = 30,
                    cache_max_size: Optional[int] = 1000,
                    config: Optional[Dict[str, Any]] = None) -> "BinanceAPI":
        """Geliştirilmiş create methodu."""
        async with cls._initialization_lock:
            if cls._instance is None:
                try:
                    cls._instance = cls.__new__(cls)
                    await cls._instance._initialize(
                        http_client, circuit_breaker, cache_ttl, cache_max_size, config
                    )
                    logger.info("✅ BinanceAPI singleton instance created successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to create BinanceAPI instance: {e}")
                    raise RuntimeError(f"BinanceAPI initialization failed: {e}")
            
            return cls._instance
 

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Daha güvenli ve optimize cache key generation"""
        import hashlib
        import json
        
        # Parametreleri normalize et
        params = {
            'args': [str(arg) for arg in args if arg is not None],
            'kwargs': {k: str(v) for k, v in kwargs.items() 
                      if v is not None and not k.startswith('_')}
        }
        
        # JSON serialization ile daha güvenli key
        params_str = json.dumps(params, sort_keys=True, separators=(',', ':'))
        time_window = int(time.time()) // max(getattr(self._cache, '_ttl', 60), 1)
        
        # Hash kullanarak key uzunluğunu kontrol et
        hash_digest = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        
        return f"bnc_{prefix}_{hash_digest}_w{time_window}"

    def _normalize_param(self, param: Any) -> str:
        """Parametreleri string'e çevir ve normalize et"""
        if isinstance(param, bool):
            return "true" if param else "false"
        elif isinstance(param, (int, float)):
            return str(param)
        elif isinstance(param, str):
            return param.upper().replace(" ", "_").replace("/", "_")
        else:
            return str(param).replace(" ", "_")
 
 
    async def _initialize(self, 
                     http_client: BinanceHTTPClient, 
                     circuit_breaker: CircuitBreaker,
                     cache_ttl: int,
                     cache_max_size: Optional[int],
                     config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with new public/private structure."""
        
        # Validate config before anything else
        await self._validate_config(config or {})
        
        # Rest of initialization
        self.http = http_client
        self.circuit_breaker = circuit_breaker
        self._cache = Cache(ttl=cache_ttl, max_size=cache_max_size)
        self._config = config or {}
        
        # Yeni yapı: Public ve Private aggregator'lar
        self.public = BinancePublic(http_client, circuit_breaker)
        self.private = BinancePrivate(http_client, circuit_breaker)
        
        # Rate limiting configuration
        self._last_request_time = 0
        self._min_request_interval = 1.0 / self._config.get("requests_per_second", 10)
        self._request_count = 0
        self._total_request_time = 0.0
        
        # ✅ GÜVENLİ LOGGING - BURAYA EKLENECEK
        logger.info("✅ BinanceAPI initialized with new public/private structure")
        api_key = self._config.get("api_key")
        if api_key:
            logger.info(f"✅ API key configured: {api_key[:8]}...")
        if self._config.get("testnet"):
            logger.info("🔧 Testnet mode active")
    
    
    # Config Validation
    async def _validate_config(self, config: Dict[str, Any]) -> None:
        """Comprehensive configuration validation."""
        
        # Required URLs
        required_urls = ['base_url', 'fapi_url']
        for url_key in required_urls:
            url = config.get(url_key)
            if not url:
                raise ValueError(f"Missing required URL: {url_key}")
            if not url.startswith(('https://', 'http://')):
                raise ValueError(f"Invalid URL format for {url_key}: {url}")
        
        # Rate limiting (Binance TOS compliance)
        max_requests = 50
        requested_requests = config.get('requests_per_second', 10)
        if requested_requests > max_requests:
            raise ValueError(f"Rate limit exceeds Binance TOS: {requested_requests} > {max_requests}")
        if requested_requests <= 0:
            raise ValueError(f"Rate limit must be positive: {requested_requests}")
        
        # Cache settings
        cache_ttl = config.get('cache_ttl', 30)
        if cache_ttl <= 0:
            raise ValueError(f"Cache TTL must be positive: {cache_ttl}")
        
        cache_max_size = config.get('max_cache_size', 1000)
        if cache_max_size and cache_max_size <= 0:
            raise ValueError(f"Cache max size must be positive: {cache_max_size}")
        
        # Circuit breaker settings
        failure_threshold = config.get('failure_threshold', 5)
        if failure_threshold <= 0:
            raise ValueError(f"Failure threshold must be positive: {failure_threshold}")
        
        reset_timeout = config.get('reset_timeout', 60)
        if reset_timeout <= 0:
            raise ValueError(f"Reset timeout must be positive: {reset_timeout}")
        
        # API key format validation (basic)
        api_key = config.get('api_key')
        if api_key and len(api_key) < 20:  # Binance API key minimum length
            raise ValueError(f"Invalid API key format: too short")
        
        logger.info("✅ Configuration validation completed successfully")
            
        
    #
    # Rate Limiting
    async def _rate_limit(self) -> None:
        """Geliştirilmiş rate limiting with burst support"""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        # Burst support için minimum interval
        min_interval = max(self._min_request_interval, 0.01)  # 10ms minimum
        
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            # Precision sleep için asyncio.sleep yerine loop time
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()

    #h
    async def _handle_request_error(self, error: Exception, cache_key: str, 
                                  func_name: str, metrics: Dict[str, Any]) -> None:
        """Merkezi error handling"""
        error_type = type(error).__name__
        
        if isinstance(error, BinanceCircuitBreakerError):
            logger.warning(f"🚫 Circuit breaker blocked {func_name}")
            return
        
        elif isinstance(error, asyncio.TimeoutError):
            logger.error(f"⏰ Timeout in {func_name} after {metrics['response_time']:.3f}s")
            await self.circuit_breaker.record_failure(error)
            
        elif isinstance(error, BinanceAPIError):
            # Binance-specific errors
            if hasattr(error, 'code'):
                if error.code in [-1003, -1006, -1007]:  # Rate limit errors
                    logger.warning(f"⚠️ Rate limit hit in {func_name}: {error}")
                    await asyncio.sleep(1)  # Backoff
            logger.error(f"🔴 API Error in {func_name}: {error}")
            await self.circuit_breaker.record_failure(error)
            
        else:
            logger.error(f"❌ Unexpected error in {func_name}: {error}")
            await self.circuit_breaker.record_failure(error)


    @retry(max_retries=3, delay=1.0, backoff=2.0)
    async def _cached_request(self, cache_key: str, func: Callable, *args, **kwargs) -> Any:
        """Geliştirilmiş metriklerle request handling"""
        start_time = time.time()
        metrics = {
            'cache_hit': False,
            'retry_count': 0,
            'response_time': 0.0
        }
        
        try:
            # Cache check with metrics
            if self._cache:
                cached_data = await self._cache.get(cache_key)
                if cached_data is not None:
                    metrics['cache_hit'] = True
                    logger.debug(f"✅ Cache hit for {cache_key}")
                    return cached_data
            
            # Rate limiting
            await self._rate_limit()
            
            # Circuit breaker state check
            if self.circuit_breaker.is_open():
                logger.warning(f"🚫 Circuit breaker open for {func.__name__}")
                raise BinanceCircuitBreakerError("Circuit breaker is open")
            
            # Actual API call
            data = await func(*args, **kwargs)
            
            # Cache successful responses
            if self._cache and data is not None:
                asyncio.create_task(self._cache.set(cache_key, data))  # Async cache set
            
            await self.circuit_breaker.record_success()
            
            # Update metrics
            metrics['response_time'] = time.time() - start_time
            self._request_count += 1
            self._total_request_time += metrics['response_time']
            
            logger.debug(f"✅ {func.__name__} completed in {metrics['response_time']:.3f}s")
            return data
            
        except Exception as e:
            metrics['response_time'] = time.time() - start_time
            await self._handle_request_error(e, cache_key, func.__name__, metrics)
            raise
            
    
    
    ##
    async def close(self) -> None:
        """Cleanup resources and close connections."""
        cleanup_tasks = []
        
        if hasattr(self, 'http'):
            cleanup_tasks.append(self.http.close())
        
        if hasattr(self, '_cache'):
            cleanup_tasks.append(self._cache.cleanup())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("✅ BinanceAPI resources cleaned up successfully")
    
    async def __aenter__(self) -> "BinanceAPI":
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with proper cleanup."""
        await self.close()
    
    # -------------------------------------------------------------------------
    # PUBLIC API METHODS WITH CACHING (Backward Compatibility)
    # -------------------------------------------------------------------------
    
    async def get_all_24h_tickers(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        cache_key = self._generate_cache_key("tickers_24h", symbol or "all")
        try:
            if symbol:
                return await self._cached_request(cache_key, self.public.spot.get_all_24h_tickers, symbol)
            else:
                return await self._cached_request(cache_key, self.public.spot.get_all_24h_tickers)
        except Exception as e:
            logger.error(f"❌ Failed to get 24h tickers: {e}")
            return []
    
    
    async def get_exchange_info(self, futures: bool = False) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("exchange_info", "futures" if futures else "spot")
        try:
            if futures:
                return await self._cached_request(cache_key, self.public.futures.get_futures_exchange_info)
            else:
                return await self._cached_request(cache_key, self.public.spot.get_exchange_info)
        except Exception as e:
            logger.error(f"❌ Failed to get exchange info: {e}")
            return {}


    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500, futures: bool = False) -> List[List[Any]]:
        cache_key = self._generate_cache_key("klines", symbol, interval, limit, futures=futures)
        if futures:
            return await self._cached_request(cache_key, self.public.futures.get_futures_klines, symbol, interval, limit)
        else:
            return await self._cached_request(cache_key, self.public.spot.get_klines, symbol, interval, limit)
    
    
    async def get_server_time(self) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("server_time")
        return await self._cached_request(cache_key, self.public.spot.get_server_time)

    async def get_order_book(self, symbol: str, limit: int = 100, futures: bool = False) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("orderbook", symbol, limit, futures=futures)
        if futures:
            return await self._cached_request(cache_key, self.public.futures.get_futures_order_book, symbol, limit)
        else:
            return await self._cached_request(cache_key, self.public.spot.get_order_book, symbol, limit)
        
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("funding_rate", symbol)
        return await self._cached_request(cache_key, self.public.futures.get_funding_rate, symbol)

    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("open_interest", symbol)
        return await self._cached_request(cache_key, self.public.futures.get_open_interest, symbol)

    async def get_futures_mark_price(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("mark_price", symbol)
        return await self._cached_request(cache_key, self.public.futures.get_futures_mark_price, symbol)

    async def get_avg_price(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("avg_price", symbol)
        return await self._cached_request(cache_key, self.public.spot.get_avg_price, symbol)

    async def get_advanced_market_metrics(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("advanced_metrics", symbol)
        return await self._cached_request(cache_key, self.public.spot.get_advanced_market_metrics, symbol)

    async def get_comprehensive_futures_data(self, symbol: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("futures_data", symbol)
        return await self._cached_request(cache_key, self.public.futures.get_comprehensive_futures_data, symbol)
        
    # 
    async def get_book_ticker(self, symbol: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if symbol:
            cache_key = self._generate_cache_key("book_ticker", symbol)
            return await self._cached_request(cache_key, self.public.spot.get_book_ticker, symbol)
        else:
            cache_key = self._generate_cache_key("book_ticker", "all")
            return await self._cached_request(cache_key, self.public.spot.get_book_ticker)
    
   
   
    async def get_balance(self, asset: Optional[str] = None, futures: bool = False) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        try:
            if futures:
                balances = await self.private.futures.get_balance() or []
                if asset:
                    for balance in balances:
                        if balance.get('asset') == asset.upper():
                            return balance
                    return {}
                return balances
            else:
                return await self.private.spot.get_account_balance(asset)
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return {} if asset else []
   
       
    async def symbol_exists(self, symbol: str, futures: bool = False) -> bool:
        """Check if symbol exists."""
        if futures:
            return await self.public.futures.futures_symbol_exists(symbol)
        else:
            return await self.public.spot.symbol_exists(symbol)
    
    async def get_all_symbols(self, futures: bool = False) -> List[str]:
        """Get all symbols."""
        if futures:
            return await self.public.futures.get_all_futures_symbols()
        else:
            return await self.public.spot.get_all_symbols()
    
    # -------------------------------------------------------------------------
    # PRIVATE API METHODS (Backward Compatibility - Yeni yapıya delegate)
    # -------------------------------------------------------------------------
    
    async def get_open_orders(self, symbol: Optional[str] = None, futures: bool = False) -> List[Dict[str, Any]]:
        """Get open orders."""
        if futures:
            return await self.private.futures.get_open_orders(symbol)
        else:
            return await self.private.spot.get_open_orders(symbol)
    
    async def place_order(self, symbol: str, side: str, type_: str, quantity: float, 
                         price: Optional[float] = None, futures: bool = False, **kwargs) -> Dict[str, Any]:
        """Place order."""
        if futures:
            return await self.private.futures.place_order(symbol, side, type_, quantity, price, **kwargs)
        else:
            return await self.private.spot.place_order(symbol, side, type_, quantity, price, **kwargs)
    
    async def get_account_info(self, futures: bool = False) -> Dict[str, Any]:
        """Get account info."""
        if futures:
            return await self.private.futures.get_account_info()
        else:
            return await self.private.spot.get_account_info()
    
 
    # -------------------------------------------------------------------------
    # ENHANCED MARKET DATA METHODS
    # -------------------------------------------------------------------------
    
    async def get_top_gainers_with_volume(self, 
                                         limit: int = 20, 
                                         min_volume_usdt: float = 1_000_000) -> List[Dict[str, Any]]:
        """Get top gaining coins with volume filter."""
        try:
            tickers = await self.get_all_24h_tickers()
            
            filtered = [
                t for t in tickers 
                if float(t.get('quoteVolume', 0)) >= min_volume_usdt 
                and float(t.get('priceChangePercent', 0)) > 0
            ]
            
            filtered.sort(key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get top gainers with volume filter: {e}")
            return []
    
    async def get_top_losers_with_volume(self, 
                                        limit: int = 20, 
                                        min_volume_usdt: float = 1_000_000) -> List[Dict[str, Any]]:
        """Get top losing coins with volume filter."""
        try:
            tickers = await self.get_all_24h_tickers()
            
            filtered = [
                t for t in tickers 
                if float(t.get('quoteVolume', 0)) >= min_volume_usdt 
                and float(t.get('priceChangePercent', 0)) < 0
            ]
            
            filtered.sort(key=lambda x: float(x.get('priceChangePercent', 0)))
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get top losers with volume filter: {e}")
            return []
    
    async def get_volume_leaders(self, limit: int = 20, min_volume_usdt: float = 1_000_000) -> List[Dict[str, Any]]:
        """Get coins with highest trading volume."""
        try:
            tickers = await self.get_all_24h_tickers()
            
            filtered = [
                t for t in tickers 
                if float(t.get('quoteVolume', 0)) >= min_volume_usdt
            ]
            
            filtered.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get volume leaders: {e}")
            return []
    
    # -------------------------------------------------------------------------
    # ADVANCED AGGREGATION METHODS
    # -------------------------------------------------------------------------
    
    async def get_unified_account_summary(self) -> Dict[str, Any]:
        """Get unified account summary combining spot and futures."""
        try:
            spot_account, futures_account = await asyncio.gather(
                self.private.spot.get_account_info(),
                self.private.futures.get_account_info(),
                return_exceptions=True
            )
            
            spot_balances = spot_account.get('balances', []) if not isinstance(spot_account, Exception) else []
            futures_balances = futures_account.get('assets', []) if not isinstance(futures_account, Exception) else []
            
            return {
                'timestamp': datetime.now().isoformat(),
                'spot': {
                    'total_balance': sum(float(b['free']) + float(b['locked']) for b in spot_balances),
                    'balances': spot_balances
                },
                'futures': {
                    'total_balance': sum(float(b['walletBalance']) for b in futures_balances),
                    'balances': futures_balances
                }
            }
        except Exception as e:
            logger.error(f"❌ Error getting unified account summary: {e}")
            return {}
    #
    # Portfolio Snapshot
    async def get_portfolio_snapshot(self, base_currency: str = "USDT") -> Dict[str, Any]:
        """Optimize edilmiş portfolio snapshot."""
        try:
            # Parallel requests for better performance
            spot_task = self.private.spot.get_account_info()
            futures_task = self.private.futures.get_account_info()
            
            spot_account, futures_account = await asyncio.gather(
                spot_task, futures_task, return_exceptions=True
            )

            # Handle exceptions
            if isinstance(spot_account, Exception):
                logger.error(f"Spot balance error: {spot_account}")
                spot_balances = []
            else:
                spot_balances = spot_account.get('balances', [])

            if isinstance(futures_account, Exception):
                logger.warning(f"Futures balances not available: {futures_account}")
                futures_balances = []
            else:
                futures_balances = futures_account.get('assets', [])

            # Optimize symbol collection
            symbols_to_fetch = set()
            assets_to_process = set()

            # Collect unique assets
            for balance in spot_balances:
                asset = balance['asset']
                total = float(balance['free']) + float(balance['locked'])
                if total > 0:
                    assets_to_process.add(asset)
                    if asset != base_currency:
                        symbols_to_fetch.add(f"{asset}{base_currency}")

            for balance in futures_balances:
                asset = balance['asset']
                wallet_balance = float(balance.get('walletBalance', 0))
                unrealized_pnl = float(balance.get('unrealizedProfit', 0))
                total_balance = wallet_balance + unrealized_pnl
                
                if total_balance != 0:  # Include negative PNL positions
                    assets_to_process.add(asset)
                    if asset != base_currency:
                        symbols_to_fetch.add(f"{asset}{base_currency}")

            # Batch price fetching with caching
            prices = {}
            if symbols_to_fetch:
                prices = await self.get_prices_batch(list(symbols_to_fetch))

            # Pre-calculate all prices including inverse pairs
            price_cache = {}
            for asset in assets_to_process:
                if asset == base_currency:
                    price_cache[asset] = 1.0
                else:
                    symbol = f"{asset}{base_currency}"
                    price = prices.get(symbol)
                    if price is not None:
                        price_cache[asset] = float(price)
                    else:
                        # Try inverse symbol
                        symbol_inv = f"{base_currency}{asset}"
                        price_inv = prices.get(symbol_inv)
                        if price_inv and float(price_inv) > 0:
                            price_cache[asset] = 1.0 / float(price_inv)
                        else:
                            price_cache[asset] = 0.0
                            logger.warning(f"Price not found for {asset}")

            # Process balances
            total_value = 0.0
            asset_details = {}

            # Process spot balances
            for balance in spot_balances:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    price = price_cache[asset]
                    value = total * price
                    
                    asset_details.setdefault(asset, {
                        'spot_balance': 0.0,
                        'futures_balance': 0.0,
                        'unrealized_pnl': 0.0,
                        'price': price,
                        'value': 0.0,
                        'percentage': 0.0
                    })
                    
                    asset_details[asset]['spot_balance'] += total
                    asset_details[asset]['value'] += value
                    total_value += value

            # Process futures balances
            for balance in futures_balances:
                asset = balance['asset']
                wallet_balance = float(balance.get('walletBalance', 0))
                unrealized_pnl = float(balance.get('unrealizedProfit', 0))
                total_balance = wallet_balance + unrealized_pnl
                
                if total_balance != 0:
                    price = price_cache[asset]
                    value = total_balance * price
                    
                    asset_details.setdefault(asset, {
                        'spot_balance': 0.0,
                        'futures_balance': 0.0,
                        'unrealized_pnl': 0.0,
                        'price': price,
                        'value': 0.0,
                        'percentage': 0.0
                    })
                    
                    asset_details[asset]['futures_balance'] += wallet_balance
                    asset_details[asset]['unrealized_pnl'] += unrealized_pnl
                    asset_details[asset]['value'] += value
                    total_value += value

            # Calculate percentages and finalize
            for asset, detail in asset_details.items():
                if total_value > 0:
                    detail['percentage'] = (detail['value'] / total_value) * 100
                
                # Cleanup zero values
                if detail['value'] == 0:
                    del asset_details[asset]

            return {
                'timestamp': datetime.now().isoformat(),
                'base_currency': base_currency,
                'total_value': total_value,
                'assets': asset_details,
                'spot_total': sum(detail['value'] for detail in asset_details.values() 
                                if detail.get('spot_balance', 0) > 0),
                'futures_total': sum(detail['value'] for detail in asset_details.values() 
                                   if detail.get('futures_balance', 0) != 0),
                'cash_balance': asset_details.get(base_currency, {}).get('value', 0)
            }

        except Exception as e:
            logger.error(f"❌ Error getting portfolio snapshot: {e}")
            raise BinanceAPIError(f"Error getting portfolio snapshot: {e}")
    

    # Batch Request

    async def get_prices_batch(self, symbols: List[str], chunk_size: int = 50) -> Dict[str, float]:
        """Büyük request'leri chunk'lara böl"""
        if len(symbols) <= chunk_size:
            return await self._fetch_prices_batch(symbols)
        
        results = {}
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i + chunk_size]
            chunk_results = await self._fetch_prices_batch(chunk)
            results.update(chunk_results)
            await asyncio.sleep(0.1)  # Small delay between chunks
        
        return results  


    async def _fetch_prices_batch(self, symbols: List[str]) -> Dict[str, float]:
        tasks = [self.get_price(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            symbol: price for symbol, price in zip(symbols, results)
            if not isinstance(price, Exception) and price is not None
        }


    
    # -------------------------------------------------------------------------
    # PARALLEL DATA FETCHING
    # -------------------------------------------------------------------------
    
    async def fetch_market_overview(self) -> Dict[str, Any]:
        """Fetch comprehensive market overview data in parallel."""
        tasks = {
            'tickers_24h': self.get_all_24h_tickers(),
            'exchange_info_spot': self.get_exchange_info(futures=False),
            'exchange_info_futures': self.get_exchange_info(futures=True),
            'top_gainers': self.get_top_gainers_with_volume(limit=10),
            'top_losers': self.get_top_losers_with_volume(limit=10),
            'volume_leaders': self.get_volume_leaders(limit=10),
            'server_time': self.get_server_time(),
        }
        
        try:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            processed_results = {}
            for key, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ Parallel fetch failed for {key}: {result}")
                    processed_results[key] = None
                else:
                    processed_results[key] = result
            
            return processed_results
            
        except Exception as e:
            logger.error(f"❌ Parallel market overview fetch failed: {e}")
            return {key: None for key in tasks.keys()}
    
    # -------------------------------------------------------------------------
    # SYSTEM HEALTH AND MONITORING
    # -------------------------------------------------------------------------
    
    async def system_health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check."""
        health = {
            'timestamp': datetime.now().isoformat(),
            'ping': False,
            'api_keys_valid': False,
            'server_time': None,
            'circuit_breaker_state': self.circuit_breaker.state,
            'cache_stats': self._cache.get_stats() if self._cache else {},
            'request_stats': {
                'total_requests': self._request_count,
                'avg_response_time': self._total_request_time / self._request_count if self._request_count > 0 else 0,
            },
            'system_status': 'unknown',
            'errors': []
        }
        
        # ✅ API key bilgisini GÜVENLİ şekilde logla
        has_api_key = bool(self.http.api_key if hasattr(self, 'http') else False)
        health['api_key_configured'] = has_api_key
        if has_api_key:
            logger.debug(f"🔑 API key configured: {self.http.api_key[:8]}...")  # DEBUG seviyesinde
        else:
            logger.debug("🔑 No API key configured (public mode only)")
        
        start_time = time.time()
        
        try:
            # Test basic connectivity
            health['ping'] = await self.ping()
            
            # Test API keys if configured
            if self.http.api_key:
                health['api_keys_valid'] = await self.check_api_keys()
            
            # Get server time
            server_time = await self.public.spot.get_server_time()
            health['server_time'] = server_time.get('serverTime')
            
            # Determine overall system status
            if health['ping'] and health['api_keys_valid']:
                health['system_status'] = 'healthy'
            elif health['ping']:
                health['system_status'] = 'degraded'
            else:
                health['system_status'] = 'offline'
            
            health['response_time'] = time.time() - start_time
            
        except Exception as e:
            health['system_status'] = 'error'
            health['errors'].append(str(e))
            health['response_time'] = time.time() - start_time
            logger.error(f"❌ Health check failed: {e}")
        
        return health
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics and statistics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'request_count': self._request_count,
            'total_request_time': self._total_request_time,
            'avg_request_time': self._total_request_time / self._request_count if self._request_count > 0 else 0,
            'cache_stats': self._cache.get_stats() if self._cache else {},
            'circuit_breaker': {
                'state': self.circuit_breaker.state,
                'failure_count': self.circuit_breaker.failure_count,
                'last_failure_time': self.circuit_breaker.last_failure_time,
            }
        }
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    async def clear_cache(self) -> None:
        """Clear all cached data."""
        if self._cache:
            await self._cache.clear()
            logger.info("✅ Cache cleared successfully")
    
    async def cleanup_expired_cache(self) -> None:
        """Clean up expired cache entries."""
        if self._cache:
            await self._cache.cleanup()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats() if self._cache else {}
    
    async def ping(self) -> bool:
        """Test API connectivity."""
        try:
            result = await self.public.spot.ping()
            return result == {}
        except Exception as e:
            logger.warning(f"❌ Ping failed: {e}")
            return False
    
    async def check_api_keys(self) -> bool:
        """Validate API keys."""
        try:
            await self.private.spot.get_account_info()
            return True
        except Exception as e:
            logger.warning(f"❌ API key check failed: {e}")
            return False
    
    async def get_price(self, symbol: str, futures: bool = False) -> Optional[float]:
        """Get current price for symbol."""
        try:
            if futures:
                ticker = await self.public.futures.get_futures_24hr_ticker(symbol)
                return float(ticker.get('lastPrice', 0))
            else:
                price_data = await self.public.spot.get_symbol_price(symbol)
                return float(price_data.get('price', 0))
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    # Özel bir güvenli logger methodu
    def _safe_log_api_info(self):
        """Güvenli API bilgisi logging."""
        if logger.isEnabledFor(logging.DEBUG):
            api_key = self._config.get("api_key")
            if api_key:
                logger.debug(f"🔑 API key: {api_key[:8]}... (length: {len(api_key)})")
            else:
                logger.debug("🔑 No API key configured")
            
            base_url = self._config.get("base_url", "")
            if "testnet" in base_url:
                logger.debug("🌐 Testnet mode active")
            else:
                logger.debug("🌐 Mainnet mode active")
                

    def __repr__(self) -> str:
        """Güvenli repr implementation."""
        return f"BinanceAPI(api_key={'***' + self._config.get('api_key', '')[-4:] if self._config.get('api_key') else 'None'})"

    def __str__(self) -> str:
        """Güvenli string representation."""
        return f"BinanceAPI(instance_id={id(self)}, has_api_key={bool(self._config.get('api_key'))})"


# =============================================================================
# GLOBAL FACTORY FUNCTIONS
# =============================================================================

_binance_api_instance: Optional[BinanceAPI] = None
_instance_lock = asyncio.Lock()

async def get_or_create_binance_api_from_config(config: Dict[str, Any]) -> BinanceAPI:
    """Config'den BinanceAPI instance'ı oluşturur veya mevcut olanı döndürür."""
    return await BinanceAPI.create_from_config(config)

async def get_or_create_binance_api(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    cache_ttl: int = 30,
    cache_max_size: Optional[int] = 1000,
    base_url: Optional[str] = None,
    fapi_url: Optional[str] = None,
    failure_threshold: int = 5,
    reset_timeout: int = 30,
    requests_per_second: int = 10,
    testnet: bool = False
) -> BinanceAPI:
    """Geliştirilmiş factory fonksiyonu."""
    global _binance_api_instance
    
    async with _instance_lock:
        if _binance_api_instance is None:
            try:
                if testnet:
                    base_url = base_url or "https://testnet.binance.vision"
                    fapi_url = fapi_url or "https://testnet.binancefuture.com"
                else:
                    base_url = base_url or "https://api.binance.com"
                    fapi_url = fapi_url or "https://fapi.binance.com"
                
                http_client = BinanceHTTPClient(
                    api_key=api_key,
                    secret_key=api_secret,
                    base_url=base_url,
                    fapi_url=fapi_url,
                    config={
                        "requests_per_second": requests_per_second
                    }
                )
                
                circuit_breaker = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    reset_timeout=reset_timeout
                )
                
                config = {
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "base_url": base_url,
                    "fapi_url": fapi_url,
                    "cache_ttl": cache_ttl,
                    "failure_threshold": failure_threshold,
                    "reset_timeout": reset_timeout,
                    "requests_per_second": requests_per_second,
                    "testnet": testnet
                }
                
                _binance_api_instance = await BinanceAPI.create(
                    http_client=http_client,
                    circuit_breaker=circuit_breaker,
                    cache_ttl=cache_ttl,
                    cache_max_size=cache_max_size,
                    config=config
                )
                
                # ✅ GÜVENLİ LOGGING - BURAYA EKLENECEK
                logger.info("✅ Global BinanceAPI instance created successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to create global BinanceAPI instance: {e}")
                raise RuntimeError(f"BinanceAPI initialization failed: {e}")
        
        return _binance_api_instance

async def get_binance_api() -> BinanceAPI:
    """Get existing global BinanceAPI instance."""
    if _binance_api_instance is None:
        raise RuntimeError(
            "BinanceAPI not initialized. Call get_or_create_binance_api() first."
        )
    return _binance_api_instance

async def close_binance_api() -> None:
    """Close and cleanup global BinanceAPI instance."""
    global _binance_api_instance
    
    if _binance_api_instance is not None:
        await _binance_api_instance.close()
        _binance_api_instance = None
        logger.info("✅ Global BinanceAPI instance closed and cleared")

@asynccontextmanager
async def binance_api_context(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    **kwargs
):
    """Context manager for temporary BinanceAPI usage."""
    api = await get_or_create_binance_api(api_key, api_secret, **kwargs)
    try:
        yield api
    finally:
        await close_binance_api()


