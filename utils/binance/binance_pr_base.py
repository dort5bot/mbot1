# utils/binance/binance_pr_base.py
"""
Common base for all private domain clients.
Holds http client + circuit breaker + key check logic.
Ortak davranış: http ve circuit_breaker injekte edilir, _require_keys() doğrulaması, logger.
"""
from typing import Any, Optional
import logging

from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_exceptions import BinanceAuthenticationError

logger = logging.getLogger(__name__)


class BinancePrivateBase:
    """
    Base class for private Binance clients.

    Attributes:
        http: BinanceHTTPClient instance
        circuit_breaker: CircuitBreaker instance
    """

    def __init__(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        self.http = http_client
        self.circuit_breaker = circuit_breaker

    async def _require_keys(self) -> None:
        """Require API key and secret for private endpoints."""
        if not getattr(self.http, "api_key", None) or not getattr(self.http, "secret_key", None):
            logger.error("Binance API key/secret not found on http client")
            raise BinanceAuthenticationError("API key and secret required for private endpoints")
