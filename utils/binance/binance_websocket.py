"""
WebSocket client for Binance API.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Set
import aiohttp
import websockets

from .binance_constants import BASE_URL, FUTURES_URL, WS_STREAMS
from .binance_exceptions import BinanceWebSocketError
from .binance_utils import generate_signature

logger = logging.getLogger(__name__)


class BinanceWebSocketManager:
    """
    WebSocket manager for Binance API streams.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        testnet: bool = False
    ):
        """
        Initialize WebSocket manager.
        
        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            testnet: Whether to use testnet
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        
        self.base_url = "wss://testnet.binance.vision" if testnet else "wss://stream.binance.com:9443"
        self.futures_url = "wss://stream.binancefuture.com" if testnet else "wss://fstream.binance.com"
        
        self.connections: Dict[str, Any] = {}
        self.subscriptions: Dict[str, Set[str]] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.listen_keys: Dict[str, str] = {}
        
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
        logger.info("✅ BinanceWebSocketManager initialized")
    
    async def connect(
        self,
        streams: List[str],
        callback: Callable,
        futures: bool = False
    ) -> str:
        """
        Connect to WebSocket streams.
        
        Args:
            streams: List of streams to subscribe to
            callback: Callback function for messages
            futures: Whether to use futures streams
            
        Returns:
            Connection ID
        """
        url = self.futures_url if futures else self.base_url
        stream_param = '/'.join([f"{s}@${s}" for s in streams])
        ws_url = f"{url}/stream?streams={stream_param}"
        
        connection_id = f"{'futures_' if futures else 'spot_'}{int(time.time() * 1000)}"
        
        self.connections[connection_id] = {
            'url': ws_url,
            'streams': streams,
            'callback': callback,
            'futures': futures,
            'running': True
        }
        
        # Start connection task
        asyncio.create_task(self._run_connection(connection_id))
        
        logger.info(f"✅ WebSocket connection {connection_id} started for {len(streams)} streams")
        return connection_id
    
    async def _run_connection(self, connection_id: str) -> None:
        """Main WebSocket connection loop."""
        connection = self.connections[connection_id]
        
        while connection['running']:
            try:
                async with websockets.connect(connection['url']) as ws:
                    logger.info(f"🔗 WebSocket {connection_id} connected")
                    self.reconnect_delay = 1
                    
                    # Main message loop
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            await connection['callback'](data)
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ JSON decode error: {e}")
                        except Exception as e:
                            logger.error(f"❌ Callback error: {e}")
                            
            except Exception as e:
                logger.error(f"❌ WebSocket {connection_id} error: {e}")
                
                # Exponential backoff for reconnection
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect WebSocket connection.
        
        Args:
            connection_id: Connection ID to disconnect
        """
        if connection_id in self.connections:
            self.connections[connection_id]['running'] = False
            del self.connections[connection_id]
            logger.info(f"✅ WebSocket {connection_id} disconnected")
    
    async def subscribe_user_data(self, callback: Callable, futures: bool = False) -> str:
        """
        Subscribe to user data stream.
        
        Args:
            callback: Callback function for messages
            futures: Whether to use futures user data
            
        Returns:
            Listen key
        """
        # Get listen key from REST API
        listen_key = await self._get_listen_key(futures)
        
        # Create user data connection
        url = self.futures_url if futures else self.base_url
        ws_url = f"{url}/ws/{listen_key}"
        
        connection_id = f"user_data_{'futures_' if futures else 'spot_'}{int(time.time() * 1000)}"
        
        self.connections[connection_id] = {
            'url': ws_url,
            'streams': ['userData'],
            'callback': callback,
            'futures': futures,
            'running': True,
            'listen_key': listen_key
        }
        
        # Start keepalive task
        asyncio.create_task(self._keepalive_listen_key(listen_key, futures))
        
        # Start connection
        asyncio.create_task(self._run_connection(connection_id))
        
        logger.info(f"✅ User data WebSocket {connection_id} started")
        return connection_id
    
    async def _get_listen_key(self, futures: bool = False) -> str:
        """
        Get listen key from REST API.
        
        Args:
            futures: Whether to get futures listen key
            
        Returns:
            Listen key
        """
        endpoint = '/fapi/v1/listenKey' if futures else '/api/v3/userDataStream'
        url = (FUTURES_URL if futures else BASE_URL) + endpoint
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['listenKey']
                else:
                    raise BinanceWebSocketError(f"Failed to get listen key: {response.status}")
    
    async def _keepalive_listen_key(self, listen_key: str, futures: bool = False) -> None:
        """
        Keep listen key alive.
        
        Args:
            listen_key: Listen key to keep alive
            futures: Whether it's a futures listen key
        """
        endpoint = '/fapi/v1/listenKey' if futures else '/api/v3/userDataStream'
        url = (FUTURES_URL if futures else BASE_URL) + endpoint
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.put(url, headers=headers, 
                                         params={'listenKey': listen_key}) as response:
                        if response.status != 200:
                            logger.warning(f"⚠️ Listen key keepalive failed: {response.status}")
                
                # Keepalive every 30 minutes (Binance requires every 60 minutes)
                await asyncio.sleep(1800)  # 30 minutes
                
            except Exception as e:
                logger.error(f"❌ Listen key keepalive error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute
    
    async def close_all(self) -> None:
        """Close all WebSocket connections."""
        for connection_id in list(self.connections.keys()):
            await self.disconnect(connection_id)
        
        logger.info("✅ All WebSocket connections closed")
    
    # Convenience methods for common streams
    async def subscribe_ticker(
        self,
        symbol: str,
        callback: Callable,
        futures: bool = False,
        interval: str = '1s'
    ) -> str:
        """
        Subscribe to ticker stream.
        
        Args:
            symbol: Trading symbol
            callback: Callback function
            futures: Whether to use futures
            interval: Update interval ('1s' or '3s')
            
        Returns:
            Connection ID
        """
        stream = f"{symbol.lower()}@ticker_{interval}"
        return await self.connect([stream], callback, futures)
    
    async def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        callback: Callable,
        futures: bool = False
    ) -> str:
        """
        Subscribe to kline stream.
        
        Args:
            symbol: Trading symbol
            interval: Kline interval
            callback: Callback function
            futures: Whether to use futures
            
        Returns:
            Connection ID
        """
        stream = f"{symbol.lower()}@kline_{interval}"
        return await self.connect([stream], callback, futures)
    
    async def subscribe_depth(
        self,
        symbol: str,
        callback: Callable,
        futures: bool = False,
        levels: int = 20
    ) -> str:
        """
        Subscribe to depth stream.
        
        Args:
            symbol: Trading symbol
            callback: Callback function
            futures: Whether to use futures
            levels: Depth levels (5, 10, 20)
            
        Returns:
            Connection ID
        """
        stream = f"{symbol.lower()}@depth{levels}@100ms"
        return await self.connect([stream], callback, futures)
    
    async def subscribe_agg_trade(
        self,
        symbol: str,
        callback: Callable,
        futures: bool = False
    ) -> str:
        """
        Subscribe to aggregated trade stream.
        
        Args:
            symbol: Trading symbol
            callback: Callback function
            futures: Whether to use futures
            
        Returns:
            Connection ID
        """
        stream = f"{symbol.lower()}@aggTrade"
        return await self.connect([stream], callback, futures)
    
    def is_connected(self, connection_id: str) -> bool:
        """
        Check if connection is active.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            True if connected
        """
        return connection_id in self.connections and self.connections[connection_id]['running']
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_all()