"""
/p komutları için Telegram handler.

Komutlar:
/p → CONFIG.SCAN_SYMBOLS (default filtre, örn. btc → BTCUSDT)
/Pn → Hacme göre ilk n coin (örn. /P10)
/Pd → Günlük en çok düşen coinler
/P coin1 coin2 ... → Manuel seçili coinler (btc, eth, sol gibi)

Aiogram 3.x Router pattern ile uyumlu hale getirilmiştir.
"""
"""
/p komutları için Telegram handler.
"""

import logging
from typing import List, Tuple
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils.binance.binance_a import BinanceAPI
from config import CONFIG

logger = logging.getLogger(__name__)

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
    lines = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]
    for idx, (symbol, change, volume, price) in enumerate(data, start=1):
        lines.append(
            f"{idx}. {symbol}: {change:.2f}% | {_format_number(volume)} | {price}"
        )
    return "\n".join(lines)

async def _get_tickers(binance: BinanceAPI) -> List[dict]:
    return await binance.public.get_all_24h_tickers()

async def _filter_symbols(symbols: List[str], tickers: List[dict]) -> List[Tuple[str, float, float, float]]:
    results = []
    for s in symbols:
        symbol = s.upper()
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"
        ticker = next((t for t in tickers if t["symbol"] == symbol), None)
        if ticker:
            results.append((
                symbol.replace("USDT", ""),
                float(ticker.get("priceChangePercent", 0)),
                float(ticker.get("quoteVolume", 0)),
                float(ticker.get("lastPrice", 0))
            ))
    return results

async def handle_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = context.args or []
        binance = BinanceAPI._instance
        
        if not binance:
            await update.message.reply_text("❌ Binance API bağlantısı kurulamadı")
            return
            
        tickers = await _get_tickers(binance)

        if not args:
            symbols = CONFIG.SCAN_SYMBOLS
            data = await _filter_symbols(symbols, tickers)
            text = _format_report("SCAN_SYMBOLS (Hacme Göre)", data)

        elif args[0].isdigit():
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
                key=lambda x: x[2],
                reverse=True,
            )
            data = sorted_data[:min(n, 20)]
            text = _format_report(f"En Yüksek Hacimli {n} Coin", data)

        elif args[0].lower() == "d":
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
                key=lambda x: x[1],
            )
            data = sorted_data[:20]
            text = _format_report("Düşüş Trendindeki Coinler", data)

        else:
            symbols = args
            data = await _filter_symbols(symbols, tickers)
            if not data:
                text = "❌ Belirtilen coinler bulunamadı"
            else:
                text = _format_report("Seçili Coinler", data)

        await update.message.reply_text(text[:4096])

    except Exception as e:
        logger.error(f"❌ /p komutu işlenirken hata: {e}")
        await update.message.reply_text("❌ Bir hata oluştu, lütfen daha sonra tekrar deneyin")

def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler(["p", "P"], handle_scan))
    logger.info("✅ /p komut handler'ı kaydedildi")
