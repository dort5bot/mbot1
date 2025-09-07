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
from aiogram import Router

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
# Global Application & Router
# ---------------------------------------------------------------------
if not config.validate():
    LOG.error("❌ Invalid configuration. Exiting...")
    exit(1)

application: Application = Application.builder().token(config.token).build()
main_router = Router()

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
            "routers_loaded": handler_status['total_routers'],
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
        load_result = await load_handlers(application, main_router)
        
        if load_result['failed']:
            LOG.warning(f"⚠️  {len(load_result['failed'])} handlers failed to load")
        else:
            LOG.info(f"✅ {len(load_result['loaded'])} handlers loaded, {len(load_result['registered'])} registered successfully")

        # Ana router'ı application'a ekle
        application.include_router(main_router)
        LOG.info(f"✅ Main router included with {len(main_router.message.handlers)} message handlers")

        # Webhook ayarla
        webhook_url = f"{config.base_url}{config.webhook_path}"
        LOG.info(f"🌐 Setting webhook URL: {webhook_url}")
        
        # Önce mevcut webhook'u temizle
        await application.bot.delete_webhook()
        await asyncio.sleep(1)
        
        # Yeni webhook'u ayarla
        await application.bot.set_webhook(webhook_url)
        LOG.info("✅ Webhook set successfully")
        
    except Exception as e:
        LOG.error(f"❌ Startup error: {e}")
        raise

async def on_shutdown(app: web.Application) -> None:
    """Bot shutdown: webhook temizleme."""
    LOG.info("🛑 Bot kapatılıyor...")
    try:
        await application.bot.delete_webhook()
        await application.shutdown()
        LOG.info("✅ Webhook removed and application shutdown complete")
    except Exception as e:
        LOG.error(f"❌ Shutdown error: {e}")

# ---------------------------------------------------------------------
# Main Application Setup
# ---------------------------------------------------------------------
def main() -> None:
    """Ana uygulama entry point."""
    LOG.info("🚀 Starting Telegram bot application...")
    
    # Web server oluştur
    app = web.Application()
    
    # Route'ları ekle
    app.router.add_post(config.webhook_path, webhook_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/handlers", handlers_handler)
    
    # Startup/shutdown event handlers
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Server'ı başlat
    LOG.info(f"🌐 Starting server on port {config.port}")
    web.run_app(
        app,
        host="0.0.0.0",
        port=config.port,
        access_log=LOG
    )

if __name__ == "__main__":
    main()
