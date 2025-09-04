"""
utils/binance/binance_circuit_breaker.py
Circuit breaker pattern implementation for Binance API."""
"""utils/binance/binance_circuit_breaker.py - Circuit breaker pattern."""

import time
import logging
from typing import Any, Callable, Dict, Optional
from .binance_constants import CircuitState
from .binance_exceptions import BinanceCircuitBreakerError

class CircuitBreaker:
    """Devre kesici deseni - TEMEL"""
    # ... mevcut kod ...
    
class SmartCircuitBreaker(CircuitBreaker):
    """Akıllı circuit breaker - ÖNERİ EKLENDİ"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_func = None
        self.metrics = []
        
    async def execute_with_fallback(self, func: Callable, fallback_func: Callable, *args, **kwargs):
        """Fallback fonksiyonu ile execute - ÖNERİ EKLENDİ"""
        try:
            return await self.execute(func, *args, **kwargs)
        except Exception as e:
            self.log.warning(f"Circuit open, fallback kullanılıyor: {e}")
            try:
                return await fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                self.log.error(f"Fallback de başarısız: {fallback_error}")
                raise
    
    def add_metrics(self, success: bool, response_time: float, endpoint: str):
        """Metrik ekle - ÖNERİ EKLENDİ"""
        self.metrics.append({
            "success": success,
            "response_time": response_time,
            "endpoint": endpoint,
            "timestamp": time.time()
        })
        # Son 100 metriği tut
        if len(self.metrics) > 100:
            self.metrics.pop(0)
