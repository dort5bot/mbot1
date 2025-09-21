"""bot/config.py - Aiogram 3.x uyumlu optimal config yönetimi

Binance ve Aiogram için yapılandırma sınıfı. Default değerler ile gelir,
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
logger.setLevel(logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")))

# Global cache instance
_CONFIG_INSTANCE: Optional["BotConfig"] = None


@dataclass
class BotConfig:
    """Aiogram 3.x uyumlu bot yapılandırma sınıfı."""
    
    # ========================
    # 🤖 TELEGRAM BOT SETTINGS
    # ========================
    TELEGRAM_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    NGROK_URL: str = field(default_factory=lambda: os.getenv("NGROK_URL", "https://2fce5af7336f.ngrok-free.app"))
    
    DEFAULT_LOCALE: str = field(default_factory=lambda: os.getenv("DEFAULT_LOCALE", "en"))
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])
    
    # Webhook settings
    USE_WEBHOOK: bool = field(default_factory=lambda: os.getenv("USE_WEBHOOK", "false").lower() == "true")
    WEBHOOK_HOST: str = field(default_factory=lambda: os.getenv("WEBHOOK_HOST", ""))
    WEBHOOK_SECRET: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    WEBAPP_HOST: str = field(default_factory=lambda: os.getenv("WEBAPP_HOST", "0.0.0.0"))
    WEBAPP_PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "3000")))
    
    # Aiogram specific settings
    AIOGRAM_REDIS_HOST: str = field(default_factory=lambda: os.getenv("AIOGRAM_REDIS_HOST", "localhost"))
    AIOGRAM_REDIS_PORT: int = field(default_factory=lambda: int(os.getenv("AIOGRAM_REDIS_PORT", "6379")))
    AIOGRAM_REDIS_DB: int = field(default_factory=lambda: int(os.getenv("AIOGRAM_REDIS_DB", "0")))
    
    # FSM storage settings
    USE_REDIS_FSM: bool = field(default_factory=lambda: os.getenv("USE_REDIS_FSM", "true").lower() == "true")
    FSM_STORAGE_TTL: int = field(default_factory=lambda: int(os.getenv("FSM_STORAGE_TTL", "3600")))
    
    # ========================
    # 🔐 BINANCE API SETTINGS
    # ========================
    BINANCE_API_KEY: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    BINANCE_API_SECRET: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    BINANCE_BASE_URL: str = field(default_factory=lambda: os.getenv("BINANCE_BASE_URL", "https://api.binance.com"))
    BINANCE_FAPI_URL: str = field(default_factory=lambda: os.getenv("BINANCE_FAPI_URL", "https://fapi.binance.com"))
    BINANCE_WS_URL: str = field(default_factory=lambda: os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443/ws"))

    # ========================
    # ⚙️ TECHNICAL SETTINGS
    # ========================
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Rate limiting
    # Devre kesici ayarları
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = field(default_factory=lambda: int(os.getenv("FAILURE_THRESHOLD", "5")))
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("RESET_TIMEOUT", "30")))
    CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("HALF_OPEN_TIMEOUT", "15")))


    # Database settings
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    USE_DATABASE: bool = field(default_factory=lambda: os.getenv("USE_DATABASE", "false").lower() == "true")
    
    # Cache settings
    CACHE_TTL: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "300")))
    MAX_CACHE_SIZE: int = field(default_factory=lambda: int(os.getenv("MAX_CACHE_SIZE", "1000")))

    
    # ========================
    # ANALYSIS CONFIGURATION
    # ========================
    ANALYSIS_CACHE_TTL: int = field(default_factory=lambda: int(os.getenv("ANALYSIS_CACHE_TTL", "60")))
    SIGNAL_THRESHOLDS: Dict[str, float] = field(default_factory=lambda: {
        "strong_bull": 0.7,
        "bull": 0.3, 
        "bear": -0.3,
        "strong_bear": -0.7
    })

    # MODULE WEIGHTS (aggregator için)
    MODULE_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "causality": 0.15,
        "derivs": 0.15,
        "onchain": 0.15,
        "orderflow": 0.15,
        "regime": 0.15,
        "risk": 0.15,
        "tremo": 0.10
    })

    # RISK MANAGEMENT
    MAX_POSITION_SIZE: float = field(default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE", "0.1")))
    DEFAULT_LEVERAGE: int = field(default_factory=lambda: int(os.getenv("DEFAULT_LEVERAGE", "3")))

    # ========================
    # 📊 TRADING SETTINGS
    # ========================
    SCAN_SYMBOLS: List[str] = field(default_factory=lambda: [
        symbol.strip() for symbol in os.getenv(
            "SCAN_SYMBOLS", 
            "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,TRXUSDT,CAKEUSDT,SUIUSDT,PEPEUSDT,ARPAUSDT,TURBOUSDT"
        ).split(",") if symbol.strip()
    ])
    
    ENABLE_TRADING: bool = field(default_factory=lambda: os.getenv("ENABLE_TRADING", "false").lower() == "true")
    TRADING_STRATEGY: str = field(default_factory=lambda: os.getenv("TRADING_STRATEGY", "conservative"))
    MAX_LEVERAGE: int = field(default_factory=lambda: int(os.getenv("MAX_LEVERAGE", "3")))
    
    # Alert settings
    ALERT_PRICE_CHANGE_PERCENT: float = field(default_factory=lambda: float(os.getenv("ALERT_PRICE_CHANGE_PERCENT", "5.0")))
    ENABLE_PRICE_ALERTS: bool = field(default_factory=lambda: os.getenv("ENABLE_PRICE_ALERTS", "true").lower() == "true")
    ALERT_COOLDOWN: int = field(default_factory=lambda: int(os.getenv("ALERT_COOLDOWN", "300")))

    # ========================
    # 🛠️ METHODS & PROPERTIES
    # ========================
    @property
    def WEBHOOK_PATH(self) -> str:
        """Webhook path'i dinamik olarak oluşturur (Telegram formatına uygun)."""
        if not self.TELEGRAM_TOKEN:
            return "/webhook/default"
        return f"/webhook/{self.TELEGRAM_TOKEN}"

    @property
    def WEBHOOK_URL(self) -> str:
        return f"{self.WEBHOOK_HOST.rstrip('/')}{self.WEBHOOK_PATH}"

    @classmethod
    def load(cls) -> "BotConfig":
        """Environment'dan config yükler."""
        return cls()

    def validate(self) -> bool:
        """Config değerlerini doğrular."""
        errors = []
        
        # Telegram bot validation
        if not self.TELEGRAM_TOKEN:
            errors.append("❌ TELEGRAM_TOKEN gereklidir")
        
        # Webhook validation (eğer webhook kullanılıyorsa)
        if self.USE_WEBHOOK:
            if not self.WEBHOOK_HOST:
                errors.append("❌ WEBHOOK_HOST gereklidir (USE_WEBHOOK=true)")
        
        # Binance validation (eğer trading enabled ise)
        if self.ENABLE_TRADING:
            if not self.BINANCE_API_KEY:
                errors.append("❌ BINANCE_API_KEY gereklidir (trading enabled)")
            if not self.BINANCE_API_SECRET:
                errors.append("❌ BINANCE_API_SECRET gereklidir (trading enabled)")
        
        if errors:
            raise ValueError("\n".join(errors))
        
        return True

    def is_admin(self, user_id: int) -> bool:
        """Kullanıcının admin olup olmadığını kontrol eder."""
        return user_id in self.ADMIN_IDS

    def to_dict(self) -> Dict[str, Any]:
        """Config'i dict olarak döndürür (debug/log amaçlı)."""
        sensitive_fields = {"TELEGRAM_TOKEN", "BINANCE_API_KEY", "BINANCE_API_SECRET", "WEBHOOK_SECRET"}
        result = {}
        
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name in sensitive_fields and value:
                result[field_name] = "***HIDDEN***"
            else:
                result[field_name] = value
        
        # Property'leri de ekle
        result["WEBHOOK_PATH"] = self.WEBHOOK_PATH
        result["WEBHOOK_URL"] = self.WEBHOOK_URL
        
        return result


