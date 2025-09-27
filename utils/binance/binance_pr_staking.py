# utils/binance/binance_pr_staking.py
"""
StakingClient: staking endpoints (sapi staking).
Staking endpoints (/sapi/v1/staking/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class StakingClient(BinancePrivateBase):
    """Staking operations."""

    async def get_product_list(self, product: str = "STAKING", asset: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/staking/productList"""
        try:
            params: Dict[str, Any] = {"product": product}
            if asset:
                params["asset"] = asset.upper()
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/staking/productList", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting staking products")
            raise BinanceAPIError(f"Error getting staking product list: {e}")

    async def stake_asset(self, product: str, product_id: str, amount: float) -> Dict[str, Any]:
        """POST /sapi/v1/staking/purchase"""
        try:
            params = {"product": product, "productId": product_id, "amount": amount}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/staking/purchase", params=params, signed=True)
        except Exception as e:
            logger.exception("Error staking asset")
            raise BinanceAPIError(f"Error staking asset: {e}")

    async def unstake_asset(self, product: str, product_id: str, position_id: Optional[str] = None, amount: Optional[float] = None) -> Dict[str, Any]:
        """POST /sapi/v1/staking/redeem"""
        try:
            params: Dict[str, Any] = {"product": product, "productId": product_id}
            if position_id:
                params["positionId"] = position_id
            if amount is not None:
                params["amount"] = amount
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/staking/redeem", params=params, signed=True)
        except Exception as e:
            logger.exception("Error unstaking asset")
            raise BinanceAPIError(f"Error unstaking asset: {e}")

    async def get_history(self, product: str, txn_type: str, asset: Optional[str] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/staking/stakingRecord"""
        try:
            params: Dict[str, Any] = {"product": product, "txnType": txn_type}
            if asset:
                params["asset"] = asset.upper()
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/staking/stakingRecord", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting staking history")
            raise BinanceAPIError(f"Error getting staking history: {e}")
