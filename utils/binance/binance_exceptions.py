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