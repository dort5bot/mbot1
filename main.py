"""
main.py - Telegram Bot Ana Giriş Noktası (FİNAL)
----------------------------------------
Aiogram 3.x + Router pattern + Webhook + Render uyumlu.
- Yeni config yapısına tam uyumlu
- Gelişmiş error handling
- Health check endpoints
- Graceful shutdown
- Local polling desteği eklendi
free tier platformlarla tam uyumludur.
+ (Webhook path now uses /webhook/<BOT_TOKEN> format)
"""

import os
import asyncio
import logging
import signal
from typing import Optional, Dict, Any

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

# Global instances
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
# Rate Limit Filter
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

# ---------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------
class LoggingMiddleware:
    async def __call__(self, handler, event, data):
        logger.info(f"📨 Update received: {getattr(event, 'update_id', 'unknown')}")
        start_time = asyncio.get_event_loop().time()
        try:
            result = await handler(event, data)
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Update processed in {processing_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"❌ Error processing update: {e}")
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

    @classmethod
    def resolve(cls, key: str) -> Optional[Any]:
        return cls._instances.get(key)

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        return cls._instances.copy()

# ---------------------------------------------------------------------
# Polling (Local Dev)
# ---------------------------------------------------------------------
async def start_polling() -> None:
    global bot, dispatcher
    if not bot or not dispatcher:
        logger.error("❌ Bot or dispatcher not initialized for polling")
        return
    try:
        logger.info("🔄 Starting polling mode...")
        await dispatcher.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("⏹️ Polling cancelled")
    except Exception as e:
        logger.error(f"❌ Polling failed: {e}")

# ---------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    global bot, dispatcher, binance_api, app_config, polling_task

    app_config = await get_config()

    bot = Bot(
        token=get_telegram_token(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
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
        logger.info("✅ Binance API initialized")
    else:
        binance_api = None
        logger.info("ℹ️ Binance API not initialized")

    await clear_handler_cache()
    load_results = await load_handlers(dispatcher)
    if load_results.get("failed", 0) > 0:
        logger.warning(f"⚠️ {load_results['failed']} handlers failed to load")

    if app_config.USE_WEBHOOK and app_config.WEBHOOK_HOST:
        host = app_config.WEBHOOK_HOST.rstrip("/")
        token = get_telegram_token()
        webhook_url = f"{host}/webhook/{token}"
        await bot.delete_webhook(drop_pending_updates=True)
        secret = getattr(app_config, "WEBHOOK_SECRET", None) or None
        if secret:
            await bot.set_webhook(webhook_url, secret_token=secret)
        else:
            await bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook set: {webhook_url}")
    else:
        polling_task = asyncio.create_task(start_polling())
        logger.info("✅ Polling mode started")

    for admin_id in get_admins():
        try:
            await bot.send_message(admin_id, "🤖 Bot başlatıldı ve çalışıyor!")
        except Exception as e:
            logger.warning(f"⚠️ Admin {admin_id} mesaj gönderilemedi: {e}")

async def on_shutdown(app: web.Application) -> None:
    global bot, binance_api, polling_task
    logger.info("🛑 Shutting down...")

    if polling_task and not polling_task.done():
        polling_task.cancel()
        try:
            await polling_task
        except Exception:
            pass

    if bot and app_config and app_config.USE_WEBHOOK:
        try:
            await bot.delete_webhook()
            logger.info("✅ Webhook deleted")
        except Exception as e:
            logger.warning(f"⚠️ Webhook delete failed: {e}")

    if binance_api:
        await binance_api.close()
    if bot and hasattr(bot, 'session'):
        await bot.session.close()

    DIContainer._instances.clear()
    logger.info("🛑 Resources cleaned up")

# ---------------------------------------------------------------------
# Health Endpoints
# ---------------------------------------------------------------------
async def health_check(request: web.Request) -> web.Response:
    return web.json_response(await check_services())

async def readiness_check(request: web.Request) -> web.Response:
    global bot, app_config
    if bot and app_config:
        return web.json_response({"status": "ready"})
    return web.json_response({"status": "not_ready"}, status=503)

async def version_info(request: web.Request) -> web.Response:
    return web.json_response(await get_system_info())

# ---------------------------------------------------------------------
# Create App
# ---------------------------------------------------------------------
async def create_app() -> web.Application:
    global app_config, bot, dispatcher

    app_config = await get_config()
    app = web.Application()

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/ready", readiness_check)
    app.router.add_get("/version", version_info)

    if app_config.USE_WEBHOOK and app_config.WEBHOOK_HOST:
        webhook_handler = SimpleRequestHandler(
            dispatcher=dispatcher,
            bot=bot,
            secret_token=getattr(app_config, "WEBHOOK_SECRET", None) or None
        )
        webhook_handler.register(app, path="/webhook/{token}")
        logger.info("📨 Webhook endpoint configured")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    setup_application(app, dispatcher, bot=bot)
    return app

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
async def check_services() -> Dict[str, Any]:
    global bot, binance_api, app_config
    services_status = {}

    try:
        if bot:
            me = await bot.get_me()
            services_status["telegram"] = {"status": "connected", "username": me.username}
        else:
            services_status["telegram"] = {"status": "disconnected"}
    except Exception as e:
        services_status["telegram"] = {"status": "disconnected", "error": str(e)}

    if app_config and app_config.ENABLE_TRADING:
        try:
            if binance_api:
                ping_result = await binance_api.ping()
                services_status["binance"] = {"status": "connected" if ping_result else "disconnected"}
            else:
                services_status["binance"] = {"status": "disconnected"}
        except Exception as e:
            services_status["binance"] = {"status": "disconnected", "error": str(e)}
    else:
        services_status["binance"] = {"status": "disabled"}

    return services_status

async def get_system_info() -> Dict[str, Any]:
    global app_config
    return {
        "version": "1.0.0",
        "python_version": os.sys.version,
        "aiohttp_version": aiohttp.__version__,
        "debug_mode": app_config.DEBUG if app_config else False,
        "webhook_enabled": app_config.USE_WEBHOOK if app_config else False,
        "services": await check_services(),
        "di_services": list(DIContainer.get_all().keys())
    }

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
async def main() -> None:
    global app_config, runner
    try:
        app = await create_app()
        if app_config.USE_WEBHOOK:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host=app_config.WEBAPP_HOST, port=app_config.WEBAPP_PORT)
            await site.start()
            logger.info(f"✅ Server started on port {app_config.WEBAPP_PORT}")
        else:
            logger.info("✅ Polling mode active")
        await shutdown_event.wait()
    finally:
        if runner:
            await runner.cleanup()
        logger.info("✅ Cleanup completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        exit(1)
