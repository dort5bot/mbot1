"""utils/binance/binance_a.py
Binance API aggregator - Ana toplayıcı sınıf.

Bu modül, BinancePublicAPI ve BinancePrivateAPI sınıflarını birleştirerek
tüm Binance API endpoint'lerine tek bir noktadan erişim sağlar.

Kullanım:
    from utils.binance.binance_a import BinanceAPI
    from utils.binance.binance_request import BinanceHTTPClient
    from utils.binance.binance_circuit_breaker import CircuitBreaker

    http_client = BinanceHTTPClient(api_key="...", secret_key="...")
    cb = CircuitBreaker(...)
    binance = BinanceAPI(http_client, cb)

    # Public endpoint
    server_time = await binance.public.get_server_time()
    
    # Private endpoint
    account_info = await binance.private.get_account_info()

🔧 Özellikler:
- Singleton pattern
- Async/await uyumlu
- Type hints + docstring
- Logging
- PEP8 uyumlu
"""

import logging
from typing import Optional

from .binance_request import BinanceHTTPClient
from .binance_circuit_breaker import CircuitBreaker
from .binance_public import BinancePublicAPI
from .binance_private import BinancePrivateAPI

logger = logging.getLogger(__name__)


class BinanceAPI:
    """
    Binance API aggregator sınıfı.

    Bu sınıf, hem public hem de private Binance API'lerine erişim sağlar.
    Singleton pattern kullanır.
    """

    _instance: Optional["BinanceAPI"] = None

    def __new__(cls, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> "BinanceAPI":
        """
        Singleton instance döndürür.

        Args:
            http_client: BinanceHTTPClient örneği
            circuit_breaker: CircuitBreaker örneği

        Returns:
            BinanceAPI singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(http_client, circuit_breaker)
            logger.info("✅ BinanceAPI aggregator singleton instance created")
        return cls._instance

    def _initialize(self, http_client: BinanceHTTPClient, circuit_breaker: CircuitBreaker) -> None:
        """
        Instance'ı başlat.

        Args:
            http_client: BinanceHTTPClient örneği
            circuit_breaker: CircuitBreaker örneği
        """
        self.http = http_client
        self.circuit_breaker = circuit_breaker
        
        # Public ve private API'leri oluştur
        self.public = BinancePublicAPI(http_client, circuit_breaker)
        self.private = BinancePrivateAPI(http_client, circuit_breaker)
        
        logger.info("✅ BinanceAPI aggregator initialized with public and private APIs")

    async def close(self) -> None:
        """
        HTTP client'ı kapat ve kaynakları temizle.
        """
        if hasattr(self, 'http'):
            await self.http.close()
            logger.info("✅ BinanceAPI HTTP client closed")

    def __del__(self) -> None:
        """
        Destructor - HTTP client'ı kapat.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
            else:
                loop.run_until_complete(self.close())
        except Exception:
            pass  # Ignore errors during cleanup

    # -------------------------
    # Convenience Methods
    # -------------------------
    async def ping(self) -> bool:
        """
        Binance API'ye ping at ve bağlantıyı test et.

        Returns:
            True if ping successful, False otherwise
        """
        try:
            result = await self.public.ping()
            return result == {}  # Binance ping returns empty dict on success
        except Exception as e:
            logger.warning(f"❌ Ping failed: {e}")
            return False

    async def check_api_keys(self) -> bool:
        """
        API key'lerin geçerli olup olmadığını kontrol et.

        Returns:
            True if API keys are valid, False otherwise
        """
        try:
            await self.private.get_account_info()
            return True
        except Exception as e:
            logger.warning(f"❌ API key check failed: {e}")
            return False

    async def get_balance(self, asset: Optional[str] = None, futures: bool = False) -> dict:
        """
        Hesap bakiyesini getir (spot veya futures).

        Args:
            asset: Optional asset symbol (e.g., "BTC")
            futures: If True, get futures balance

        Returns:
            Balance information
        """
        if futures:
            if asset:
                # Futures için asset bazlı bakiye
                balances = await self.private.get_futures_balance()
                for balance in balances:
                    if balance.get('asset') == asset.upper():
                        return balance
                return {}
            return await self.private.get_futures_balance()
        else:
            return await self.private.get_account_balance(asset)

    async def get_symbol_info(self, symbol: str, futures: bool = False) -> Optional[dict]:
        """
        Sembol bilgilerini getir.

        Args:
            symbol: Trading pair symbol
            futures: If True, get futures symbol info

        Returns:
            Symbol information or None if not found
        """
        try:
            if futures:
                exchange_info = await self.public.get_futures_exchange_info()
            else:
                exchange_info = await self.public.get_exchange_info()
            
            for s in exchange_info.get('symbols', []):
                if s.get('symbol') == symbol.upper():
                    return s
            return None
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    async def get_all_symbols(self, futures: bool = False) -> list:
        """
        Tüm sembolleri getir.

        Args:
            futures: If True, get futures symbols

        Returns:
            List of all symbols
        """
        if futures:
            return await self.public.get_all_futures_symbols()
        return await self.public.get_all_symbols()

    async def get_price(self, symbol: str, futures: bool = False) -> Optional[float]:
        """
        Sembolün mevcut fiyatını getir.

        Args:
            symbol: Trading pair symbol
            futures: If True, get futures price

        Returns:
            Current price or None if error
        """
        try:
            if futures:
                ticker = await self.public.get_futures_24hr_ticker(symbol)
                return float(ticker.get('lastPrice', 0))
            else:
                price_data = await self.public.get_symbol_price(symbol)
                return float(price_data.get('price', 0))
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    # -------------------------
    # Order Management Convenience
    # -------------------------
    async def create_order(self, symbol: str, side: str, order_type: str, quantity: float,
                          price: Optional[float] = None, futures: bool = False, **kwargs) -> dict:
        """
        Yeni order oluştur.

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            order_type: "LIMIT", "MARKET", etc.
            quantity: Order quantity
            price: Order price (for limit orders)
            futures: If True, create futures order
            **kwargs: Additional order parameters

        Returns:
            Order creation result
        """
        if futures:
            return await self.private.place_futures_order(
                symbol, side, order_type, quantity, price, **kwargs
            )
        else:
            return await self.private.place_order(
                symbol, side, order_type, quantity, price, **kwargs
            )

    async def cancel_order(self, symbol: str, order_id: Optional[int] = None,
                          orig_client_order_id: Optional[str] = None, futures: bool = False) -> dict:
        """
        Order iptal et.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            orig_client_order_id: Client order ID
            futures: If True, cancel futures order

        Returns:
            Cancellation result
        """
        if futures:
            return await self.private.cancel_futures_order(
                symbol, order_id, orig_client_order_id
            )
        else:
            return await self.private.cancel_order(
                symbol, order_id, orig_client_order_id
            )

    async def get_open_orders(self, symbol: Optional[str] = None, futures: bool = False) -> list:
        """
        Açık order'ları getir.

        Args:
            symbol: Optional trading pair symbol
            futures: If True, get futures orders

        Returns:
            List of open orders
        """
        if futures:
            return await self.private.get_futures_open_orders(symbol)
        else:
            return await self.private.get_open_orders(symbol)

    # -------------------------
    # Position Management (Futures)
    # -------------------------
    async def get_positions(self, symbol: Optional[str] = None) -> list:
        """
        Futures pozisyonları getir.

        Args:
            symbol: Optional trading pair symbol

        Returns:
            List of positions
        """
        positions = await self.private.get_futures_positions()
        if symbol:
            symbol_upper = symbol.upper()
            return [p for p in positions if p.get('symbol') == symbol_upper]
        return positions

    async def get_position(self, symbol: str) -> Optional[dict]:
        """
        Belirli bir sembolün futures pozisyonunu getir.

        Args:
            symbol: Trading pair symbol

        Returns:
            Position information or None if not found
        """
        positions = await self.get_positions(symbol)
        return positions[0] if positions else None

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """
        Futures kaldıraç oranını ayarla.

        Args:
            symbol: Trading pair symbol
            leverage: Leverage value

        Returns:
            Result of leverage change
        """
        return await self.private.change_futures_leverage(symbol, leverage)

    async def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        """
        Futures margin tipini ayarla.

        Args:
            symbol: Trading pair symbol
            margin_type: "ISOLATED" or "CROSSED"

        Returns:
            Result of margin type change
        """
        return await self.private.change_futures_margin_type(symbol, margin_type)

    # -------------------------
    # User Data Stream
    # -------------------------
    async def create_listen_key(self, futures: bool = False) -> str:
        """
        ListenKey oluştur.

        Args:
            futures: If True, create futures listen key

        Returns:
            Listen key
        """
        result = await self.private.create_listen_key(futures)
        return result.get('listenKey', '')

    async def keepalive_listen_key(self, listen_key: str, futures: bool = False) -> dict:
        """
        ListenKey'i yenile.

        Args:
            listen_key: Listen key to keep alive
            futures: If True, keep alive futures listen key

        Returns:
            Result of keepalive operation
        """
        return await self.private.keepalive_listen_key(listen_key, futures)

    async def close_listen_key(self, listen_key: str, futures: bool = False) -> dict:
        """
        ListenKey'i kapat.

        Args:
            listen_key: Listen key to close
            futures: If True, close futures listen key

        Returns:
            Result of close operation
        """
        return await self.private.close_listen_key(listen_key, futures)

    # -------------------------
    # Additional convenience methods
    # -------------------------
    async def get_24h_stats(self, symbol: str, futures: bool = False) -> dict:
        """
        24 saatlik istatistikleri getir.

        Args:
            symbol: Trading pair symbol
            futures: If True, get futures stats

        Returns:
            24-hour statistics
        """
        if futures:
            tickers = await self.public.get_futures_24hr_ticker(symbol)
            if isinstance(tickers, list):
                for ticker in tickers:
                    if ticker.get('symbol') == symbol.upper():
                        return ticker
                return {}
            return tickers
        else:
            return await self.public.get_all_24h_tickers(symbol)

    async def get_order_book(self, symbol: str, limit: int = 100, futures: bool = False) -> dict:
        """
        Order book'u getir.

        Args:
            symbol: Trading pair symbol
            limit: Depth limit
            futures: If True, get futures order book

        Returns:
            Order book data
        """
        if futures:
            return await self.public.get_futures_order_book(symbol, limit)
        else:
            return await self.public.get_order_book(symbol, limit)

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500, futures: bool = False) -> list:
        """
        Kline/candlestick verilerini getir.

        Args:
            symbol: Trading pair symbol
            interval: Kline interval
            limit: Number of klines
            futures: If True, get futures klines

        Returns:
            List of klines
        """
        if futures:
            return await self.public.get_futures_klines(symbol, interval, limit)
        else:
            return await self.public.get_klines(symbol, interval, limit)

    async def get_mark_price(self, symbol: str) -> dict:
        """
        Futures mark price'ı getir.

        Args:
            symbol: Trading pair symbol

        Returns:
            Mark price data
        """
        return await self.public.get_futures_mark_price(symbol)

    async def get_funding_rate_history(self, symbol: str, limit: int = 100) -> list:
        """
        Funding rate geçmişini getir.

        Args:
            symbol: Trading pair symbol
            limit: Number of records

        Returns:
            Funding rate history
        """
        return await self.public.get_futures_funding_rate_history(symbol, limit)

    async def get_open_interest(self, symbol: str) -> dict:
        """
        Open interest'i getir.

        Args:
            symbol: Trading pair symbol

        Returns:
            Open interest data
        """
        return await self.public.get_futures_open_interest(symbol)

    # -------------------------
    # Wallet operations
    # -------------------------
    async def get_deposit_address(self, coin: str, network: Optional[str] = None) -> dict:
        """
        Deposit adresi getir.

        Args:
            coin: Coin symbol
            network: Network name

        Returns:
            Deposit address information
        """
        return await self.private.get_deposit_address(coin, network)

    async def get_deposit_history(self, coin: Optional[str] = None, status: Optional[int] = None,
                                 start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """
        Deposit geçmişini getir.

        Args:
            coin: Coin symbol
            status: Deposit status
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            Deposit history
        """
        return await self.private.get_deposit_history(coin, status, start_time, end_time)

    async def get_withdraw_history(self, coin: Optional[str] = None, status: Optional[int] = None,
                                  start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """
        Withdrawal geçmişini getir.

        Args:
            coin: Coin symbol
            status: Withdrawal status
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            Withdrawal history
        """
        return await self.private.get_withdraw_history(coin, status, start_time, end_time)

    async def withdraw_crypto(self, coin: str, address: str, amount: float,
                             network: Optional[str] = None, address_tag: Optional[str] = None) -> dict:
        """
        Cryptocurrency withdraw et.

        Args:
            coin: Coin symbol
            address: Withdrawal address
            amount: Amount to withdraw
            network: Network name
            address_tag: Address tag

        Returns:
            Withdrawal result
        """
        return await self.private.withdraw(coin, address, amount, network, address_tag)

    # -------------------------
    # Staking operations
    # -------------------------
    async def get_staking_products(self, product: str = "STAKING", asset: Optional[str] = None) -> list:
        """
        Staking ürünlerini getir.

        Args:
            product: Product type
            asset: Asset symbol

        Returns:
            List of staking products
        """
        return await self.private.get_staking_product_list(product, asset)

    async def stake(self, product: str, product_id: str, amount: float) -> dict:
        """
        Varlık stake et.

        Args:
            product: Product type
            product_id: Product ID
            amount: Amount to stake

        Returns:
            Staking result
        """
        return await self.private.stake_asset(product, product_id, amount)

    async def unstake(self, product: str, product_id: str, position_id: Optional[str] = None,
                     amount: Optional[float] = None) -> dict:
        """
        Varlık unstake et.

        Args:
            product: Product type
            product_id: Product ID
            position_id: Position ID
            amount: Amount to unstake

        Returns:
            Unstaking result
        """
        return await self.private.unstake_asset(product, product_id, position_id, amount)

    async def get_staking_history(self, product: str, txn_type: str, asset: Optional[str] = None,
                                 start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """
        Staking geçmişini getir.

        Args:
            product: Product type
            txn_type: Transaction type
            asset: Asset symbol
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            Staking history
        """
        return await self.private.get_staking_history(product, txn_type, asset, start_time, end_time)

    # -------------------------
    # Savings operations
    # -------------------------
    async def get_savings_products(self, product_type: str = "ACTIVITY", asset: Optional[str] = None) -> list:
        """
        Savings ürünlerini getir.

        Args:
            product_type: Product type
            asset: Asset symbol

        Returns:
            List of savings products
        """
        return await self.private.get_savings_product_list(product_type, asset)

    async def purchase_savings(self, product_id: str, amount: float) -> dict:
        """
        Savings ürünü satın al.

        Args:
            product_id: Product ID
            amount: Amount to purchase

        Returns:
            Purchase result
        """
        return await self.private.purchase_savings_product(product_id, amount)

    async def get_savings_balance(self, asset: Optional[str] = None) -> dict:
        """
        Savings bakiyesini getir.

        Args:
            asset: Asset symbol

        Returns:
            Savings balance
        """
        return await self.private.get_savings_balance(asset)

    # -------------------------
    # Utility methods
    # -------------------------
    async def health_check(self) -> dict:
        """
        Sistem sağlık durumunu kontrol et.

        Returns:
            Health status information
        """
        health = {
            'ping': await self.ping(),
            'api_keys_valid': await self.check_api_keys(),
            'timestamp': None,
            'server_time': None
        }

        try:
            server_time = await self.public.get_server_time()
            health['timestamp'] = server_time.get('serverTime')
            health['server_time'] = server_time
        except Exception as e:
            health['timestamp'] = f"Error: {e}"

        return health

    async def get_system_status(self) -> dict:
        """
        Sistem durumunu getir.

        Returns:
            System status information
        """
        try:
            # Bu endpoint Binance'de mevcut olmayabilir, alternatif implementasyon
            health = await self.health_check()
            exchange_info = await self.public.get_exchange_info()
            
            return {
                'status': 'normal' if health['ping'] else 'degraded',
                'ping': health['ping'],
                'api_keys_valid': health['api_keys_valid'],
                'symbols_count': len(exchange_info.get('symbols', [])),
                'server_time': health['server_time']
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }