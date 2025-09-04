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
