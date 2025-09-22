# handlers/p_handler.py
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from typing import List, Dict, Any

from utils.binance.binance_a import get_or_create_binance_api
from bot.config import Config  # config.py'den import

logger = logging.getLogger(__name__)
router = Router()

# Yardımcı fonksiyon: sayıyı formatla
def format_number(value: float, precision: int = 2) -> str:
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.2f}K"
    return f"${value:.{precision}f}"

# Yardımcı fonksiyon: coin listesini tabloya çevir
def format_report(title: str, data: List[Dict[str, Any]]) -> str:
    lines = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]
    for idx, t in enumerate(data, 1):
        symbol = t.get("symbol", "N/A").replace("USDT", "")
        change = float(t.get("priceChangePercent", 0))
        volume = float(t.get("quoteVolume", 0))
        price = float(t.get("lastPrice", t.get("price", 0)))
        lines.append(
            f"{idx}. {symbol}: {change:+.2f}% | {format_number(volume)} | {price:.4f}"
        )
    return "\n".join(lines)

# /p komutu → özel coinler veya SCAN_SYMBOLS
@router.message(Command("p"))
async def cmd_p(message: Message, config: Config):
    try:
        args = message.text.strip().split()[1:]
        if args:
            symbols = [s.upper() + "USDT" if not s.upper().endswith("USDT") else s.upper() for s in args]
        else:
            symbols = config.SCAN_SYMBOLS  # config'ten al

        api = await get_or_create_binance_api()
        data = await api.get_custom_symbols_data(symbols)

        if not data:
            await message.answer("❌ Veri bulunamadı.")
            return

        text = format_report("Seçili Coinler" if args else "SCAN_SYMBOLS (Hacme Göre)", data)
        await message.answer(text)
    except Exception as e:
        logger.error(f"/p komutu hatası: {e}", exc_info=True)
        await message.answer("❌ Komut çalıştırılırken hata oluştu.")

# /pg komutu → en çok yükselenler
@router.message(Command("pg"))
async def cmd_pg(message: Message):
    try:
        args = message.text.strip().split()[1:]
        limit = int(args[0]) if args else 20

        api = await get_or_create_binance_api()
        data = await api.get_top_gainers_with_volume(limit=limit)

        if not data:
            await message.answer("❌ Veri bulunamadı.")
            return

        text = format_report(f"En Çok Yükselenler (Top {limit})", data)
        await message.answer(text)
    except Exception as e:
        logger.error(f"/pg komutu hatası: {e}", exc_info=True)
        await message.answer("❌ Komut çalıştırılırken hata oluştu.")

# /pl komutu → en çok düşenler
@router.message(Command("pl"))
async def cmd_pl(message: Message):
    try:
        args = message.text.strip().split()[1:]
        limit = int(args[0]) if args else 20

        api = await get_or_create_binance_api()
        data = await api.get_top_losers_with_volume(limit=limit)

        if not data:
            await message.answer("❌ Veri bulunamadı.")
            return

        text = format_report(f"En Çok Düşenler (Top {limit})", data)
        await message.answer(text)
    except Exception as e:
        logger.error(f"/pl komutu hatası: {e}", exc_info=True)
        await message.answer("❌ Komut çalıştırılırken hata oluştu.")

# /test_api komutu → Binance API bağlantı testi
@router.message(Command("test_api"))
async def cmd_test_api(message: Message):
    try:
        api = await get_or_create_binance_api()
        health = await api.system_health_check()

        text = (
            "✅ Binance API Testi\n"
            f"📡 Ping: {health['ping']}\n"
            f"🔑 API Keys: {health['api_keys_valid']}\n"
            f"🕒 Server Time: {health['server_time']}\n"
            f"🚦 Circuit Breaker: {health['circuit_breaker_state']}\n"
            f"📊 Cache Stats: {health['cache_stats']}\n"
            f"⚙️ System Status: {health['system_status']}"
        )
        await message.answer(text)
    except Exception as e:
        logger.error(f"/test_api komutu hatası: {e}", exc_info=True)
        await message.answer("❌ Binance API testi başarısız oldu.")
