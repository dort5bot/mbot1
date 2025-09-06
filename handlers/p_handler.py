"""
handlers/p_handler.py
/p →CONFIG.SCAN_SYMBOLS default(filtre ekler btc ile btcusdt sonuç verir)
/P n → sayı girilirse hacimli ilk n coin
/P d → düşenler.
/P coin1 coin2... → manuel seçili coinler.
Binance datasında küçük/büyük fark olsa da eşleşir.
async uyumlu + PEP8 + type hints + docstring + async yapı + singleton + logging olacak
"""

import logging
import os
from typing import List, Optional, Dict, Any, Set
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils.binance.binance_a import get_binance_client

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

COMMAND: str = "P"
HELP: str = (
    "/P → ENV'deki SCAN_SYMBOLS listesi (hacme göre sıralı)\n"
    "/P n → En çok yükselen n coin (varsayılan 20)\n"
    "/P d → En çok düşen 20 coin\n"
    "/P coin1 coin2 ... → Belirtilen coin(ler)"
)

# ENV'den SCAN_SYMBOLS oku ve normalize et
SCAN_SYMBOLS: List[str] = [
    s.strip().upper() if s.strip().endswith("USDT") else s.strip().upper() + "USDT"
    for s in os.getenv(
        "SCAN_SYMBOLS",
        "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,TRXUSDT,CAKEUSDT,SUIUSDT,PEPEUSDT,ARPAUSDT,TURBOUSDT"
    ).split(",")
]


def normalize_symbol(sym: str) -> str:
    """Sembol adını normalize eder (ör. bnb → BNBUSDT)."""
    sym = sym.strip().upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    return sym


async def fetch_ticker_data(
    symbols: Optional[List[str]] = None,
    descending: bool = True,
    sort_by: str = "change",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Binance'ten ticker verilerini alır, filtreler ve sıralar.

    Args:
        symbols (Optional[List[str]]): İstenen semboller (örn: ["BTC", "ETHUSDT"]).
        descending (bool): Sıralama yönü. Default True.
        sort_by (str): "change" veya "volume".
        limit (Optional[int]): Kaç adet sonuç döneceği.

    Returns:
        List[Dict[str, Any]]: Ticker verileri.
    """
    try:
        api = get_binance_client(None, None)
        data: List[Dict[str, Any]] = await api.get_all_24h_tickers()

        if not data:
            LOG.warning("Binance'ten veri alınamadı")
            return []

        # Sadece USDT pariteleri
        usdt_pairs: List[Dict[str, Any]] = [
            d for d in data if d.get("symbol", "").upper().endswith("USDT")
        ]

        # İstenen coinler varsa filtrele
        if symbols:
            wanted: Set[str] = {normalize_symbol(s) for s in symbols}
            usdt_pairs = [
                d for d in usdt_pairs if d.get("symbol", "").upper() in wanted
            ]

        # Sıralama
        if sort_by == "volume":
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
        else:
            usdt_pairs.sort(
                key=lambda x: float(x["priceChangePercent"]),
                reverse=descending
            )

        return usdt_pairs[:limit] if limit else usdt_pairs

    except Exception as e:
        LOG.error(f"Ticker verisi alınırken hata: {e}")
        return []


def format_report(data: List[Dict[str, Any]], title: str) -> str:
    """Ticker verilerini okunabilir bir rapor formatına dönüştürür."""
    if not data:
        return "Gösterilecek veri yok."

    lines: List[str] = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]

    for i, coin in enumerate(data, start=1):
        try:
            symbol: str = coin["symbol"].replace("USDT", "")
            change: float = float(coin["priceChangePercent"])
            vol_usd: float = float(coin["quoteVolume"])
            price: float = float(coin["lastPrice"])

            # Hacim formatı
            if vol_usd >= 1_000_000_000:
                vol_fmt = f"${vol_usd/1_000_000_000:.1f}B"
            elif vol_usd >= 1_000_000:
                vol_fmt = f"${vol_usd/1_000_000:.1f}M"
            else:
                vol_fmt = f"${vol_usd:,.0f}"

            lines.append(
                f"{i}. {symbol}: {change:+.2f}% | {vol_fmt} | {price:.8f}"
            )

        except (KeyError, ValueError) as e:
            LOG.warning(f"Veri formatlama hatası: {e}")
            continue

    return "\n".join(lines)


async def p_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/P komutunu işler ve kripto para verilerini gösterir."""
    try:
        if not update.message:
            return

        args: List[str] = context.args or []

        if not args:
            # /P → ENV'deki SCAN_SYMBOLS, hacme göre sıralı
            data = await fetch_ticker_data(symbols=SCAN_SYMBOLS, sort_by="volume")
            title = "SCAN_SYMBOLS (Hacme Göre)"
        elif args[0].lower() == "d":
            # /P d → Düşenler
            data = await fetch_ticker_data(descending=False, limit=20)
            title = "Düşüş Trendindeki Coinler"
        elif args[0].isdigit():
            # /P n → n sayıda coin
            n: int = min(int(args[0]), 50)  # Maksimum 50 coin gösterilsin
            data = await fetch_ticker_data(descending=True, limit=n)
            title = f"En Çok Yükselen {n} Coin"
        else:
            # /P coin1 coin2... → Manuel seçim
            data = await fetch_ticker_data(symbols=args)
            title = "Seçili Coinler"

        if not data:
            await update.message.reply_text(
                "Veri alınamadı veya eşleşen sembol bulunamadı."
            )
            return

        report: str = format_report(data, title)

        # Telegram mesaj sınırı (4096 karakter) kontrolü
        if len(report) > 4096:
            report = (
                report[:4000]
                + "\n...\n(Mesaj sınırı aşıldı, bazı veriler gösterilemiyor)"
            )

        await update.message.reply_text(report)

    except Exception as e:
        LOG.error(f"/P komutu işlenirken hata: {e}")
        await update.message.reply_text("Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


def register(application: Application) -> None:
    """Telegram botu için komut işleyicilerini kaydeder."""
    try:
        application.add_handler(CommandHandler("p", p_handler))
        application.add_handler(CommandHandler("P", p_handler))
        LOG.info("P handler başarıyla kaydedildi.")
    except Exception as e:
        LOG.error(f"P handler kaydedilirken hata: {e}")


