"""
main.py - Telegram Bot Ana Giriş Noktası
----------------------------------------
Render uyumlu webhook setup (aiohttp).
- Async + logging + .env desteği
- Handler loader ile dinamik handler import
- Webhook endpoint: /webhook/<TOKEN>
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

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
BASE_URL: str = os.getenv("BASE_URL", "https://mbot1-fcu9.onrender.com")
PORT: int = int(os.getenv("PORT", 8080))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger(__name__)


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
    except Exception as e:
        LOG.error("❌ Webhook JSON parse error: %s", e)
        return web.Response(status=400)

    update: Update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return web.Response(status=200)


# ---------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    """Bot startup: handler yükleme + webhook set etme."""
    LOG.info("🤖 Bot başlatılıyor...")

    # Handler cache temizle
    await clear_handler_cache()

    # Handlerları yükle
    await load_handlers(application)
    LOG.info("✅ Tüm handler'lar başarıyla yüklendi.")

    # Webhook ayarla
    webhook_url = f"{BASE_URL}/webhook/{TELEGRAM_TOKEN}"
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(webhook_url)
    LOG.info("🌐 Webhook set edildi: %s", webhook_url)


async def on_shutdown(app: web.Application) -> None:
    """Graceful shutdown."""
    LOG.info("🛑 Bot kapatılıyor...")
    await application.stop()


# ---------------------------------------------------------------------
# Main Entrypoint
# ---------------------------------------------------------------------
async def main() -> None:
    LOG.info("Event loop başlatılıyor...")

    # aiohttp server
    web_app = web.Application()
    web_app.router.add_post(f"/webhook/{TELEGRAM_TOKEN}", webhook_handler)

    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    LOG.info("🚀 Webhook server started on port %s", PORT)

    # Telegram Application run
    await application.initialize()
    await application.start()
    await application.updater.start_polling()  # update_queue için gerekli

    # Sonsuza kadar bekle
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOG.error("🚨 Bot kapatıldı.")
