"""
main.py - Telegram Bot Ana Giriş Noktası
----------------------------------------
Free tier (Render, Railway, Oracle) uyumlu webhook setup.
- Async + logging + .env desteği
- Platforma özel otomatik config detection
- Handler loader ile dinamik handler import
- Webhook endpoint: /webhook/<TOKEN>
tüm free tier platformlarda problemsiz çalışacak 
✅ Platform Otomasyonu
Railway: RAILWAY_STATIC_URL
Render: RENDER_EXTERNAL_URL
Vercel: VERCEL_URL
Oracle/VPS: PUBLIC_IP
Local fallback

✅ Free Tier Optimizasyon
Düşük memory usage + Async efficiency + Auto-restart friendly

"""

import os
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

from utils.handler_loader import load_handlers, clear_handler_cache

# ---------------------------------------------------------------------
# Config & Logging
# ---------------------------------------------------------------------
load_dotenv()

# Platforma göre otomatik BASE_URL detection
def get_base_url() -> str:
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

# Environment variables
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
BASE_URL: str = get_base_url()
PORT: int = int(os.getenv("PORT", 8080))  # Render/Railway otomatik atar

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger(__name__)

# Platform bilgisi log
platform = "Railway" if os.getenv("RAILWAY_STATIC_URL") else \
           "Render" if os.getenv("RENDER_EXTERNAL_URL") else \
           "Vercel" if os.getenv("VERCEL_URL") else \
           "Oracle/VPS" if os.getenv("PUBLIC_IP") else \
           "Local"
LOG.info(f"🏗️  Platform detected: {platform}")

# ---------------------------------------------------------------------
# Global Application
# ---------------------------------------------------------------------
application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---------------------------------------------------------------------
# Webhook Handler
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
# Health Check Handler (Railway/Render için)
# ---------------------------------------------------------------------
async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint for platform monitoring"""
    return web.json_response({"status": "ok", "platform": platform})

# ---------------------------------------------------------------------
# Startup & Shutdown
# ---------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    """Bot startup: handler yükleme + webhook set etme."""
    LOG.info("🤖 Bot başlatılıyor...")
    
    try:
        # Handler cache temizle ve yükle
        await clear_handler_cache()
        await load_handlers(application)
        LOG.info("✅ Tüm handler'lar başarıyla yüklendi.")

        # Webhook ayarla (30s timeout ile)
        webhook_url = f"{BASE_URL}/webhook/{TELEGRAM_TOKEN}"
        LOG.info(f"🌐 Webhook URL: {webhook_url}")
        
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
    LOG.info(f"🚀 Starting bot on {platform} platform...")
    LOG.info(f"📊 PORT: {PORT}, BASE_URL: {BASE_URL}")

    try:
        # aiohttp web application
        web_app = web.Application()
        
        # Routes
        web_app.router.add_post(f"/webhook/{TELEGRAM_TOKEN}", webhook_handler)
        web_app.router.add_get("/health", health_handler)  # Railway/Render health check
        web_app.router.add_get("/", health_handler)        # Root endpoint
        
        # Lifecycle events
        web_app.on_startup.append(on_startup)
        web_app.on_shutdown.append(on_shutdown)

        # Server setup
        runner = web.AppRunner(web_app)
        await runner.setup()
        
        # 0.0.0.0 binding (tüm interfacelere açık)
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        
        LOG.info(f"🌐 Server started on port {PORT}")
        LOG.info(f"🔧 Health check: {BASE_URL}/health")
        LOG.info(f"📨 Webhook endpoint: {BASE_URL}/webhook/{TELEGRAM_TOKEN}")

        # Telegram application'ı başlat (POLLING OLMADAN)
        await application.initialize()
        await application.start()
        LOG.info("✅ Telegram application started")

        # Sonsuz bekleyiş (free tier auto-restart handle eder)
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
