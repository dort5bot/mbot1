"""
main.py - Telegram Bot Ana Giriş Noktası

🔐 Güvenli yapı: .env ile secret yönetimi
⚙️ Katmanlı mimari: Config, handler loader, async yapı
📦 Modüler yapı: Handler'lar otomatik yüklenir
webhook moduna uygun
.env içine ekle
        WEBHOOK_URL=https://mbot1-fcu9.onrender.com/webhook
        ENABLE_PING_SERVER=true
async uyumlu + PEP8 + type hints + docstring + singleton + logging destekler
"""
"""
main.py - Telegram Bot Ana Giriş Noktası (Webhook Modu)

🔐 Güvenli yapı: .env ile secret yönetimi
⚙️ Katmanlı mimari: Config, handler loader, async yapı
📦 Modüler yapı: Handler'lar otomatik yüklenir
async uyumlu + PEP8 + type hints + singleton + logging destekler
🌍 Webhook mode: Render gibi servislerde uzun vadeli stabil çalışır
"""

import os
import sys
import asyncio
import logging
import signal
import nest_asyncio
from typing import Optional

from telegram import Bot, Update
from telegram.ext import Application, ApplicationBuilder
from telegram.error import Conflict
from aiohttp import web

from config import get_config, BinanceConfig
from utils.handler_loader import load_handlers, clear_handler_cache, get_loaded_handlers

# Event loop çakışmalarını önlemek için
nest_asyncio.apply()

# Logging yapılandırması
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger: logging.Logger = logging.getLogger(__name__)


async def start_ping_server() -> web.TCPSite:
    """
    Basit bir HTTP ping endpoint (UptimeRobot için).
    .env içinde ENABLE_PING_SERVER=true ise aktif olur.

    Returns:
        web.TCPSite: Başlatılan TCP site objesi
    """
    async def handle(_request: web.Request) -> web.Response:
        return web.Response(text="✅ Bot alive")

    app = web.Application()
    app.router.add_get("/", handle)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🌍 Ping server running on port %s", port)
    return site


async def start_bot() -> Application:
    """
    Telegram botu başlatır (Webhook mode).

    Returns:
        Application: Başlatılan Telegram Application objesi
    """
    app: Optional[Application] = None
    try:
        # 📌 Binance Config yükle
        config: BinanceConfig = await get_config()
        if not config.api_key or not config.secret_key:
            raise ValueError("❌ API Key veya Secret eksik!")

        logger.info("🔐 API Key ve Secret yüklendi")

        # 📌 Telegram bot token
        bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN eksik!")

        # 📌 Webhook URL
        webhook_url: str = os.getenv("WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise ValueError("❌ WEBHOOK_URL eksik!")

        # 📌 Telegram Bot nesnesi
        bot = Bot(token=bot_token)

        # 📌 Mevcut webhook'u temizle ve güncelle
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(url=webhook_url)
        logger.info("🌐 Webhook set edildi: %s", webhook_url)

        # 📌 Application oluşturma
        app = ApplicationBuilder().token(bot_token).build()

        # 📌 Handler'ları yükle
        await load_handlers(app)
        await clear_handler_cache()
        loaded = await get_loaded_handlers()
        logger.info("Loaded handlers: %s", loaded)
        logger.info("✅ Tüm handler'lar başarıyla yüklendi.")

        # 📌 aiohttp WebApp (Webhook endpoint)
        async def webhook_handler(request: web.Request) -> web.Response:
            try:
                data = await request.json()
                update: Update = Update.de_json(data, app.bot)
                await app.update_queue.put(update)
            except Exception as exc:
                logger.exception("🚨 Webhook verisi işlenemedi: %s", exc)
                return web.Response(status=500, text="Webhook error")
            return web.Response(text="OK")

        web_app = web.Application()
        web_app.router.add_post("/webhook", webhook_handler)

        # 📌 Ayrıca opsiyonel ping server
        if os.getenv("ENABLE_PING_SERVER", "false").lower() == "true":
            web_app.router.add_get("/", lambda _: web.Response(text="✅ Bot alive"))

        port = int(os.getenv("PORT", 8080))
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("🚀 Webhook server started on port %s", port)

        # 📌 Graceful shutdown için sinyal handler
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def signal_handler() -> None:
            logger.info("🛑 Shutdown sinyali alındı")
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        # 📌 Application lifecycle
        await app.initialize()
        await app.start()
        try:
            await stop_event.wait()
        finally:
            logger.info("🔴 Bot durduruluyor...")
            await app.stop()
            await app.shutdown()
            await runner.cleanup()

        return app

    except Conflict as e:
        logger.error("❌ Bot zaten çalışıyor! Diğer örnekleri kapatın.")
        logger.error("Conflict details: %s", e)
        if app:
            try:
                await app.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Webhook temizlendi, tekrar deneyin...")
                await asyncio.sleep(10)
            except Exception:
                pass
        sys.exit(1)

    except Exception as e:
        logger.exception("🚨 Bot başlatılamadı: %s", str(e))
        raise


def main() -> None:
    """Ana giriş noktası."""
    try:
        logger.info("🤖 Bot başlatılıyor...")

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            logger.info("Event loop zaten çalışıyor, doğrudan başlatılıyor...")
            loop.create_task(start_bot())
        else:
            logger.info("Event loop başlatılıyor...")
            loop.run_until_complete(start_bot())

    except KeyboardInterrupt:
        logger.warning("⛔ Bot manuel olarak durduruldu.")
    except Conflict:
        logger.error("❌ Bot çakışması! Lütfen diğer bot örneklerini kapatın.")
    except Exception as e:
        logger.exception("🚨 Bot başlatılamadı: %s", str(e))


if __name__ == "__main__":
    main()
