"""Binance WebSocket yönetimi."""

import asyncio
import json
import time
import logging
from typing import Any, Dict, List, Callable, Set
from collections import defaultdict
from contextlib import asynccontextmanager
import websockets

from .binance_metrics import WSMetrics
from .binance_exceptions import BinanceWebSocketError

class BinanceWebSocketManager:
    """Binance WebSocket bağlantılarını yöneten sınıf."""
    
    def __init__(self, config: Any):
        self.config = config
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.metrics = WSMetrics()
        self._running = True
        self._message_times: List[float] = []
        self._tasks: Set[asyncio.Task] = set()
        self.log = logging.getLogger(__name__)
        self.log.info("WebSocket Manager initialized")

    @asynccontextmanager
    async def websocket_connection(self, stream_name: str):
        """WebSocket bağlantısı için context manager."""
        try:
            url = f"wss://stream.binance.com:9443/ws/{stream_name}"
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                yield ws
        except Exception as e:
            self.metrics.failed_connections += 1
            self.log.error(f"WebSocket connection failed for {stream_name}: {e}")
            raise BinanceWebSocketError(f"WebSocket connection failed: {e}")

    async def _listen_stream(self, stream_name: str) -> None:
        """WebSocket döngüsü."""
        while self._running:
            try:
                async with self.websocket_connection(stream_name) as ws:
                    self.connections[stream_name] = ws
                    self.log.info(f"WS connected: {stream_name}")
                    self.metrics.total_connections += 1
                    
                    async for msg in ws:
                        self.metrics.messages_received += 1
                        self._message_times.append(time.time())
                        
                        if len(self._message_times) > 100:
                            self._message_times.pop(0)
                        
                        try:
                            data = json.loads(msg)
                        except Exception as e:
                            self.log.error(f"Failed to parse WS message ({stream_name}): {e}")
                            continue
                        
                        for cb in list(self.callbacks.get(stream_name, [])):
                            try:
                                if asyncio.iscoroutinefunction(cb):
                                    await cb(data)
                                else:
                                    cb(data)
                            except Exception as e:
                                self.log.error(f"Callback error for {stream_name}: {e}")
            
            except Exception as e:
                self.metrics.failed_connections += 1
                self.log.warning(f"WS reconnect {stream_name} in {self.config.WS_RECONNECT_DELAY}s: {e}")
                await asyncio.sleep(self.config.WS_RECONNECT_DELAY)

    async def subscribe(self, stream_name: str, callback: Callable[[Any], Any]) -> None:
        """Yeni bir WebSocket stream'ine subscribe ol."""
        if stream_name not in self.connections:
            await self._create_connection(stream_name)
        self.callbacks[stream_name].append(callback)
        self.log.info(f"Subscribed to {stream_name}")

    async def _create_connection(self, stream_name: str) -> None:
        """Yeni WebSocket bağlantısı oluştur."""
        try:
            async with self.websocket_connection(stream_name) as ws:
                self.connections[stream_name] = ws
                self.metrics.total_connections += 1
                
                task = asyncio.create_task(self._listen_stream(stream_name))
                self._tasks.add(task)
                task.add_done_callback(lambda t: self._tasks.discard(t))
                self.log.info(f"WebSocket connection created for {stream_name}")
                
        except Exception as e:
            self.metrics.failed_connections += 1
            self.log.error(f"Failed to create WS connection for {stream_name}: {e}")
            raise BinanceWebSocketError(f"Failed to create connection: {e}")

    async def close_all(self) -> None:
        """Tüm bağlantıları temiz bir şekilde kapat."""
        self._running = False
        for stream_name, ws in self.connections.items():
            try:
                await ws.close()
                self.log.info(f"Closed WebSocket connection for {stream_name}")
            except Exception as e:
                self.log.error(f"Error closing WebSocket for {stream_name}: {e}")
        self.connections.clear()
        self.callbacks.clear()
        
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        self.log.info("All WebSocket connections closed")

    def get_metrics(self) -> WSMetrics:
        """WebSocket metriklerini getir."""
        if self._message_times:
            interval = max(self._message_times[-1] - self._message_times[0], 1)
            self.metrics.avg_message_rate = len(self._message_times) / interval
        return self.metrics

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all()