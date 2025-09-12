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

# Configure logging
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

# Graceful shutdown flag
shutdown_event = asyncio.Event()

# ---------------------------------------------------------------------
# Signal Handling for Graceful Shutdown
# ---------------------------------------------------------------------
def handle_shutdown(signum, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    # set the asyncio event in an async-safe way
    try:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except Exception:
        # If loop closed or unavailable, set directly (best-effort)
        shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# ---------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------
async def error_handler(event: ErrorEvent) -> None:
    """Global error handler for aiogram."""
    logger.error(f"❌ Error handling update: {event.exception}")
    
    try:
        if getattr(event.update, "message", None):
            await event.update.message.answer("❌ Bir hata oluştu, lütfen daha sonra tekrar deneyin.")
    except Exception as e:
        logger.error(f"❌ Failed to send error message: {e}")

# ---------------------------------------------------------------------
# Rate Limiting Filter
# ---------------------------------------------------------------------
class RateLimitFilter(BaseFilter):
    """Rate limiting filter for messages."""
    
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
# Middleware Implementation
# ---------------------------------------------------------------------
class LoggingMiddleware:
    """Middleware for request logging and monitoring."""
    
    async def __call__(self, handler, event, data):
        # Pre-processing
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
    """Middleware for user authentication and authorization."""
    
    async def __call__(self, handler, event, data):
        global app_config
        
        # Some events may not have from_user (like callback query wrappers), guard accordingly
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
    """Simple dependency injection container for global instances."""
    
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, key: str, instance: Any) -> None:
        """Register an instance with a key."""
        cls._instances[key] = instance
        logger.debug(f"📦 DI Container: Registered {key}")
    
    @classmethod
    def resolve(cls, key: str) -> Optional[Any]:
        """Resolve an instance by key."""
        return cls._instances.get(key)
    
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all registered instances."""
        return cls._instances.copy()

# ... (önceki importlar ve yapılandırma aynı)

# ---------------------------------------------------------------------
# Handler yükleme sonrasında yönlendiricileri kontrol et
# ---------------------------------------------------------------------
def log_routers(dispatcher: Dispatcher):
    """Log all registered routers and handlers."""
    logger.info("📋 Registered routers and handlers:")
    
    # dispatcher doğrudan kendisi router koleksiyonunu içerir
    for i, router in enumerate(dispatcher._routers):
        logger.info(f"  {i+1}. {router.__class__.__name__}")
        
        # Handler'ları logla
        for j, handler in enumerate(router.handlers):
            handler_name = handler.callback.__name__ if hasattr(handler.callback, '__name__') else 'unknown'
            logger.info(f"    └ Handler {j+1}: {handler_name}")
            logger.info(f"      Filters: {[f.__class__.__name__ for f in handler.filters]}")

# ---------------------------------------------------------------------
# Polling Setup for Local Development
# ---------------------------------------------------------------------
async def start_polling() -> None:
    """Start polling for local development when webhook is not configured."""
    global bot, dispatcher
    
    if not bot or not dispatcher:
        logger.error("❌ Bot or dispatcher not initialized for polling")
        return
    
    try:
        logger.info("🔄 Starting polling mode for local development...")
        # start_polling will run until cancelled
        await dispatcher.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("⏹️ Polling task cancelled")
    except Exception as e:
        logger.error(f"❌ Polling failed: {e}")

# ---------------------------------------------------------------------
# Lifespan Management (Async Context Manager)
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan():
    """Manage application lifecycle with async context manager."""
    global bot, dispatcher, binance_api, app_config, polling_task
    
    try:
        # Load configuration
        app_config = await get_config()
        
        # Initialize bot with default properties
        bot = Bot(
            token=get_telegram_token(),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
            )
        )
        
        # Initialize dispatcher
        dispatcher = Dispatcher()
        dispatcher.errors.register(error_handler)
        
        # Register middleware
        dispatcher.update.outer_middleware(LoggingMiddleware())
        dispatcher.update.outer_middleware(AuthenticationMiddleware())
        logger.info("✅ Middleware registered: Logging, Authentication")
        
        # Register instances in DI container
        DIContainer.register('bot', bot)
        DIContainer.register('dispatcher', dispatcher)
        DIContainer.register('config', app_config)
        
        # Initialize Binance API (only if trading is enabled)
        if app_config.ENABLE_TRADING:
            http_client = BinanceHTTPClient(
                api_key=app_config.BINANCE_API_KEY,
                secret_key=app_config.BINANCE_API_SECRET,
                base_url=app_config.BINANCE_BASE_URL,
                timeout=app_config.REQUEST_TIMEOUT
            )
            
            circuit_breaker = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60,
                half_open_attempts=2
            )
            
            binance_api = BinanceAPI(http_client, circuit_breaker)
            DIContainer.register('binance_api', binance_api)
            logger.info("✅ Binance API initialized (trading enabled)")
        else:
            binance_api = None
            logger.info("ℹ️ Binance API not initialized (trading disabled)")
        
        # Handler'ları yükle
        await clear_handler_cache()
        load_results = await load_handlers(dispatcher)
        logger.info(f"✅ Handlers loaded: {load_results}")
        
        # Router debug log
        log_routers(dispatcher)
        
        if load_results.get("failed", 0) > 0:
            logger.warning(f"⚠️ {load_results['failed']} handlers failed to load")
        
        # Start polling if webhook is not configured (local development)
        if not app_config.USE_WEBHOOK:
            polling_task = asyncio.create_task(start_polling())
            logger.info("✅ Polling mode started for local development")
        
        logger.info("✅ Application components initialized")
        yield
        
    except Exception as e:
        logger.error(f"❌ Application initialization failed: {e}")
        raise
    finally:
        # Cleanup resources
        cleanup_tasks = []
        
        # Cancel polling task if running
        if polling_task and not polling_task.done():
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("✅ Polling task cancelled successfully")
            except Exception as e:
                logger.warning(f"⚠️ Error cancelling polling task: {e}")
        
        if binance_api:
            cleanup_tasks.append(binance_api.close())
        
        if bot and hasattr(bot, 'session'):
            cleanup_tasks.append(bot.session.close())
        
        # Clear DI container
        DIContainer._instances.clear()
        
        if cleanup_tasks:
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ Cleanup task failed: {result}")
        
        logger.info("🛑 Application resources cleaned up")

# ---------------------------------------------------------------------
# Webhook Setup Functions
# ---------------------------------------------------------------------
async def on_startup(bot: Bot) -> None:
    """Execute on application startup."""
    global app_config
    
    try:
        # Set webhook if webhook is configured
        if app_config.USE_WEBHOOK and app_config.WEBHOOK_HOST:
            # Ensure WEBHOOK_HOST doesn't end with slash
            host = app_config.WEBHOOK_HOST.rstrip("/")
            token = get_telegram_token()
            webhook_url = f"{host}/webhook/{token}"
            await bot.delete_webhook(drop_pending_updates=True)
            
            # set secret_token if provided in config, else None
            secret = getattr(app_config, "WEBHOOK_SECRET", None) or None
            if secret:
                await bot.set_webhook(webhook_url, secret_token=secret)
            else:
                await bot.set_webhook(webhook_url)
            
            logger.info(f"✅ Webhook set successfully: {webhook_url}")
        else:
            logger.info("ℹ️ Webhook not configured, using polling mode")
        
        # Log health check URL
        try:
            host = app_config.WEBAPP_HOST
            port = app_config.WEBAPP_PORT
            logger.info(f"🌐 Health check: http://{host}:{port}/health")
        except Exception:
            logger.info("🌐 Health check endpoint available at /health")
        
        # 🔔 Adminlere "Bot başlatıldı" mesajı gönder
        for admin_id in get_admins():
            try:
                await bot.send_message(admin_id, "🤖 Bot başlatıldı ve çalışıyor!")
            except Exception as e:
                logger.warning(f"⚠️ Admin {admin_id} mesaj gönderilemedi: {e}")
    
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

# ... (diğer fonksiyonlar aynı kalacak)

# ---------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------
async def main() -> None:
    """Main application entry point."""
    global app_config, runner
    
    try:
        # Load configuration
        app_config = await get_config()
        
        # Platform detection
        platform = "Render" if "RENDER" in os.environ else "Local"
        logger.info(f"🏗️ Platform detected: {platform}")
        logger.info(f"🌐 Environment: {'production' if not app_config.DEBUG else 'development'}")
        logger.info(f"🚪 Port: {app_config.WEBAPP_PORT}")
        logger.info(f"🏠 Host: {app_config.WEBAPP_HOST}")
        logger.info(f"🤖 Trading enabled: {app_config.ENABLE_TRADING}")
        logger.info(f"🌐 Webhook mode: {'enabled' if app_config.USE_WEBHOOK else 'disabled (polling)'}")
        
        # Create and run application
        app = await create_app()
        
        # Only start web server if webhook is configured
        if app_config.USE_WEBHOOK:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host=app_config.WEBAPP_HOST, port=app_config.WEBAPP_PORT)
            await site.start()
            
            logger.info(f"✅ Server started successfully on port {app_config.WEBAPP_PORT}")
            logger.info(f"📊 Health check: http://{app_config.WEBAPP_HOST}:{app_config.WEBAPP_PORT}/health")
        else:
            logger.info("✅ Polling mode active, web server not started")
        
        logger.info("🤖 Bot is now running...")
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        logger.info("👋 Shutdown signal received, exiting...")
        
    except KeyboardInterrupt:
        logger.info("🛑 Application stopped by user")
    except Exception as e:
        logger.error(f"🚨 Critical error: {e}")
        raise
    finally:
        # Ensure proper cleanup
        try:
            if runner:
                await runner.cleanup()
            logger.info("✅ Application cleanup completed")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")

if __name__ == "__main__":
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        exit(1)
