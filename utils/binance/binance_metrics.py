"""
Metrics and monitoring for Binance API.
"""

import time
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for API requests."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    errors_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class RateLimitMetrics:
    """Metrics for rate limiting."""
    requests_per_minute: float = 0
    orders_per_second: float = 0
    weight_used: int = 0
    weight_limit: int = 1200  # Default Binance weight limit


class AdvancedMetrics:
    """
    Advanced metrics collection and monitoring for Binance API.
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize metrics collector.
        
        Args:
            window_size: Size of sliding window for metrics
        """
        self.window_size = window_size
        self.request_metrics = RequestMetrics()
        self.rate_limit_metrics = RateLimitMetrics()
        self.start_time = time.time()
        self.lock = asyncio.Lock()
        logger.info("✅ AdvancedMetrics initialized")
    
    async def record_request(self, success: bool, response_time: float, 
                           error_type: Optional[str] = None) -> None:
        """
        Record API request metrics.
        
        Args:
            success: Whether the request was successful
            response_time: Response time in seconds
            error_type: Type of error if request failed
        """
        async with self.lock:
            self.request_metrics.total_requests += 1
            self.request_metrics.total_response_time += response_time
            self.request_metrics.response_times.append(response_time)
            
            if success:
                self.request_metrics.successful_requests += 1
            else:
                self.request_metrics.failed_requests += 1
                if error_type:
                    self.request_metrics.errors_by_type[error_type] = (
                        self.request_metrics.errors_by_type.get(error_type, 0) + 1
                    )
    
    async def record_rate_limit(self, weight_used: int = 1) -> None:
        """
        Record rate limit usage.
        
        Args:
            weight_used: Weight used by the request
        """
        async with self.lock:
            self.rate_limit_metrics.weight_used += weight_used
    
    async def reset_rate_limit(self) -> None:
        """Reset rate limit metrics."""
        async with self.lock:
            self.rate_limit_metrics.weight_used = 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        async def _get_metrics():
            async with self.lock:
                response_times = list(self.request_metrics.response_times)
                avg_response_time = (self.request_metrics.total_response_time / 
                                   self.request_metrics.total_requests if 
                                   self.request_metrics.total_requests > 0 else 0)
                
                return {
                    "uptime_seconds": time.time() - self.start_time,
                    "total_requests": self.request_metrics.total_requests,
                    "successful_requests": self.request_metrics.successful_requests,
                    "failed_requests": self.request_metrics.failed_requests,
                    "success_rate": (
                        self.request_metrics.successful_requests / 
                        self.request_metrics.total_requests * 100 
                        if self.request_metrics.total_requests > 0 else 100
                    ),
                    "average_response_time": avg_response_time,
                    "min_response_time": min(response_times) if response_times else 0,
                    "max_response_time": max(response_times) if response_times else 0,
                    "p95_response_time": (
                        statistics.quantiles(response_times, n=100)[94] 
                        if len(response_times) >= 5 else 0
                    ),
                    "current_rpm": self._calculate_rpm(),
                    "weight_used": self.rate_limit_metrics.weight_used,
                    "weight_remaining": (
                        self.rate_limit_metrics.weight_limit - 
                        self.rate_limit_metrics.weight_used
                    ),
                    "weight_percentage": (
                        self.rate_limit_metrics.weight_used / 
                        self.rate_limit_metrics.weight_limit * 100
                    ),
                    "errors_by_type": dict(self.request_metrics.errors_by_type),
                }
        
        # For synchronous access, we need to run async function
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to create a task
                future = asyncio.create_task(_get_metrics())
                loop.run_until_complete(future)
                return future.result()
            else:
                return loop.run_until_complete(_get_metrics())
        except:
            # Fallback for edge cases
            return {}
    
    def _calculate_rpm(self) -> float:
        """Calculate requests per minute."""
        uptime_minutes = (time.time() - self.start_time) / 60
        return self.request_metrics.total_requests / uptime_minutes if uptime_minutes > 0 else 0
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status based on metrics."""
        metrics = self.get_metrics()
        
        success_rate = metrics.get("success_rate", 100)
        avg_response_time = metrics.get("average_response_time", 0)
        weight_percentage = metrics.get("weight_percentage", 0)
        
        status = "HEALTHY"
        issues = []
        
        if success_rate < 95:
            status = "DEGRADED"
            issues.append(f"Low success rate: {success_rate:.1f}%")
        
        if avg_response_time > 2.0:  # More than 2 seconds average
            status = "DEGRADED"
            issues.append(f"High response time: {avg_response_time:.2f}s")
        
        if weight_percentage > 80:
            status = "DEGRADED"
            issues.append(f"High rate limit usage: {weight_percentage:.1f}%")
        
        if weight_percentage > 95:
            status = "CRITICAL"
            issues.append(f"Critical rate limit usage: {weight_percentage:.1f}%")
        
        return {
            "status": status,
            "issues": issues,
            "metrics": metrics
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        async def _reset():
            async with self.lock:
                self.request_metrics = RequestMetrics()
                self.rate_limit_metrics = RateLimitMetrics()
                self.start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_reset())
            else:
                loop.run_until_complete(_reset())
        except:
            pass


# Singleton instance
metrics = AdvancedMetrics()