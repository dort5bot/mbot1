# utils/binance/binance_pr_savings.py
"""
SavingsClient: daily/flexible savings endpoints.
Savings / Lending endpoints (flexible/locked) (/sapi/v1/lending/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class SavingsClient(BinancePrivateBase):
    """Savings / lending operations."""

    async def get_product_list(self, product_type: str = "ACTIVITY", asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/lending/daily/product/list"""
        try:
            params: Dict[str, Any] = {"type": product_type}
            if asset:
                params["asset"] = asset.upper()
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/lending/daily/product/list", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting savings product list")
            raise BinanceAPIError(f"Error getting savings product list: {e}")

    async def purchase_product(self, product_id: str, amount: float) -> Dict[str, Any]:
        """POST /sapi/v1/lending/daily/purchase"""
        try:
            params = {"productId": product_id, "amount": amount}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/lending/daily/purchase", params=params, signed=True)
        except Exception as e:
            logger.exception("Error purchasing savings product")
            raise BinanceAPIError(f"Error purchasing savings product: {e}")

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """GET /sapi/v1/lending/daily/token/position"""
        try:
            params = {"asset": asset.upper()} if asset else {}
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/lending/daily/token/position", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting savings balance")
            raise BinanceAPIError(f"Error getting savings balance: {e}")
