"""
main.py - Telegram Bot Ana Giriş Noktası
----------------------------------------
Free tier (Render, Railway, Oracle) uyumlu webhook setup.
- Async + logging + .env desteği
- Platforma özel otomatik config detection
- Handler loader ile dinamik handler import
- Webhook endpoint: /webhook/<TOKEN>
Geliştirilmiş özelliklerle: config management, enhanced health check, error resilience.
"""

import os
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

from utils.handler_loader import load_handlers, clear_handler_cache, get_handler_status

# ---------------------------------------------------------------------
# Config Management
# ---------------------------------------------------------------------
load_dotenv()

class Config:
    """Merkezi yapılandırma sınıfı"""
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.base_url = self._get_base_url()
        self.port = int(os.getenv("PORT", 8080))
        self.webhook_path = f"/webhook/{self.token}"
        self.platform = self._detect_platform()

    #✅ Platform Otomasyonu: Railway: RAILWAY_STATIC_URL/ Render: RENDER_EXTERNAL_URL/ Vercel: VERCEL_URL/ Oracle/VPS: PUBLIC_IP
    def _get_base_url(self) -> str:
        """Platforma göre otomatik BASE_URL belirle"""
        # Railway - Otomatik static URL
        if railway_url := os.getenv("RAILWAY_STATIC_URL"):
            return railway_url
        
        # Render - External URL
        if render_url := os.getenv("RENDER_EXTERNAL_URL"):
            return render_url
        
        # Vercel, Fly.io veya diğer platformlar
        if vercel_url := os.getenv("VERCEL_URL"):
            return f"https://{vercel_url}"
        
        # Oracle Cloud veya VPS - Public IP
        if public_ip := os.getenv("PUBLIC_IP"):
            return f"https://{public_ip}"
        
        # Fallback: Manuel BASE_URL veya localhost
        return os.getenv("BASE_URL", "https://localhost")

    def _detect_platform(self) -> str:
        """Çalışılan platformu tespit et"""
        if os.getenv("RAILWAY_STATIC_URL"):
            return "Railway"
        elif os.getenv("RENDER_EXTERNAL_URL"):
            return "Render"
        elif os.getenv("VERCEL_URL"):
            return "Vercel"
        elif os.getenv("PUBLIC_IP"):
            return "Oracle/VPS"
        else:
            return "Local"

    def validate(self) -> bool:
        """Gerekli config değerlerini kontrol et"""
        if not self.token:
            logging.error("❌ TELEGRAM_TOKEN environment variable is required")
            return False
        return True

# Config instance
config = Config()

# ---------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger(__name__)

# Platform bilgisi log
LOG.info(f"🏗️  Platform detected: {config.platform}")
LOG.info(f"🌐 Base URL: {config.base_url}")
LOG.info(f"🚪 Port: {config.port}")

# ---------------------------------------------------------------------
# Global Application
# ---------------------------------------------------------------------
if not config.validate():
    LOG.error("❌ Invalid configuration. Exiting...")
    exit(1)

application: Application = Application.builder().token(config.token).build()

# ---------------------------------------------------------------------
# Webhook Handler
#Free tier (Render, Railway, Oracle) uyumlu webhook setup.
# ---------------------------------------------------------------------
async def webhook_handler(request: web.Request) -> web.Response:
    """Handle Telegram webhook POST requests."""
    try:
        data = await request.json()
        update: Update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return web.Response(status=200)
    except Exception as e:
        LOG.error(f"❌ Webhook error: {e}")
        return web.Response(status=400)

