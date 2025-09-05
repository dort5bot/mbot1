"""
main.py - Telegram Bot Ana Giriş Noktası

🔐 Güvenli yapı: .env ile secret yönetimi
⚙️ Katmanlı mimari: Config, handler loader, async yapı
📦 Modüler yapı: Handler'lar otomatik yüklenir
async uyumlu + PEP8 + type hints + docstring + async yapı + singleton + logging olacak
"""
import os
import asyncio
import logging
import nest_asyncio
import sys
import signal

from telegram import Bot    #webhook'u temizle, sadece tek bot örneği çalıştır
from telegram.ext import Application, ApplicationBuilder
from telegram.error import Conflict
from config import get_config, BinanceConfig
from utils.handler_loader import load_handlers, clear_handler_cache, get_loaded_handlers

# aiohttp basit ping server
from aiohttp import web

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
    logger.info(f"🌍 Ping server running on port {port}")
    return site


async def start_bot() -> Application:
    """
    Telegram botu başlatır.
    
    Returns:
        Application: Başlatılan Telegram uygulama objesi
    """
    try:
        config: BinanceConfig = await get_config()

        if not config.api_key or not config.secret_key:
            raise ValueError("❌ API Key veya Secret eksik!")

        logger.info("🔐 API Key ve Secret yüklendi")

        # Telegram bot token
        bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN eksik!")

        # Mevcut webhook'u temizle
        bot = Bot(token=bot_token)
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Application oluşturma
        app: Application = ApplicationBuilder().token(bot_token).build()

        # handler_loader
        await load_handlers(app)
        clear_handler_cache()
        loaded = get_loaded_handlers()
        logger.info(f"Loaded handlers: {loaded}")

        logger.info("✅ Tüm handler'lar başarıyla yüklendi. Bot başlatılıyor...")

        # Ping server gerekiyorsa başlat
        ping_site = None
        if os.getenv("ENABLE_PING_SERVER", "false").lower() == "true":
            ping_site = await start_ping_server()

        # Graceful shutdown için sinyal handler'ları
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()
        
        def signal_handler():
            logger.info("🛑 Shutdown sinyali alındı")
            stop_event.set()
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        # Çakışma kontrolü ile polling
        await app.initialize()
        await app.start()
        
        # Uygulama çalışırken stop_event bekleyin
        try:
            await stop_event.wait()
        finally:
            logger.info("🔴 Bot durduruluyor...")
            await app.stop()
            await app.shutdown()
            
            # Ping server'ı durdur
            if ping_site:
                await ping_site._runner.cleanup()
                
        return app

    except Conflict as e:
        logger.error("❌ Bot zaten çalışıyor! Lütfen diğer örnekleri kapatın.")
        logger.error(f"Conflict details: {e}")
        try:
            async with app:
                await app.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Webhook temizlendi, 10 saniye bekleyip tekrar deneyin...")
                await asyncio.sleep(10)
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        logger.exception(f"🚨 Bot başlatılamadı: {str(e)}")
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
        logger.exception(f"🚨 Bot başlatılamadı: {str(e)}")


if __name__ == "__main__":
    main()
