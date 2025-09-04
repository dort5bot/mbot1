
"""
utils/binance/binance_metrics.py
Binance API metrik sınıfları.
# PEP8 + type hints + docstring + async yapı + singleton + logging + Async Yapı olacak
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import time


@dataclass
class RequestMetrics:
    total_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limited_requests: int = 0
    avg_response_time: float = 0.0
    last_request_time: float = 0.0

    def update_response_time(self, response_time: float) -> None:
        """Yeni bir response süresi ekle ve ortalamayı güncelle."""
        if self.total_requests > 0:
            # Hareketli ortalama
            self.avg_response_time = (
                (self.avg_response_time * (self.total_requests - 1)) + response_time
            ) / self.total_requests
        else:
            self.avg_response_time = response_time
        self.last_request_time = time.time()


@dataclass
class WSMetrics:
    total_connections: int = 0
    failed_connections: int = 0
    messages_received: int = 0
    reconnections: int = 0
    avg_message_rate: float = 0.0
    _message_timestamps: List[float] = field(default_factory=list, repr=False)

    def add_message(self, timestamp: float = None) -> None:
        """Yeni mesaj geldiğinde çağır. Ortalama mesaj hızını günceller."""
        if timestamp is None:
            timestamp = time.time()
        self.messages_received += 1
        self._message_timestamps.append(timestamp)
        # Son 1000 mesajı tut
        if len(self._message_timestamps) > 1000:
            self._message_timestamps.pop(0)
        self.update_message_rate()

    def update_message_rate(self) -> None:
        """Son N mesaj zamanına göre ortalama mesaj hızını güncelle."""
        ts = self._message_timestamps
        if len(ts) > 1:
            interval = max(ts[-1] - ts[0], 1e-6)
            self.avg_message_rate = len(ts) / interval
        else:
            self.avg_message_rate = 0.0


@dataclass
class AdvancedMetrics(RequestMetrics):
    """Gelişmiş metrikler - Weight, endpoint, IP limitleri ve recent errors"""
    weight_usage: int = 0
    weight_limit_remaining: int = 1200
    ip_rate_limit_remaining: int = 1200
    order_rate_limit_remaining: int = 10
    endpoint_usage: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)

    def update_weight_usage(self, endpoint: str, weight: int) -> None:
        """Weight kullanımını güncelle."""
        self.weight_usage += weight
        self.weight_limit_remaining -= weight
        self.endpoint_usage[endpoint] = self.endpoint_usage.get(endpoint, 0) + 1

    def add_error(self, endpoint: str, error: str, status_code: int = None) -> None:
        """Hata ekle ve son 10 hatayı sakla."""
        self.recent_errors.append({
            "endpoint": endpoint,
            "error": error,
            "status_code": status_code,
            "timestamp": time.time()
        })
        if len(self.recent_errors) > 10:
            self.recent_errors.pop(0)
