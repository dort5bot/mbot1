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