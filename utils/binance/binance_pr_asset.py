# utils/binance/binance_pr_asset.py
"""
AssetClient: deposit/withdraw/dust + asset endpoints.
Deposit/withdraw endpoints (/sapi/v1/capital/*, /sapi/v1/asset/*).
"""
from typing import Any, Dict, List, Optional
import logging

from .binance_pr_base import BinancePrivateBase
from .binance_exceptions import BinanceAPIError

logger = logging.getLogger(__name__)


class AssetClient(BinancePrivateBase):
    """Deposit, withdraw, dust conversion operations."""

    async def get_dust_log(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict[str, Any]:
        """GET /sapi/v1/asset/dribblet"""
        try:
            params = {}
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/asset/dribblet", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting dust log")
            raise BinanceAPIError(f"Error getting dust log: {e}")

    async def convert_dust(self, assets: List[str]) -> Dict[str, Any]:
        """POST /sapi/v1/asset/dust - convert micro-assets to BNB"""
        try:
            params = {"asset": ",".join([a.upper() for a in assets])}
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/asset/dust", params=params, signed=True)
        except Exception as e:
            logger.exception("Error converting dust")
            raise BinanceAPIError(f"Error converting dust: {e}")

    async def get_deposit_address(self, coin: str, network: Optional[str] = None) -> Dict[str, Any]:
        """GET /sapi/v1/capital/deposit/address"""
        try:
            params = {"coin": coin.upper()}
            if network:
                params["network"] = network
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/capital/deposit/address", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting deposit address")
            raise BinanceAPIError(f"Error getting deposit address for {coin}: {e}")

    async def get_deposit_history(self, coin: Optional[str] = None, status: Optional[int] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/capital/deposit/hisrec"""
        try:
            params = {}
            if coin:
                params["coin"] = coin.upper()
            if status is not None:
                params["status"] = status
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/capital/deposit/hisrec", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting deposit history")
            raise BinanceAPIError(f"Error getting deposit history: {e}")

    async def get_withdraw_history(self, coin: Optional[str] = None, status: Optional[int] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """GET /sapi/v1/capital/withdraw/history"""
        try:
            params = {}
            if coin:
                params["coin"] = coin.upper()
            if status is not None:
                params["status"] = status
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            return await self.circuit_breaker.execute(self.http._request, "GET", "/sapi/v1/capital/withdraw/history", params=params, signed=True)
        except Exception as e:
            logger.exception("Error getting withdraw history")
            raise BinanceAPIError(f"Error getting withdraw history: {e}")

    async def withdraw(self, coin: str, address: str, amount: float, network: Optional[str] = None, address_tag: Optional[str] = None) -> Dict[str, Any]:
        """POST /sapi/v1/capital/withdraw/apply"""
        try:
            params = {"coin": coin.upper(), "address": address, "amount": amount}
            if network:
                params["network"] = network
            if address_tag:
                params["addressTag"] = address_tag
            return await self.circuit_breaker.execute(self.http._request, "POST", "/sapi/v1/capital/withdraw/apply", params=params, signed=True)
        except Exception as e:
            logger.exception("Error withdrawing asset")
            raise BinanceAPIError(f"Error withdrawing {coin}: {e}")
