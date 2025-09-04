"""
utils/binance/binance_metrics.py
Binance API metrik sınıfları."""

"""utils/binance/binance_metrics.py - Metrics classes."""

from dataclasses import dataclass, field
from typing import Dict, List
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

@dataclass
class WSMetrics:
    total_connections: int = 0
    failed_connections: int = 0
    messages_received: int = 0
    reconnections: int = 0
    avg_message_rate: float = 0.0

@dataclass
class AdvancedMetrics(RequestMetrics):
    """Gelişmiş metrikler - ÖNERİ EKLENDİ"""
    weight_usage: int = 0
    weight_limit_remaining: int = 1200
    ip_rate_limit_remaining: int = 1200
    order_rate_limit_remaining: int = 10
    endpoint_usage: Dict[str, int] = field(default_factory=lambda: {})
    recent_errors: List[Dict[str, Any]] = field(default_factory=lambda: [])
    
    def update_weight_usage(self, endpoint: str, weight: int):
        """Weight kullanımını güncelle - ÖNERİ EKLENDİ"""
        self.weight_usage += weight
        self.weight_limit_remaining -= weight
        self.endpoint_usage[endpoint] = self.endpoint_usage.get(endpoint, 0) + 1
        
    def add_error(self, endpoint: str, error: str, status_code: int = None):
        """Hata ekle - ÖNERİ EKLENDİ"""
        self.recent_errors.append({
            "endpoint": endpoint,
            "error": error,
            "status_code": status_code,
            "timestamp": time.time()
        })
        # Son 10 hatayı tut
        if len(self.recent_errors) > 10:
            self.recent_errors.pop(0)
