# utils/binance/binance_pr_mining.py
"""
MiningClient: mining endpoints (sapi mining).

Mining endpoints (/sapi/v1/mining/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class MiningClient(BinancePrivateBase):
    """Mining operations."""

    async def get_earnings_list(self, algo: str, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/mining/payment/list"""
        try:
            params: Dict[str, Any] = {"algo": algo}
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/mining/payment/list", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting mining earnings list")
            raise BinanceAPIError(f"Error getting mining earnings: {e}")

    async def get_account_list(self, algo: str) -> List[Dict[str, Any]]:
        """GET /sapi/v1/mining/worker/list"""
        try:
            params = {"algo": algo}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/mining/worker/list", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting mining account list")
            raise BinanceAPIError(f"Error getting mining account list: {e}")
