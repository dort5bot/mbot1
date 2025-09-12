import os
import asyncio
import logging
import signal
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter
from aiogram.types import ErrorEvent

from utils.handler_loader import load_handlers, clear_handler_cache
from utils.binance.binance_a import BinanceAPI
from utils.binance.binance_request import BinanceHTTPClient
from utils.binance.binance_circuit_breaker import CircuitBreaker
from config import BotConfig, get_config, get_telegram_token, get_admins

# ---------------------------------------------------------------------
# Config & Logging Setup
# ---------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

bot: Optional[Bot] = None
dispatcher: Optional[Dispatcher] = None
binance_api: Optional[BinanceAPI] = None
app_config: Optional[BotConfig] = None
runner: Optional[web.AppRunner] = None
polling_task: Optional[asyncio.Task] = None
shutdown_event = asyncio.Event()

# ---------------------------------------------------------------------
# Signal Handling
# ---------------------------------------------------------------------
def handle_shutdown(signum, frame) -> None:
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    try:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except Exception:
        shutdown_event.set()

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# ---------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------
async def error_handler(event: ErrorEvent) -> None:
    logger.error(f"❌ Error handling update: {event.exception}")
    try:
        if getattr(event.update, "message", None):
            await event.update.message.answer("❌ Bir hata oluştu, lütfen daha sonra tekrar deneyin.")
    except Exception as e:
        logger.error(f"❌ Failed to send error message: {e}")

# ---------------------------------------------------------------------
# Filters & Middleware
# ---------------------------------------------------------------------
class RateLimitFilter(BaseFilter):
    def __init__(self, rate: float = 1.0):
        self.rate = rate
        self.last_called = 0.0

    async def __call__(self, message: Message) -> bool:
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_called >= self.rate:
            self.last_called = current_time
            return True
        return False

class LoggingMiddleware:
    async def __call__(self, handler, event, data):
        logger.info(f"📨 Update received: {getattr(event, 'update_id', 'unknown')}")
        start_time = asyncio.get_event_loop().time()
        try:
            result = await handler(event, data)
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Update processed: {getattr(event, 'update_id', 'unknown')} in {processing_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"❌ Error processing update {getattr(event, 'update_id', 'unknown')}: {e}")
            raise

class AuthenticationMiddleware:
    async def __call__(self, handler, event, data):
        global app_config
        user = getattr(event, "from_user", None)
        if user:
            user_id = user.id
            data['user_id'] = user_id
            data['is_admin'] = app_config.is_admin(user_id) if app_config else False
            logger.debug(f"👤 User {user_id} - Admin: {data['is_admin']}")
        return await handler(event, data)

# ---------------------------------------------------------------------
# Dependency Injection Container
# ---------------------------------------------------------------------
class DIContainer:
    _instances: Dict[str, Any] = {}
    @classmethod
    def register(cls, key: str, instance: Any) -> None:
        cls._instances[key] = instance
        logger.debug(f"📦 DI Container: Registered {key}")
    @classmethod
    def resolve(cls, key: str) -> Optional[Any]:
        return cls._instances.get(key)
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        return cls._instances.copy()

# ---------------------------------------------------------------------
# Polling (for local dev)
# ---------------------------------------------------------------------
async def start_polling() -> None:
    global bot, dispatcher
    if not bot or not dispatcher:
        logger.error("❌ Bot or dispatcher not initialized for polling")
        return
    try:
        logger.info("🔄 Starting polling mode for local development...")
        await dispatcher.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("⏹️ Polling task cancelled")
    except Exception as e:
        logger.error(f"❌ Polling failed: {e}")

# ---------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan():
    global bot, dispatcher, binance_api, app_config, polling_task, runner
    try:
        app_config = await get_config()
        bot = Bot(
            token=get_telegram_token(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        main_router = Router()
        dispatcher = Dispatcher()
        dispatcher.include_router(main_router)
        dispatcher.errors.register(error_handler)
        dispatcher.update.outer_middleware(LoggingMiddleware())
        dispatcher.update.outer_middleware(AuthenticationMiddleware())

        DIContainer.register('bot', bot)
        DIContainer.register('dispatcher', dispatcher)
        DIContainer.register('config', app_config)

        if app_config.ENABLE_TRADING:
            http_client = BinanceHTTPClient(
                api_key=app_config.BINANCE_API_KEY,
                secret_key=app_config.BINANCE_API_SECRET,
                base_url=app_config.BINANCE_BASE_URL,
                timeout=app_config.REQUEST_TIMEOUT
            )
            circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, half_open_attempts=2)
            binance_api = BinanceAPI(http_client, circuit_breaker)
            DIContainer.register('binance_api', binance_api)
            logger.info("✅ Binance API initialized (trading enabled)")
        else:
            binance_api = None
            logger.info("ℹ️ Binance API not initialized (trading disabled)")

        if not app_config.USE_WEBHOOK:
            polling_task = asyncio.create_task(start_polling())

        logger.info("✅ Application components initialized")
        yield

    finally:
        if polling_task and not polling_task.done():
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("✅ Polling task cancelled successfully")

        if binance_api:
            try:
                await binance_api.close()
            except Exception as e:
                logger.warning(f"⚠️ Binance API close failed: {e}")

        if bot and hasattr(bot, 'session'):
            try:
                await bot.session.close()
            except Exception as e:
                logger.warning(f"⚠️ Bot session close failed: {e}")

        if runner:
            try:
                await runner.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Runner cleanup failed: {e}")

        DIContainer._instances.clear()
        logger.info("🛑 Application resources cleaned up")

# ---------------------------------------------------------------------
# Health, Startup, Shutdown, Utility funcs (DEĞİŞMEDİ)
# ---------------------------------------------------------------------
# ... [BURASI SENDEKİYLE AYNI KALSIN] ...

# ---------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------
async def main() -> None:
    global app_config, runner
    try:
        app_config = await get_config()
        platform = "Render" if "RENDER" in os.environ else "Local"
        logger.info(f"🏗️ Platform detected: {platform}")
        logger.info(f"🌐 Environment: {'production' if not app_config.DEBUG else 'development'}")

        app = await create_app()
        if app_config.USE_WEBHOOK:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host=app_config.WEBAPP_HOST, port=app_config.WEBAPP_PORT)
            await site.start()
            logger.info(f"✅ Server started successfully on port {app_config.WEBAPP_PORT}")
        else:
            logger.info("✅ Polling mode active, web server not started")

        await shutdown_event.wait()
        logger.info("👋 Shutdown signal received, exiting...")

    except Exception as e:
        logger.error(f"🚨 Critical error: {e}")
        raise
    finally:
        logger.info("✅ Application cleanup completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        exit(1)
