"""bot/config.py - Optimal config yönetimi

Binance için yapılandırma sınıfı. Default değerler ile gelir,
.env dosyasındaki değerlerle override edilir.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Environment variables'ı yükle
load_dotenv()

# Logging yapılandırması
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global cache instance
_CONFIG_INSTANCE: Optional["BinanceConfig"] = None


@dataclass
class BinanceConfig:
    """Binance yapılandırma sınıfı.

    Default değerler ile başlar, .env dosyasındaki değerlerle override edilir.
    Güvenlik gerektiren parametreler (api_key, secret_key) zorunludur.
    """

    # 🔐 Güvenlik gerektirenler (.env'den ZORUNLU)
    api_key: Optional[str] = None
    secret_key: Optional[str] = None

    # ========================
    # ⚙️ TECHNICAL SETTINGS (DEFAULT DEĞERLER)
    # ========================

    # API URLs
    BASE_URL: str = "https://api.binance.com"
    FAPI_URL: str = "https://fapi.binance.com"
    WS_BASE_URL: str = "wss://stream.binance.com:9443/ws"

    # Rate limiting - HTTP
    LIMITER_RATE: int = 10
    LIMITER_PERIOD: int = 1
    MAX_REQUESTS_PER_SECOND: int = 5
    MIN_REQUEST_INTERVAL: float = 0.2

    # Rate limiting - Weight-based
    MAX_WEIGHT_PER_MINUTE: int = 1200
    WEIGHT_BUFFER: int = 50
    MAX_REQUESTS_PER_IP_PER_MINUTE: int = 1200
    MAX_ORDERS_PER_IP_PER_SECOND: int = 10

    # Connection settings
    REQUEST_TIMEOUT: int = 30
    MAX_CONNECTIONS: int = 100
    MAX_KEEPALIVE_CONNECTIONS: int = 50
    CONCURRENCY: int = 10

    # WebSocket settings
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

    # ========================
    # 📊 BUSINESS LOGIC (DEFAULT DEĞERLER)
    # ========================

    # 🔥 SCAN_SYMBOLS - takip edilen default liste
    SCAN_SYMBOLS: List[str] = field(
        default_factory=lambda: [
            "BTCUSDT",
            "ETHUSDT",
            "BNBUSDT",
            "SOLUSDT",
            "TRXUSDT",
            "CAKEUSDT",
            "SUIUSDT",
            "PEPEUSDT",
            "ARPAUSDT",
            "TURBOUSDT",
        ]
    )

    # Trading parameters
    ALERT_PRICE_CHANGE_PERCENT: float = 5.0
    MAX_POSITION_SIZE_USD: float = 1000
    TRADING_PAIRS: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    ENABLE_TRADING: bool = False
    TRADING_STRATEGY: str = "conservative"
    MAX_LEVERAGE: int = 3
    STOP_LOSS_PERCENT: float = 2.0
    TAKE_PROFIT_PERCENT: float = 5.0
    TRADING_HOURS: List[str] = field(default_factory=lambda: ["00:00-23:59"])

    # 📊 MONITORING CONFIG
    MONITORING_INTERVAL: int = 60
    ENABLE_PRICE_ALERTS: bool = True
    ENABLE_WHALE_ALERTS: bool = True
    ALERT_COOLDOWN: int = 300
    WHALE_TRADE_THRESHOLD: float = 100000.0
    VOLUME_SPIKE_THRESHOLD: float = 3.0

    # 🌐 NETWORK CONFIG
    PROXY_URL: Optional[str] = None
    ENABLE_KEEP_ALIVE: bool = True
    DNS_TIMEOUT: int = 5
    CONNECT_TIMEOUT: int = 10

    # Request weights - Sabit değerler
    REQUEST_WEIGHTS: Dict[str, int] = field(
        default_factory=lambda: {
            "/api/v3/time": 1,
            "/api/v3/exchangeInfo": 10,
            "/api/v3/ticker/price": 1,
            "/api/v3/ticker/24hr": 1,
            "/api/v3/depth": 1,
            "/api/v3/trades": 1,
            "/api/v3/aggTrades": 1,
            "/api/v3/klines": 1,
            "/api/v3/account": 10,
            "/api/v3/order": 1,
            "/api/v3/userDataStream": 1,
            "/fapi/v1/fundingRate": 1,
            "/fapi/v2/positionRisk": 5,
        }
    )

    # ========================
    # 🛠️ METHODS
    # ========================

    @classmethod
    async def from_env(cls) -> "BinanceConfig":
        """Environment'dan config oluşturur.

        .env dosyasındaki değerler varsayılanları override eder.
        API key ve secret zorunludur.
        """
        api_key: Optional[str] = os.getenv("BINANCE_API_KEY")
        secret_key: Optional[str] = os.getenv("BINANCE_API_SECRET")

        if not api_key or not secret_key:
            raise ValueError(
                "❌ Binance API key ve secret zorunludur. "
                "Lütfen .env dosyanıza BINANCE_API_KEY ve BINANCE_API_SECRET ekleyin."
            )

        return cls(
            api_key=api_key,
            secret_key=secret_key,
            SCAN_SYMBOLS=os.getenv(
                "SCAN_SYMBOLS",
                "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,TRXUSDT,CAKEUSDT,SUIUSDT,PEPEUSDT,ARPAUSDT,TURBOUSDT",
            ).split(","),
            ALERT_PRICE_CHANGE_PERCENT=float(
                os.getenv("ALERT_PRICE_CHANGE_PERCENT", "5.0")
            ),
            MAX_POSITION_SIZE_USD=float(os.getenv("MAX_POSITION_SIZE_USD", "1000")),
            TRADING_PAIRS=os.getenv("TRADING_PAIRS", "BTCUSDT,ETHUSDT").split(","),
            ENABLE_TRADING=os.getenv("ENABLE_TRADING", "false").lower() == "true",
            TRADING_STRATEGY=os.getenv("TRADING_STRATEGY", "conservative"),
            MAX_LEVERAGE=int(os.getenv("MAX_LEVERAGE", "3")),
            MONITORING_INTERVAL=int(os.getenv("MONITORING_INTERVAL", "60")),
            ENABLE_PRICE_ALERTS=os.getenv("ENABLE_PRICE_ALERTS", "true").lower()
            == "true",
            PROXY_URL=os.getenv("PROXY_URL"),
            ENABLE_KEEP_ALIVE=os.getenv("ENABLE_KEEP_ALIVE", "true").lower() == "true",
        )

    async def validate(self) -> bool:
        """Config değerlerini doğrular.

        Returns:
            bool: Config geçerli ise True
        Raises:
            ValueError: Zorunlu alanlar eksikse
        """
        if not self.api_key or not self.secret_key:
            raise ValueError("❌ API key ve secret gereklidir.")

        if len(self.SCAN_SYMBOLS) > 50:
            logger.warning(
                "⚠️ Çok fazla SCAN_SYMBOLS tanımlanmış (%d). Performans riski olabilir.",
                len(self.SCAN_SYMBOLS),
            )

        return True

    def get_weight(self, endpoint: str) -> int:
        """Belirli bir Binance endpoint'i için weight değerini döndürür.

        Args:
            endpoint (str): Binance API endpoint yolu

        Returns:
            int: Endpoint weight değeri
        """
        return self.REQUEST_WEIGHTS.get(endpoint, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Config'i dict olarak döndürür (debug/log amaçlı).

        Returns:
            Dict[str, Any]: Config dictionary
        """
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# ✅ Global config instance
async def get_config() -> BinanceConfig:
    """Global config instance'ını döndürür.

    Singleton cache mekanizması ile yalnızca ilk çağrıda yüklenir.
    """
    global _CONFIG_INSTANCE
    if _CONFIG_INSTANCE is None:
        _CONFIG_INSTANCE = await BinanceConfig.from_env()
        await _CONFIG_INSTANCE.validate()
        logger.info("✅ Binance config yüklendi")
    return _CONFIG_INSTANCE