def get_config_sync() -> BotConfig:
    """Sync config instance'ını döndürür."""
    global _CONFIG_INSTANCE
    if _CONFIG_INSTANCE is None:
        _CONFIG_INSTANCE = BotConfig.load()
        _CONFIG_INSTANCE.validate()
        logger.info("✅ Bot config yüklendi ve doğrulandı")
        logger.debug(f"Config: {_CONFIG_INSTANCE.to_dict()}")
    return _CONFIG_INSTANCE


async def get_config() -> BotConfig:
    """Global config instance'ını döndürür (async wrapper)."""
    return get_config_sync()


def get_telegram_token() -> str:
    """Aiogram için Telegram bot token'ını döndürür."""
    config = get_config_sync()
    return config.TELEGRAM_TOKEN


def get_admins() -> List[int]:
    """Admin kullanıcı ID'lerini döndürür."""
    config = get_config_sync()
    return config.ADMIN_IDS


def get_webhook_config() -> Dict[str, Any]:
    """Webhook konfigürasyonu döndürür."""
    config = get_config_sync()
    return {
        "path": config.WEBHOOK_PATH,
        "url": config.WEBHOOK_URL,
        "secret_token": config.WEBHOOK_SECRET,
        "host": config.WEBAPP_HOST,
        "port": config.WEBAPP_PORT,
    }


def get_redis_config() -> Dict[str, Any]:
    """Aiogram için Redis konfigürasyonu döndürür."""
    config = get_config_sync()
    return {
        "host": config.AIOGRAM_REDIS_HOST,
        "port": config.AIOGRAM_REDIS_PORT,
        "db": config.AIOGRAM_REDIS_DB,
    }