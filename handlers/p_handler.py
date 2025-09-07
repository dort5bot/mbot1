"""
/p komutları için Telegram handler.

Komutlar:
/p → CONFIG.SCAN_SYMBOLS (default filtre, örn. btc → BTCUSDT)
/Pn → Hacme göre ilk n coin (örn. /P10)
/Pd → Günlük en çok düşen coinler
/P coin1 coin2 ... → Manuel seçili coinler (btc, eth, sol gibi)

Aiogram 3.x Router pattern ile uyumlu hale getirilmiştir.
"""

import logging
from typing import List, Tuple, Optional
from aiogram import types, Router
from aiogram.filters import Command

from utils.binance.binance_a import BinanceAPI
from config import CONFIG

logger = logging.getLogger(__name__)
router = Router(name="p_handler")


def _format_number(num: float) -> str:
    """Rakamları kısaltmalı formatla (örn. 1234567 → $1.23M)."""
    if num >= 1e9:
        return f"${num/1e9:.1f}B"
    if num >= 1e6:
        return f"${num/1e6:.1f}M"
    if num >= 1e3:
        return f"${num/1e3:.1f}K"
    return f"${num:.1f}"


def _format_report(title: str, data: List[Tuple[str, float, float, float]]) -> str:
    """
    Raporu string formatında hazırla.

    Args:
        title: Başlık
        data: (symbol, priceChangePercent, volume, lastPrice)

    Returns:
        Hazır mesaj stringi
    """
    lines = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]
    for idx, (symbol, change, volume, price) in enumerate(data, start=1):
        lines.append(
            f"{idx}. {symbol}: {change:.2f}% | {_format_number(volume)} | {price}"
        )
    return "\n".join(lines)


async def _get_tickers(binance: BinanceAPI) -> List[dict]:
    """Binance spot 24h ticker datasını çek."""
    return await binance.public.get_all_24h_tickers()


async def _filter_symbols(symbols: List[str], tickers: List[dict]) -> List[Tuple[str, float, float, float]]:
    """Seçilen sembolleri filtrele ve normalize et (btc → BTCUSDT)."""
    results = []
    for s in symbols:
        symbol = s.upper()
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"
        ticker = next((t for t in tickers if t["symbol"] == symbol), None)
        if ticker:
            results.append((
                symbol.replace("USDT", ""),  # sadece coin ismi
                float(ticker.get("priceChangePercent", 0)),
                float(ticker.get("quoteVolume", 0)),
                float(ticker.get("lastPrice", 0))
            ))
    return results


@router.message(Command("p", "P"))
async def handle_scan(message: types.Message) -> None:
    """
    /p komutlarını işle.

    Args:
        message: Telegram message
    """
    try:
        args = message.text.split()[1:]  # /p'den sonraki argümanlar
        binance = BinanceAPI._instance
        
        if not binance:
            await message.answer("❌ Binance API bağlantısı kurulamadı")
            return
            
        tickers = await _get_tickers(binance)

        if not args:
            # default: CONFIG.SCAN_SYMBOLS
            symbols = CONFIG.SCAN_SYMBOLS
            data = await _filter_symbols(symbols, tickers)
            text = _format_report("SCAN_SYMBOLS (Hacme Göre)", data)

        elif args[0].isdigit():
            # /Pn → hacimli ilk n
            n = int(args[0])
            usdt_tickers = [t for t in tickers if t["symbol"].endswith("USDT")]
            sorted_data = sorted(
                (
                    (
                        t["symbol"].replace("USDT", ""),
                        float(t.get("priceChangePercent", 0)),
                        float(t.get("quoteVolume", 0)),
                        float(t.get("lastPrice", 0)),
                    )
                    for t in usdt_tickers
                ),
                key=lambda x: x[2],  # volume'a göre sırala
                reverse=True,
            )
            data = sorted_data[:min(n, 20)]  # max 20 coin
            text = _format_report(f"En Yüksek Hacimli {n} Coin", data)

        elif args[0].lower() == "d":
            # /Pd → düşenler
            usdt_tickers = [t for t in tickers if t["symbol"].endswith("USDT")]
            sorted_data = sorted(
                (
                    (
                        t["symbol"].replace("USDT", ""),
                        float(t.get("priceChangePercent", 0)),
                        float(t.get("quoteVolume", 0)),
                        float(t.get("lastPrice", 0)),
                    )
                    for t in usdt_tickers
                ),
                key=lambda x: x[1],  # change %'ye göre sırala (en düşük)
            )
            data = sorted_data[:20]  # ilk 20 düşen
            text = _format_report("Düşüş Trendindeki Coinler", data)

        else:
            # manuel seçilen coinler
            symbols = args
            data = await _filter_symbols(symbols, tickers)
            if not data:
                text = "❌ Belirtilen coinler bulunamadı"
            else:
                text = _format_report("Seçili Coinler", data)

        await message.answer(text[:4096])  # Telegram mesaj sınırı

    except Exception as e:
        logger.error(f"❌ /p komutu işlenirken hata: {e}")
        await message.answer("❌ Bir hata oluştu, lütfen daha sonra tekrar deneyin")


def register_handlers(main_router: Router) -> None:
    """Handler'ları ana router'a kaydet (aiogram 3.x style)"""
    main_router.include_router(router)
    logger.info("✅ /p komut handler'ı kaydedildi")
