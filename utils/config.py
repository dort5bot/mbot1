"""Binance API konfigürasyon yönetimi."""
"""utils/config.py"""

import os
from dataclasses import dataclass

@dataclass
class BinanceConfig:
    # API URLs
    BASE_URL: str = "https://api.binance.com"
    FAPI_URL: str = "https://fapi.binance.com"
    WS_BASE_URL: str = "wss://stream.binance.com:9443/ws"
    
    # ⚠️ Rate limiting
    LIMITER_RATE: int = 10                  # 10 istekte bir
    LIMITER_PERIOD: int = 1                 # 1 saniyede
    MAX_REQUESTS_PER_SECOND: int = 5        # Saniyede maksimum istek
    MIN_REQUEST_INTERVAL: float = 0.2
    
    # Connection settings
    REQUEST_TIMEOUT: int = 30
    MAX_CONNECTIONS: int = 100
    MAX_KEEPALIVE_CONNECTIONS: int = 50
    CONCURRENCY: int = 10
    
    # Retry settings
    DEFAULT_RETRY_ATTEMPTS: int = 3
    RETRY_BACKOFF_FACTOR: float = 2.0
    MAX_RETRY_DELAY: int = 60
    
    # Circuit breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60
    
    # Cache settings
    BINANCE_TICKER_TTL: int = 5
    CACHE_CLEANUP_INTERVAL: int = 60
    
    # WebSocket settings
    WS_RECONNECT_DELAY: int = 5
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 10
    
    
     # Weight-based limiting
    REQUEST_WEIGHTS = {
        '/api/v3/ticker/price': 1,
        '/api/v3/order': 10,     # Order daha yüksek weight
        '/api/v3/account': 10
    }
    
    
    @classmethod
    def from_env(cls):
        """Environment variables'dan konfigürasyon oluştur."""
        return cls(
            BASE_URL=os.getenv("BINANCE_BASE_URL", "https://api.binance.com"),
            FAPI_URL=os.getenv("BINANCE_FAPI_URL", "https://fapi.binance.com"),
            LIMITER_RATE=int(os.getenv("BINANCE_LIMITER_RATE", "10")),
            MAX_REQUESTS_PER_SECOND=int(os.getenv("BINANCE_MAX_REQUESTS_PER_SECOND", "5")),
            REQUEST_TIMEOUT=int(os.getenv("BINANCE_REQUEST_TIMEOUT", "30")),
            DEFAULT_RETRY_ATTEMPTS=int(os.getenv("BINANCE_RETRY_ATTEMPTS", "3")),
        )