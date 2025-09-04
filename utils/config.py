"""Binance API konfigürasyon yönetimi."""
"""utils/config.py"""

import os
from dataclasses import dataclass
from typing import Dict

@dataclass
class BinanceConfig:
    # API URLs
    BASE_URL: str = "https://api.binance.com"
    FAPI_URL: str = "https://fapi.binance.com"
    WS_BASE_URL: str = "wss://stream.binance.com:9443/ws"
    
    # ⚠️ Rate limiting - HTTP🔸
    LIMITER_RATE: int = 10                # 10 istekte bir
    LIMITER_PERIOD: int = 1                # 1 saniyede
    MAX_REQUESTS_PER_SECOND: int = 5        # Saniyede maksimum istek
    MIN_REQUEST_INTERVAL: float = 0.2
    
    # ⚠️ Rate limiting - Weight-based🔸
    MAX_WEIGHT_PER_MINUTE: int = 1200
    WEIGHT_BUFFER: int = 50
    MAX_REQUESTS_PER_IP_PER_MINUTE: int = 1200
    MAX_ORDERS_PER_IP_PER_SECOND: int = 10
    
    # Connection settings
    REQUEST_TIMEOUT: int = 30
    MAX_CONNECTIONS: int = 100
    MAX_KEEPALIVE_CONNECTIONS: int = 50
    CONCURRENCY: int = 10
    
    # ⚠️ WebSocket settings
    MAX_WEBSOCKET_CONNECTIONS: int = 10
    WS_RECONNECT_DELAY: int = 5
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 10
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # Retry settings
    DEFAULT_RETRY_ATTEMPTS: int = 3
    RETRY_BACKOFF_FACTOR: float = 2.0
    MAX_RETRY_DELAY: int = 60
    
    # Circuit breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60
    CIRCUIT_BREAKER_HALF_OPEN_SUCCESS: int = 3
    
    # Cache settings
    BINANCE_TICKER_TTL: int = 5
    CACHE_CLEANUP_INTERVAL: int = 60
    MAX_CACHE_SIZE: int = 1000
    
    # Batch processing
    MAX_BATCH_REQUESTS: int = 5
    BATCH_REQUEST_DELAY: float = 0.1
    
    # Request weights - Her endpoint için weight değerleri
    REQUEST_WEIGHTS: Dict[str, int] = None
    
    def __post_init__(self):
        """Dataclass init sonrası çalışır."""
        if self.REQUEST_WEIGHTS is None:
            self.REQUEST_WEIGHTS = {
                '/api/v3/time': 1,
                '/api/v3/exchangeInfo': 10,
                '/api/v3/ticker/price': 1,
                '/api/v3/ticker/24hr': 1,
                '/api/v3/depth': 1,
                '/api/v3/trades': 1,
                '/api/v3/aggTrades': 1,
                '/api/v3/klines': 1,
                '/api/v3/account': 10,
                '/api/v3/order': 1,
                '/api/v3/userDataStream': 1,
                '/fapi/v1/fundingRate': 1,
                '/fapi/v2/positionRisk': 5
            }
    
    @classmethod
    def from_env(cls):
        """Environment variables'dan konfigürasyon oluştur."""
        return cls(
            BASE_URL=os.getenv("BINANCE_BASE_URL", "https://api.binance.com"),
            FAPI_URL=os.getenv("BINANCE_FAPI_URL", "https://fapi.binance.com"),
            
            # Rate limiting
            LIMITER_RATE=int(os.getenv("BINANCE_LIMITER_RATE", "10")),
            MAX_REQUESTS_PER_SECOND=int(os.getenv("BINANCE_MAX_REQUESTS_PER_SECOND", "5")),
            MAX_WEIGHT_PER_MINUTE=int(os.getenv("BINANCE_MAX_WEIGHT", "1200")),
            
            # Connection
            REQUEST_TIMEOUT=int(os.getenv("BINANCE_REQUEST_TIMEOUT", "30")),
            MAX_CONNECTIONS=int(os.getenv("BINANCE_MAX_CONNECTIONS", "100")),
            
            # WebSocket - EKSİK OLANLAR
            MAX_WEBSOCKET_CONNECTIONS=int(os.getenv("BINANCE_MAX_WS_CONNECTIONS", "10")),
            WS_RECONNECT_DELAY=int(os.getenv("BINANCE_WS_RECONNECT_DELAY", "5")),
            
            # Retry & Circuit breaker
            DEFAULT_RETRY_ATTEMPTS=int(os.getenv("BINANCE_RETRY_ATTEMPTS", "3")),
            CIRCUIT_BREAKER_FAILURE_THRESHOLD=int(os.getenv("BINANCE_CB_FAILURE_THRESHOLD", "5")),
            
            # Cache
            BINANCE_TICKER_TTL=int(os.getenv("BINANCE_CACHE_TTL", "5")),
        )

    def get_weight(self, endpoint: str) -> int:
        """Endpoint için weight değerini döndür."""
        return self.REQUEST_WEIGHTS.get(endpoint, 1)