# ---------------------------------------------------------------------
# Enhanced Health Check Handler
# ---------------------------------------------------------------------
async def health_handler(request: web.Request) -> web.Response:
    """Detaylı health check endpoint for platform monitoring"""
    try:
        handler_status = await get_handler_status()
        webhook_status = await application.bot.get_webhook_info() if application else None
        
        status = {
            "status": "ok", 
            "platform": config.platform,
            "handlers_loaded": handler_status['total_handlers'],
            "webhook_set": webhook_status.url if webhook_status else False,
            "webhook_url": webhook_status.url if webhook_status else "Not set",
            "pending_updates": webhook_status.pending_update_count if webhook_status else 0
        }
        return web.json_response(status)
    except Exception as e:
        LOG.error(f"❌ Health check error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ---------------------------------------------------------------------
# Handler Management Endpoint (opsiyonel)
# ---------------------------------------------------------------------
async def handlers_handler(request: web.Request) -> web.Response:
    """Handler yönetim endpoint'i"""
    try:
        handler_status = await get_handler_status()
        return web.json_response(handler_status)
    except Exception as e:
        LOG.error(f"❌ Handlers endpoint error: {e}")
        return web.json_response({"error": str(e)}, status=500)

# ---------------------------------------------------------------------
# Startup & Shutdown
# ---------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    """Bot startup: handler yükleme + webhook set etme."""
    LOG.info("🤖 Bot başlatılıyor...")
    
    try:
        # Handler cache temizle ve yükle
        clear_result = await clear_handler_cache()
        if clear_result['removed']:
            LOG.info(f"🧹 Cleared {len(clear_result['removed'])} handlers from cache")
        
        # Handler'ları yükle ve kaydet
        load_result = await load_handlers(application)
        
        if load_result['failed']:
            LOG.warning(f"⚠️  {len(load_result['failed'])} handlers failed to load")
        else:
            LOG.info(f"✅ {len(load_result['loaded'])} handlers loaded, {len(load_result['registered'])} registered successfully")

        # Webhook ayarla
        webhook_url = f"{config.base_url}{config.webhook_path}"
        LOG.info(f"🌐 Setting webhook URL: {webhook_url}")
        
        # Önce mevcut webhook'u temizle
        await application.bot.delete_webhook(drop_pending_updates=True)
        
        # Yeni webhook'u set et
        await application.bot.set_webhook(
            webhook_url,
            max_connections=50,
            allowed_updates=["message", "callback_query", "chat_member"]
        )
        LOG.info("✅ Webhook başarıyla set edildi")
        
    except Exception as e:
        LOG.error(f"❌ Startup error: {e}")
        raise

async def on_shutdown(app: web.Application) -> None:
    """Graceful shutdown - Free tier'lar sık restart eder"""
    LOG.info("🛑 Bot kapatılıyor...")
    try:
        # Webhook'u temizle (optional)
        await application.bot.delete_webhook()
        LOG.info("✅ Webhook temizlendi")
    except Exception as e:
        LOG.warning(f"⚠️  Webhook cleanup failed: {e}")
    
    # Application'ı kapat
    await application.stop()
    await application.shutdown()
    LOG.info("✅ Bot başarıyla kapatıldı")

# ---------------------------------------------------------------------
# Main Entrypoint - Webhook modunda
# ---------------------------------------------------------------------
async def main() -> None:
    """Ana uygulama entrypoint"""
    LOG.info(f"🚀 Starting bot on {config.platform} platform...")
    LOG.info(f"📊 PORT: {config.port}, BASE_URL: {config.base_url}")

    try:
        # aiohttp web application
        web_app = web.Application()
        
        # Routes
        web_app.router.add_post(config.webhook_path, webhook_handler)
        web_app.router.add_get("/health", health_handler)
        web_app.router.add_get("/", health_handler)
        web_app.router.add_get("/handlers", handlers_handler)  # Opsiyonel: handler durum endpoint'i
        
        # Lifecycle events
        web_app.on_startup.append(on_startup)
        web_app.on_shutdown.append(on_shutdown)

        # Server setup
        runner = web.AppRunner(web_app)
        await runner.setup()
        
        # 0.0.0.0 binding (tüm interfacelere açık)
        site = web.TCPSite(runner, "0.0.0.0", config.port)
        await site.start()
        
        LOG.info(f"🌐 Server started on port {config.port}")
        LOG.info(f"🔧 Health check: {config.base_url}/health")
        LOG.info(f"📨 Webhook endpoint: {config.base_url}{config.webhook_path}")

        # Telegram application'ı başlat
        await application.initialize()
        await application.start()
        LOG.info("✅ Telegram application started")

        # Sonsuz bekleyiş
        await asyncio.Event().wait()

    except Exception as e:
        LOG.error(f"💥 Critical error: {e}")
        raise
    finally:
        # Cleanup garantile
        if 'runner' in locals():
            await runner.cleanup()
        LOG.info("👋 Application terminated")

# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("🛑 Manual shutdown detected")
    except Exception as e:
        LOG.error(f"🚨 Fatal error: {e}")
    finally:
        LOG.info("📴 Bot completely shut down")
