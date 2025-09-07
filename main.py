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
"""
main.py - Telegram Bot Ana Giriş Noktası
"""

import os
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

# Sadece ihtiyacımız olan fonksiyonları import ediyoruz
from utils.handler_loader import load_handlers

# ---------------------------------------------------------------------
# Config Management
# ---------------------------------------------------------------------
load_dotenv()

class Config:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.base_url = self._get_base_url()
        self.port = int(os.getenv("PORT", 8080))
        self.webhook_path = f"/webhook/{self.token}"
        self.platform = self._detect_platform()

    def _get_base_url(self) -> str:
        if railway_url := os.getenv("RAILWAY_STATIC_URL"):
            return railway_url
        if render_url := os.getenv("RENDER_EXTERNAL_URL"):
            return render_url
        if vercel_url := os.getenv("VERCEL_URL"):
            return f"https://{vercel_url}"
        if public_ip := os.getenv("PUBLIC_IP"):
            return f"https://{public_ip}"
        return os.getenv("BASE_URL", "https://localhost")

    def _detect_platform(self) -> str:
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
# ---------------------------------------------------------------------
async def webhook_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        update: Update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        LOG.error(f"❌ Webhook error: {e}")
        return web.Response(status=400)

# ---------------------------------------------------------------------
# Health Check Handler (Basitleştirilmiş)
# ---------------------------------------------------------------------
async def health_handler(request: web.Request) -> web.Response:
    try:
        status = {
            "status": "ok", 
            "platform": config.platform,
            "webhook_url": f"{config.base_url}{config.webhook_path}"
        }
        return web.json_response(status)
    except Exception as e:
        LOG.error(f"❌ Health check error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ---------------------------------------------------------------------
# Startup & Shutdown
# ---------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    LOG.info("🤖 Bot başlatılıyor...")
    
    try:
        # Handler'ları yükle
        load_result = await load_handlers(application)
        
        if load_result['failed']:
            LOG.warning(f"⚠️  {len(load_result['failed'])} handlers failed to load")
        else:
            LOG.info(f"✅ {len(load_result['loaded'])} handlers loaded, {len(load_result['registered'])} registered successfully")

        # Webhook ayarla
        webhook_url = f"{config.base_url}{config.webhook_path}"
        LOG.info(f"🌐 Setting webhook URL: {webhook_url}")
        
        await application.bot.delete_webhook()
        await asyncio.sleep(1)
        
        await application.bot.set_webhook(webhook_url)
        LOG.info("✅ Webhook set successfully")
        
    except Exception as e:
        LOG.error(f"❌ Startup error: {e}")
        raise

async def on_shutdown(app: web.Application) -> None:
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
    LOG.info("🚀 Starting Telegram bot application...")
    
    # Web server oluştur
    app = web.Application()
    
    # Route'ları ekle
    app.router.add_post(config.webhook_path, webhook_handler)
    app.router.add_get("/health", health_handler)
    
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
