"""Circuit breaker pattern implementation for Binance API."""

import time
import logging
from typing import Any, Callable, Dict
from .binance_constants import CircuitState
from .binance_exceptions import BinanceCircuitBreakerError

class CircuitBreaker:
    """Devre kesici deseni için gelişmiş hata yönetimi sınıfı."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60, name: str = "default") -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        self.name = name
        self.success_count = 0
        self.log = logging.getLogger(__name__)
        self.log.info(f"CircuitBreaker '{name}' initialized")

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Bir fonksiyonu devre kesici kontrolü ile çalıştır."""
        current_time = time.time()

        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.log.warning(f"CircuitBreaker '{self.name}' moving to HALF_OPEN state")
            else:
                remaining = self.reset_timeout - (current_time - self.last_failure_time)
                self.log.error(f"CircuitBreaker '{self.name}' is OPEN. Retry in {remaining:.1f}s")
                raise BinanceCircuitBreakerError(f"Circuit breaker is OPEN. Retry in {remaining:.1f}s")

        try:
            result = await func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= max(1, self.failure_threshold // 2):
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.log.info(f"CircuitBreaker '{self.name}' reset to CLOSED state")

            return result

        except Exception as e:
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.failure_count = self.failure_threshold
                self.log.error(f"CircuitBreaker '{self.name}' reverted to OPEN from HALF_OPEN")
            else:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.log.error(f"CircuitBreaker '{self.name}' tripped to OPEN state")

            self.log.error(f"CircuitBreaker '{self.name}' execution failed: {str(e)}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Devre kesicinin mevcut durum bilgisini döndür."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": time.time() - self.last_failure_time if self.last_failure_time > 0 else 0
        }