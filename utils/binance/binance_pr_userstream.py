# utils/binance/binance_pr_userstream.py
"""
UserStreamClient: user data stream endpoints (listenKey).
Works for both spot (/api/v3/userDataStream) and futures (/fapi/v1/listenKey)
"""
from typing import Any, Dict
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class UserStreamClient(BinancePrivateBase):
    """Listen key create/keepalive/close."""

    async def create_listen_key(self, futures: bool = False) -> Dict[str, Any]:
        """POST /api/v3/userDataStream or /fapi/v1/listenKey"""
        try:
            endpoint = "/fapi/v1/listenKey" if futures else "/api/v3/userDataStream"
            return await self.circuit_breaker.execute(self.http._request, "POST", endpoint, signed=True, futures=futures)
        except Exception as e:
            logger.exception("Error creating listen key")
            raise BinanceAPIError(f"Error creating listen key: {e}")

    async def keepalive_listen_key(self, listen_key: str, futures: bool = False) -> Dict[str, Any]:
        """PUT the listen key to keep alive."""
        try:
            endpoint = "/fapi/v1/listenKey" if futures else "/api/v3/userDataStream"
            params = {"listenKey": listen_key}
            return await self.circuit_breaker.execute(self.http._request, "PUT", endpoint, params=params, signed=True, futures=futures)
        except Exception as e:
            logger.exception("Error keeping listen key alive")
            raise BinanceAPIError(f"Error keeping listen key alive: {e}")

    async def close_listen_key(self, listen_key: str, futures: bool = False) -> Dict[str, Any]:
        """DELETE the listen key."""
        try:
            endpoint = "/fapi/v1/listenKey" if futures else "/api/v3/userDataStream"
            params = {"listenKey": listen_key}
            return await self.circuit_breaker.execute(self.http._request, "DELETE", endpoint, params=params, signed=True, futures=futures)
        except Exception as e:
            logger.exception("Error closing listen key")
            raise BinanceAPIError(f"Error closing listen key: {e}")
