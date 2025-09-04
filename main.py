"""
main.py - Telegram Bot Ana Giriş Noktası

🔐 Güvenli yapı: .env ile secret yönetimi
⚙️ Katmanlı mimari: Config, handler loader, async yapı
📦 Modüler yapı: Handler'lar otomatik yüklenir
# PEP8 + type hints + docstring + async yapı + singleton + logging + Async Yapı olacak
"""

import os
import asyncio
import logging
import nest_asyncio

from telegram.ext import Application, ApplicationBuilder
from config import get_config, BinanceConfig
from utils.handler_loader import load_handlers, clear_handler_cache, get_loaded_handlers

# Event loop çakışmalarını önlemek için (import'tan sonra)
nest_asyncio.apply()

# Logging yapılandırması
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger: logging.Logger = logging.getLogger(__name__)

async def start_bot() -> None:
    """Telegram botu başlatır."""
    app = None
    try:
        config: BinanceConfig = await get_config()

        if not config.api_key or not config.secret_key:
            raise ValueError("❌ API Key veya Secret eksik!")

        logger.info("🔐 API Key ve Secret yüklendi")

        # Teknik ayarlar
        logger.info("⚙️ Teknik Ayarlar:")
        logger.info(f" - Request Timeout: {config.REQUEST_TIMEOUT}")
        logger.info(f" - Max Requests: {config.MAX_REQUESTS_PER_SECOND}")
        logger.info(f" - Max Connections: {config.MAX_CONNECTIONS}")

        # İzlenen semboller
        logger.info("📊 İzlenecek Semboller:")
        for symbol in config.SCAN_SYMBOLS:
            logger.info(f" - {symbol}")
        logger.info(f"🎯 Fiyat Uyarı Eşiği: %{config.ALERT_PRICE_CHANGE_PERCENT}")

        # Telegram bot token
        bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN eksik!")

        # Application oluşturma
        app = ApplicationBuilder().token(bot_token).build()

        # handler_loader Handler'ları yükle
        await load_handlers(app)
        # handler_loader Cache'i temizle (yeniden yüklemek için)
        clear_handler_cache()
        # handler_loader Yüklenmiş handler'ları listele
        loaded = get_loaded_handlers()
        logger.info(f"Loaded handlers: {loaded}")

        logger.info("✅ Tüm handler'lar başarıyla yüklendi. Bot başlatılıyor...")

        # Botu çalıştır - run_polling yerine manual loop yönetimi
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # Sonsuz döngü
        while True:
            await asyncio.sleep(3600)  # Her saat kontrol et
            
    except Exception as e:
        logger.exception(f"🚨 Bot başlatılamadı: {str(e)}")
        if app:
            await app.stop()
            await app.shutdown()
        raise

def main() -> None:
    """Ana giriş noktası."""
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        logger.warning("⛔ Bot manuel olarak durduruldu.")
    except Exception as e:
        logger.exception(f"🚨 Bot başlatılamadı: {str(e)}")

if __name__ == "__main__":
    main()
