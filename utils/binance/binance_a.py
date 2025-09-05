"""utils/binance/binance_a.py
Binance API ana aggregator - tek giriş noktası.

Bu modül Binance API'sine erişim için merkezi bir istemci sınıfı sunar.
Alt modülleri birleştirir ve hem public hem private endpointlere
tek sınıf üzerinden erişim imkanı sağlar.

Gerekli bileşenler:
- BinanceHTTPClient (.binance_request)
- CircuitBreaker (.binance_circuit_breaker)
- BinancePublicAPI (.binance_public)
- BinancePrivateAPI (.binance_private)
- BinanceWebSocketManager (.binance_websocket)
- Yardımcı fonksiyonlar/metrikler vb.

Not: Private endpoint wrapper'ları burada eklenmiştir (spot/futures/margin/staking/listenKey).
"""

import os
import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .binance_request import BinanceHTTPClient
from .binance_public import BinancePublicAPI
from .binance_private import BinancePrivateAPI
from .binance_websocket import BinanceWebSocketManager
from .binance_circuit_breaker import CircuitBreaker
from .binance_utils import klines_to_dataframe
from .binance_exceptions import BinanceAPIError
from .binance_metrics import AdvancedMetrics
from config import get_config

LOG = logging.getLogger("binance_a")
LOG.setLevel(logging.INFO)


