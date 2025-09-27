# utils/binance/binance_pr_subaccount.py
"""
SubAccountClient: sub-account management endpoints.
Sub-account endpoints (/sapi/v1/sub-account/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class SubAccountClient(BinancePrivateBase):
    """Sub-account operations."""

    async def get_list(self, email: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/sub-account/list"""
        try:
            params = {"email": email} if email else {}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/sub-account/list", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting sub-account list")
            raise BinanceAPIError(f"Error getting sub-account list: {e}")

    async def create(self, sub_account_string: str) -> Dict[str, Any]:
        """POST /sapi/v1/sub-account/virtualSubAccount"""
        try:
            params = {"subAccountString": sub_account_string}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/sub-account/virtualSubAccount", params=params, signed=True)
        except Exception as e:
            logger.exception("Error creating sub-account")
            raise BinanceAPIError(f"Error creating sub-account: {e}")

    async def get_assets(self, email: str) -> Dict[str, Any]:
        """GET /sapi/v3/sub-account/assets"""
        try:
            params = {"email": email}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v3/sub-account/assets", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting sub-account assets")
            raise BinanceAPIError(f"Error getting sub-account assets: {e}")
