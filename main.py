"""
main.py - Telegram Bot Ana Giriş Noktası

🔐 Güvenli yapı: .env ile secret yönetimi
⚙️ Katmanlı mimari: Config, handler loader, async yapı
📦 Modüler yapı: Handler'lar otomatik yüklenir
"""

import asyncio
import logging

from telegram.ext import Application, ApplicationBuilder

from utils.config import get_config, BinanceConfig
from utils.handler_loader import load_handlers


# Logging yapılandırması
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger: logging.Logger = logging.getLogger(__name__)


async def start_bot() -> None:
    """
    Telegram botu başlatır. Config'i yükler, handler'ları ekler ve uygulamayı çalıştırır.

    Raises:
        Exception: Config eksikse ya da başlatma sırasında hata oluşursa
    """
    # ✅ Config'i yükle (.env ile override edilen singleton yapı)
    config: BinanceConfig = await get_config()

    # 🔐 GÜVENLİK - .env'den API Key (print etmiyoruz - sadece kontrol)
    if not config.api_key or not config.secret_key:
        raise ValueError(
            "❌ API Key veya Secret eksik! Lütfen .env dosyanızı kontrol edin.\n"
            "  -> Gerekli alanlar: BINANCE_API_KEY, BINANCE_API_SECRET"
        )

    logger.info("🔐 API Key ve Secret yüklendi")

    # ⚙️ TECHNICAL - Default değerlerden log
    logger.info("⚙️ Teknik Ayarlar:")
    logger.info(f" - Request Timeout: {config.REQUEST_TIMEOUT}")
    logger.info(f" - Max Requests: {config.MAX_REQUESTS_PER_SECOND}")
    logger.info(f" - Max Connections: {config.MAX_CONNECTIONS}")

    # 📊 BUSINESS - İzlenen semboller & eşikler
    logger.info("📊 İzlenecek Semboller:")
    for symbol in config.SCAN_SYMBOLS:
        logger.info(f" - {symbol}")
    logger.info(f"🎯 Fiyat Uyarı Eşiği: %{config.ALERT_PRICE_CHANGE_PERCENT}")

    # ✅ Telegram bot uygulamasını başlat
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN eksik! .env dosyasını kontrol edin.")

    app: Application = ApplicationBuilder().token(bot_token).build()

    # 🔌 Handler'ları yükle
    await load_handlers(app)

    logger.info("✅ Tüm handler'lar başarıyla yüklendi. Bot başlatılıyor...")

    # 🚀 Botu çalıştır
    await app.run_polling()


def main() -> None:
    """
    Ana giriş noktası. Async event loop başlatır.
    """
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.warning("⛔ Bot manuel olarak durduruldu.")
    except Exception as e:
        logger.exception(f"🚨 Bot başlatılamadı: {str(e)}")


if __name__ == "__main__":
    main()
