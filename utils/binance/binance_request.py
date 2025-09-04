"""Binance HTTP request mekanizması."""

import os
import time
import json
import asyncio
import random
import hmac
import hashlib
import httpx
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlencode
from aiolimiter import AsyncLimiter

from .binance_constants import RequestPriority
from .binance_metrics import RequestMetrics
from .binance_exceptions import BinanceRequestError, BinanceRateLimitError

class BinanceHTTPClient:
    """Binance HTTP API istemcisi için gelişmiş yönetim sınıfı."""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, config: Any = None) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.config = config
        self._last_request = 0
        self.client = None
        self.limiter = AsyncLimiter(config.LIMITER_RATE, config.LIMITER_PERIOD)
        self.log = logging.getLogger(__name__)

        # Concurrency control
        self.semaphores = {
            RequestPriority.HIGH: asyncio.Semaphore(config.CONCURRENCY),
            RequestPriority.NORMAL: asyncio.Semaphore(config.CONCURRENCY),
            RequestPriority.LOW: asyncio.Semaphore(config.CONCURRENCY // 2),
        }

        # Cache system
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._last_cache_cleanup = time.time()

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / config.MAX_REQUESTS_PER_SECOND

        # Metrics
        self.metrics = RequestMetrics()
        self.request_times: List[float] = []

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            base_url=self.config.BASE_URL,
            timeout=self.config.REQUEST_TIMEOUT,
            limits=httpx.Limits(
                max_connections=self.config.MAX_CONNECTIONS,
                max_keepalive_connections=self.config.MAX_KEEPALIVE_CONNECTIONS,
                keepalive_expiry=300
            ),
            http2=True,
            verify=True,
            cert=os.getenv("SSL_CERT_PATH")
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _cleanup_cache(self) -> None:
        """Süresi dolmuş önbellek girdilerini temizle."""
        current_time = time.time()
        if current_time - self._last_cache_cleanup < self.config.CACHE_CLEANUP_INTERVAL:
            return

        expired_keys = [key for key, (ts, _) in self._cache.items()
                        if current_time - ts > self.config.BINANCE_TICKER_TTL]

        for key in expired_keys:
            del self._cache[key]

        # Cache boyutu sınırlaması
        if len(self._cache) > 1000:
            oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[:100]
            for key in oldest_keys:
                del self._cache[key]

        self._last_cache_cleanup = current_time

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False,
        max_retries: Optional[int] = None,
        priority: RequestPriority = RequestPriority.NORMAL,
    ) -> Any:
        """Ana HTTP request methodu."""
        if self.client is None:
            raise BinanceRequestError("HTTP client not initialized")

        try:
            if max_retries is None:
                max_retries = self.config.DEFAULT_RETRY_ATTEMPTS

            # Rate limiting
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)

            self.last_request_time = time.time()
            self.metrics.total_requests += 1

            # Base URL ve headers
            base_url = self.config.FAPI_URL if futures else self.config.BASE_URL
            headers = {}
            params = params or {}

            # Signed request
            if signed:
                if not self.api_key or not self.secret_key:
                    raise BinanceAuthenticationError("API key and secret key required for signed requests")
                signed_params = dict(params)
                signed_params["timestamp"] = int(time.time() * 1000)
                query = urlencode(signed_params)
                signature = hmac.new(self.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
                signed_params["signature"] = signature
                params = signed_params
                headers["X-MBX-APIKEY"] = self.api_key
            elif self.api_key:
                headers["X-MBX-APIKEY"] = self.api_key

            # Cache cleanup
            if time.time() - self._last_cache_cleanup > self.config.CACHE_CLEANUP_INTERVAL:
                self._cleanup_cache()

            # Cache kontrolü
            cache_key = f"{method}:{base_url}{path}:{json.dumps(params, sort_keys=True) if params else ''}"
            ttl = getattr(self.config, "BINANCE_TICKER_TTL", 0)

            if ttl > 0 and cache_key in self._cache:
                ts_cache, data = self._cache[cache_key]
                if time.time() - ts_cache < ttl:
                    self.metrics.cache_hits += 1
                    return data
                else:
                    self.metrics.cache_misses += 1
                    del self._cache[cache_key]

            # Retry loop
            attempt = 0
            last_exception = None
            start_time = time.time()

            while attempt < max_retries:
                attempt += 1
                try:
                    async with self.limiter:
                        async with self.semaphores[priority]:
                            r = await self.client.request(method, path, params=params, headers=headers)

                    if r.status_code == 200:
                        data = r.json()
                        if ttl > 0:
                            self._cache[cache_key] = (time.time(), data)

                        response_time = time.time() - start_time
                        self.request_times.append(response_time)
                        if len(self.request_times) > 100:
                            self.request_times.pop(0)

                        self.metrics.avg_response_time = sum(self.request_times) / len(self.request_times)
                        self.metrics.last_request_time = time.time()
                        return data

                    if r.status_code == 429:
                        self.metrics.rate_limited_requests += 1
                        retry_after = int(r.headers.get("Retry-After", 1))
                        delay = min(2 ** attempt, 60) + retry_after
                        self.log.warning(f"Rate limited for {path}. Sleeping {delay}s")
                        await asyncio.sleep(delay)
                        continue

                    r.raise_for_status()

                except httpx.HTTPStatusError as e:
                    if e.response is not None and e.response.status_code >= 500:
                        delay = min(2 ** attempt, 30)
                        self.log.warning(f"Server error {e.response.status_code} for {path}, retrying")
                        await asyncio.sleep(delay)
                        last_exception = e
                        continue
                    else:
                        self.metrics.failed_requests += 1
                        self.log.error(f"HTTP error for {path}: {e}")
                        raise BinanceRequestError(f"HTTP error: {e}")

                except (httpx.RequestError, asyncio.TimeoutError) as e:
                    last_exception = e
                    self.metrics.failed_requests += 1
                    delay = min(2 ** attempt, 60) + random.uniform(0, 0.3)
                    self.log.error(f"Request error for {path}: {e}, retrying")
                    await asyncio.sleep(delay)

            raise last_exception or BinanceRequestError(f"Max retries ({max_retries}) exceeded for {path}")

        except Exception as e:
            self.log.error(f"Request failed for {method} {path}: {str(e)}")
            raise

    async def close(self) -> None:
        """HTTP client'ı temiz bir şekilde kapat."""
        if self.client:
            try:
                await self.client.aclose()
                self.client = None
                self.log.info("HTTP client closed successfully")
            except Exception as e:
                self.log.error(f"Error closing HTTP client: {e}")