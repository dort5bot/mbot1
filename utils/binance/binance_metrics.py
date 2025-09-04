"""Binance API metrik sınıfları."""

from dataclasses import dataclass

@dataclass
class RequestMetrics:
    total_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limited_requests: int = 0
    avg_response_time: float = 0.0
    last_request_time: float = 0.0

@dataclass
class WSMetrics:
    total_connections: int = 0
    failed_connections: int = 0
    messages_received: int = 0
    reconnections: int = 0
    avg_message_rate: float = 0.0