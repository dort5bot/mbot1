"""
Binance API type definitions and type hints.
"""

from typing import TypedDict, List, Union, Optional, Dict, Any
from datetime import datetime

# Basic Types
Symbol = str
Asset = str
Interval = str  # e.g., "1m", "1h", "1d"
OrderSide = str  # "BUY" or "SELL"
OrderType = str  # "LIMIT", "MARKET", etc.


class Kline(TypedDict):
    """Kline/candlestick data structure."""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float
    ignore: float


class OrderBook(TypedDict):
    """Order book data structure."""
    lastUpdateId: int
    bids: List[List[str]]
    asks: List[List[str]]


class Ticker(TypedDict):
    """24hr ticker price change statistics."""
    symbol: str
    priceChange: str
    priceChangePercent: str
    weightedAvgPrice: str
    prevClosePrice: str
    lastPrice: str
    lastQty: str
    bidPrice: str
    askPrice: str
    openPrice: str
    highPrice: str
    lowPrice: str
    volume: str
    quoteVolume: str
    openTime: int
    closeTime: int
    firstId: int
    lastId: int
    count: int


class Balance(TypedDict):
    """Account balance structure."""
    asset: str
    free: str
    locked: str


class AccountInfo(TypedDict):
    """Account information structure."""
    makerCommission: int
    takerCommission: int
    buyerCommission: int
    sellerCommission: int
    canTrade: bool
    canWithdraw: bool
    canDeposit: bool
    updateTime: int
    accountType: str
    balances: List[Balance]
    permissions: List[str]


class Order(TypedDict):
    """Order information structure."""
    symbol: str
    orderId: int
    orderListId: int
    clientOrderId: str
    price: str
    origQty: str
    executedQty: str
    cummulativeQuoteQty: str
    status: str
    timeInForce: str
    type: str
    side: str
    stopPrice: str
    icebergQty: str
    time: int
    updateTime: int
    isWorking: bool
    origQuoteOrderQty: str


class Trade(TypedDict):
    """Trade information structure."""
    id: int
    price: str
    qty: str
    quoteQty: str
    time: int
    isBuyerMaker: bool
    isBestMatch: bool


# Futures Types
class Position(TypedDict):
    """Futures position information."""
    symbol: str
    positionAmt: str
    entryPrice: str
    markPrice: str
    unRealizedProfit: str
    liquidationPrice: str
    leverage: str
    maxNotionalValue: str
    marginType: str
    isolatedMargin: str
    isAutoAddMargin: str
    positionSide: str
    notional: str
    isolatedWallet: str
    updateTime: int


class FuturesAccount(TypedDict):
    """Futures account information."""
    assets: List[Dict[str, Any]]
    positions: List[Position]
    canDeposit: bool
    canTrade: bool
    canWithdraw: bool
    feeTier: int
    updateTime: int
    totalInitialMargin: str
    totalMaintMargin: str
    totalWalletBalance: str
    totalUnrealizedProfit: str
    totalMarginBalance: str
    totalPositionInitialMargin: str
    totalOpenOrderInitialMargin: str
    totalCrossWalletBalance: str
    totalCrossUnPnl: str
    availableBalance: str
    maxWithdrawAmount: str


# WebSocket Types
class WSMessage(TypedDict):
    """WebSocket message structure."""
    stream: str
    data: Dict[str, Any]


# Response Types
class BinanceResponse(TypedDict):
    """Generic Binance API response."""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    timestamp: int