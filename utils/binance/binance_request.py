"""
HTTP client for Binance API requests.
"""

import aiohttp
import asyncio
import time
import logging
import hashlib
import hmac
import urllib.parse
from typing import Dict, List, Any, Optional, Union
from .binance_constants import BASE_URL, FUTURES_URL, DEFAULT_CONFIG
from .binance_exceptions import (
    BinanceAPIError, BinanceRequestError, BinanceRateLimitError,
    BinanceAuthenticationError, BinanceTimeoutError
)
from .binance_metrics import metrics

logger = logging.getLogger(__name__)


class BinanceHTTPClient:
    """
    Async HTTP client for Binance API with retry logic and error handling.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """
        Initialize HTTP client.
        
        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            config: Configuration dictionary
            session: Existing aiohttp session (optional)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._session = session or aiohttp.ClientSession(   # ✅ buraya eklendi
            timeout=aiohttp.ClientTimeout(total=(config or DEFAULT_CONFIG)["timeout"]),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=20)
        )
        self._last_request_time = 0
        self._min_request_interval = 1.0 / 10  # 10 requests per second default
        self._weight_used = 0
        self._weight_reset_time = time.time() + 60  # Reset in 1 minute
        
        logger.info("✅ BinanceHTTPClient initialized")
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("✅ BinanceHTTPClient session closed")

    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config["timeout"]),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=20)
            )
        return self._session
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("✅ BinanceHTTPClient session closed")
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for private requests.
        
        Args:
            params: Request parameters
            
        Returns:
            Signature string
        """
        if not self.secret_key:
            raise BinanceAuthenticationError("Secret key required for signed requests")
        
        query_string = urllib.parse.urlencode(params)
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Add authentication headers to request.
        
        Args:
            headers: Existing headers
            
        Returns:
            Updated headers with authentication
        """
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        return headers
    
    async def _rate_limit(self) -> None:
        """
        Implement rate limiting between requests.
        """
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        
        self._last_request_time = time.time()
    
    async def _handle_rate_limit(self, response_headers: Dict[str, str]) -> None:
        """
        Handle rate limit information from response headers.
        
        Args:
            response_headers: Response headers from Binance
        """
        weight = response_headers.get('X-MBX-USED-WEIGHT', '0')
        order_count = response_headers.get('X-MBX-ORDER-COUNT-10S', '0')
        
        try:
            weight_used = int(weight)
            await metrics.record_rate_limit(weight_used)
            self._weight_used += weight_used
        except ValueError:
            pass
        
        # Reset weight counter every minute
        if time.time() > self._weight_reset_time:
            self._weight_used = 0
            self._weight_reset_time = time.time() + 60
            await metrics.reset_rate_limit()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False,
        retries: int = None
    ) -> Any:
        """
        Make HTTP request to Binance API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature
            futures: Whether to use futures API
            retries: Number of retries (overrides config)
            
        Returns:
            API response data
            
        Raises:
            BinanceAPIError: For API errors
            BinanceRequestError: For request errors
        """
        retries = retries or self.config["max_retries"]
        params = params or {}
        
        # Prepare request
        base_url = FUTURES_URL if futures else BASE_URL
        url = f"{base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            if 'recvWindow' not in params:
                params['recvWindow'] = self.config["recv_window"]
            params['signature'] = self._generate_signature(params)
        
        headers = self._add_auth_headers(headers)
        
        # Make request with retries
        for attempt in range(retries + 1):
            try:
                await self._rate_limit()
                
                session = await self._get_session()
                start_time = time.time()
                
                async with session.request(
                    method=method,
                    url=url,
                    params=params if method == 'GET' else None,
                    data=params if method != 'GET' else None,
                    headers=headers
                ) as response:
                    response_time = time.time() - start_time
                    
                    # Handle rate limits
                    await self._handle_rate_limit(response.headers)
                    
                    # Parse response
                    if response.status == 200:
                        data = await response.json()
                        await metrics.record_request(True, response_time)
                        return data
                    
                    # Handle errors
                    error_data = await response.text()
                    await self._handle_error(response.status, error_data, response_time)
                    
            except asyncio.TimeoutError:
                error_msg = f"Request timeout after {self.config['timeout']}s"
                await metrics.record_request(False, self.config['timeout'], "timeout")
                if attempt == retries:
                    raise BinanceTimeoutError(error_msg)
                
            except aiohttp.ClientError as e:
                error_msg = f"HTTP client error: {str(e)}"
                await metrics.record_request(False, 0, "connection_error")
                if attempt == retries:
                    raise BinanceRequestError(error_msg)
            
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                await metrics.record_request(False, 0, "unexpected_error")
                if attempt == retries:
                    raise BinanceRequestError(error_msg)
            
            # Exponential backoff for retries
            if attempt < retries:
                delay = self.config["retry_delay"] * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{retries} after {delay}s delay")
                await asyncio.sleep(delay)
    
    async def _handle_error(self, status_code: int, error_data: str, response_time: float) -> None:
        """
        Handle API error responses.
        
        Args:
            status_code: HTTP status code
            error_data: Error response data
            response_time: Response time in seconds
        """
        try:
            error_json = await asyncio.get_event_loop().run_in_executor(
                None, lambda: eval(error_data) if error_data else {}
            )
            error_code = error_json.get('code', -1)
            error_msg = error_json.get('msg', 'Unknown error')
            
            await metrics.record_request(False, response_time, f"api_error_{error_code}")
            
            if status_code == 429:
                raise BinanceRateLimitError(error_msg, error_code, error_json)
            elif status_code == 401:
                raise BinanceAuthenticationError(error_msg, error_code, error_json)
            elif status_code >= 400:
                raise BinanceAPIError(error_msg, error_code, error_json)
            else:
                raise BinanceRequestError(f"HTTP {status_code}: {error_msg}")
                
        except (ValueError, SyntaxError):
            await metrics.record_request(False, response_time, "invalid_response")
            raise BinanceRequestError(f"HTTP {status_code}: Invalid response: {error_data}")
    
    # Public methods for different request types
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False
    ) -> Any:
        """Make GET request."""
        return await self._request('GET', endpoint, params, signed, futures)
    
    async def post(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False
    ) -> Any:
        """Make POST request."""
        return await self._request('POST', endpoint, params, signed, futures)
    
    async def put(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False
    ) -> Any:
        """Make PUT request."""
        return await self._request('PUT', endpoint, params, signed, futures)
    
    async def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        futures: bool = False
    ) -> Any:
        """Make DELETE request."""
        return await self._request('DELETE', endpoint, params, signed, futures)
    
    def get_weight_usage(self) -> int:
        """Get current weight usage."""
        return self._weight_used
    
    def get_weight_remaining(self) -> int:
        """Get remaining weight until reset."""
        return 1200 - self._weight_used  # Binance default weight limit
    
    async def health_check(self) -> bool:
        """Check if API is reachable."""
        try:
            await self.get('/api/v3/ping')
            return True
        except Exception:
            return False
