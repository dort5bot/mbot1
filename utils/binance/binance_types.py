"""Binance API type definitions."""

from typing import TypedDict, Literal, Union

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

# 🎯 Order Types
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT", "MARKET", "STOP_LOSS"]
OrderStatus = Literal["NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED"]

class OrderData(TypedDict):
    symbol: str
    orderId: int
    side: OrderSide
    type: OrderType
    status: OrderStatus
    price: str
    quantity: str