class BinanceClient:
    """Binance API'sine erişim için ana istemci sınıfı (Singleton)

    Hem public hem private endpoint'lere kolay erişim sağlayan wrapper'lar içerir.
    """

    _instance: Optional["BinanceClient"] = None

    def __new__(cls, *args, **kwargs) -> "BinanceClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        config: Any = None,
        http_client: Optional[BinanceHTTPClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.secret_key = secret_key or os.getenv("BINANCE_API_SECRET")
        self.config = config or get_config()

        # HTTP Client (API key/secret burada set edilebilir)
        self.http = http_client or BinanceHTTPClient(self.api_key, self.secret_key, self.config)

        # Circuit Breaker
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=self.config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=self.config.CIRCUIT_BREAKER_RESET_TIMEOUT,
            name="binance_main",
        )

        # API Modülleri
        self.public = BinancePublicAPI(self.http, self.circuit_breaker)
        self.private = BinancePrivateAPI(self.http, self.circuit_breaker)

        # WebSocket Manager (futures/ws için kullanılabilir)
        self.ws_manager = BinanceWebSocketManager(secret_key=self.secret_key)

        # Ek metrikler
        self.metrics = AdvancedMetrics()

        self._initialized = True
        LOG.info("✅ BinanceClient initialized successfully.")

    # --------------------------
    # PUBLIC WRAPPERS
    # --------------------------
    async def get_server_time(self) -> Dict[str, Any]:
        return await self.public.get_server_time()

    async def ping(self) -> Dict[str, Any]:
        return await self.public.ping()

    async def get_exchange_info(self) -> Dict[str, Any]:
        return await self.public.get_exchange_info()

    async def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        return await self.public.get_symbol_price(symbol)

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        return await self.public.get_order_book(symbol, limit)

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        return await self.public.get_recent_trades(symbol, limit)

    async def get_klines(
        self, symbol: str, interval: str = "1m", limit: int = 500
    ) -> List[List[Union[str, float, int]]]:
        return await self.public.get_klines(symbol, interval, limit)

    async def get_all_24h_tickers(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return await self.public.get_all_24h_tickers(symbol)

    async def get_all_symbols(self) -> List[str]:
        return await self.public.get_all_symbols()

    async def get_book_ticker(
        self, symbol: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        return await self.public.get_book_ticker(symbol)

    async def get_all_book_tickers(self) -> List[Dict[str, Any]]:
        return await self.public.get_all_book_tickers()

    async def get_avg_price(self, symbol: str) -> Dict[str, Any]:
        return await self.public.get_avg_price(symbol)

    async def get_agg_trades(
        self,
        symbol: str,
        from_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return await self.public.get_agg_trades(symbol, from_id, start_time, end_time, limit)

    async def get_historical_trades(
        self, symbol: str, limit: int = 500, from_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return await self.public.get_historical_trades(symbol, limit, from_id)

    async def get_ui_klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        return await self.public.get_ui_klines(symbol, interval, start_time, end_time, limit)

    async def symbol_exists(self, symbol: str) -> bool:
        return await self.public.symbol_exists(symbol)

    # --------------------------
    # PRIVATE WRAPPERS (Spot / Futures / Margin / Staking / ListenKey)
    # --------------------------
    # Spot Account & Orders
    async def get_account_info(self) -> Dict[str, Any]:
        """Spot hesap bilgilerini getir."""
        return await self.private.get_account_info()

    async def get_account_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Hesap bakiyesi veya tek varlık bakiyesi getir."""
        return await self.private.get_account_balance(asset)

    async def place_order(
        self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Spot piyasada yeni order oluştur."""
        return await self.private.place_order(symbol, side, type_, quantity, price)

    async def cancel_order(
        self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Spot order iptal et."""
        return await self.private.cancel_order(symbol, order_id, orig_client_order_id)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Açık spot order'ları getir."""
        return await self.private.get_open_orders(symbol)

    async def get_order_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Spot order geçmişini getir."""
        return await self.private.get_order_history(symbol, limit)

    # Futures Account
    async def get_futures_account_info(self) -> Dict[str, Any]:
        """Futures hesap bilgilerini getir (USDT-margined/perpetual)."""
        return await self.private.get_futures_account_info()

    async def get_futures_positions(self) -> List[Dict[str, Any]]:
        """Futures açık pozisyonlarını getir."""
        return await self.private.get_futures_positions()

    async def place_futures_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """Futures piyasada yeni order oluştur."""
        return await self.private.place_futures_order(symbol, side, type_, quantity, price, reduce_only)

    async def get_funding_rate(self, symbol: str, limit: int = 1) -> List[Dict[str, Any]]:
        """Funding rate (kısa dönem geçmişi) bilgilerini getir."""
        return await self.private.get_funding_rate(symbol, limit)

    # Margin Trading
    async def get_margin_account_info(self) -> Dict[str, Any]:
        """Margin hesap bilgilerini getir."""
        return await self.private.get_margin_account_info()

    async def place_margin_order(
        self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Margin piyasada yeni order oluştur."""
        return await self.private.place_margin_order(symbol, side, type_, quantity, price)

    async def repay_margin_loan(self, asset: str, amount: float) -> Dict[str, Any]:
        """Margin borcunu öde."""
        return await self.private.repay_margin_loan(asset, amount)

    # Staking (Savings / Earn benzeri private endpoints)
    async def get_staking_products(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking/earn ürün listesini getir."""
        return await self.private.get_staking_products(product)

    async def stake_product(self, product: str, product_id: str, amount: float) -> Dict[str, Any]:
        """Belirtilen staking ürününe stake yap."""
        return await self.private.stake_product(product, product_id, amount)

    async def get_staking_history(self, product: str = "STAKING") -> List[Dict[str, Any]]:
        """Staking geçmiş kayıtlarını getir."""
        return await self.private.get_staking_history(product)

    # User Data Stream (ListenKey)
    async def create_listen_key(self) -> str:
        """Spot için listenKey oluşturur (websocket user data stream)."""
        return await self.private.create_listen_key()

    async def keepalive_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey'i keepalive (uzatma)."""
        return await self.private.keepalive_listen_key(listen_key)

    async def delete_listen_key(self, listen_key: str) -> Dict[str, Any]:
        """ListenKey siler."""
        return await self.private.delete_listen_key(listen_key)

    # --------------------------
    # Helpers
    # --------------------------
    async def klines_to_df(self, symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
        """Kline verilerini DataFrame'e dönüştürür."""
        klines = await self.get_klines(symbol, interval, limit)
        return klines_to_dataframe(klines)

    # --------------------------
    # Convenience / helper wrappers - future additions
    # --------------------------
    # #future: buraya pozisyon özetleri, PnL hesapları, aggregated metrics vb. eklenebilir.
    # Örnek:
    # async def get_account_overview(self) -> Dict[str, Any]:
    #     """Spot + Futures + Margin üzerinden bir hesap özeti döndürür (farketmelere dikkat)."""
    #     spot = await self.get_account_info()
    #     futures = await self.get_futures_account_info()
    #     margin = await self.get_margin_account_info()
    #     # ...aggregate ve normalize et
    #     return {"spot": spot, "futures": futures, "margin": margin}
