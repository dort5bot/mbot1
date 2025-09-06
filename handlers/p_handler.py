"""
handlers/p_handler.py
binance_a.py uyunlu
/p →CONFIG.SCAN_SYMBOLS default(filtre ekler btc ile btcusdt sonuç verir)
/P n → sayı girilirse hacimli ilk n coin
/P d → düşenler.
/P coin1 coin2... → manuel seçili coinler.
Binance datasında küçük/büyük fark olsa da eşleşir.
async uyumlu + PEP8 + type hints + docstring + async yapı + singleton + logging olacak

sorun olursa komut yapısı 
/p,pn,pd,p coin
"""

import logging
import os
from typing import List, Optional, Dict, Any, Set
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Binance client import - güncellenmiş yapıya göre
from utils.binance.binance_a import BinanceClient

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

# Singleton Binance client instance
_binance_client: Optional[BinanceClient] = None


async def get_binance_client() -> BinanceClient:
    """
    Binance client singleton instance'ını döndürür.
    
    Returns:
        BinanceClient: Binance API client instance
    """
    global _binance_client
    if _binance_client is None:
        # Environment variables'dan API key'leri al
        api_key = os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_API_SECRET")
        
        _binance_client = BinanceClient(api_key=api_key, secret_key=secret_key)
        LOG.info("Binance client initialized")
    
    return _binance_client


def normalize_symbol(sym: str) -> str:
    """
    Sembol adını normalize eder (ör. bnb → BNBUSDT).
    
    Args:
        sym: Sembol adı
        
    Returns:
        Normalize edilmiş sembol adı
    """
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
        symbols: İstenen semboller (örn: ["BTC", "ETHUSDT"])
        descending: Sıralama yönü. Default True
        sort_by: "change" veya "volume"
        limit: Kaç adet sonuç döneceği

    Returns:
        Ticker verileri listesi
    """
    try:
        # Binance client'ı al
        client = await get_binance_client()
        
        # Tüm ticker verilerini al
        all_tickers = await client.public.get_all_24h_tickers()
        
        if not all_tickers:
            LOG.warning("Binance'ten veri alınamadı")
            return []

        # Sadece USDT pariteleri
        usdt_pairs: List[Dict[str, Any]] = [
            d for d in all_tickers if isinstance(d, dict) and 
            d.get("symbol", "").upper().endswith("USDT")
        ]

        # İstenen coinler varsa filtrele
        if symbols:
            wanted: Set[str] = {normalize_symbol(s) for s in symbols}
            usdt_pairs = [
                d for d in usdt_pairs if d.get("symbol", "").upper() in wanted
            ]

        # Sıralama
        if sort_by == "volume":
            usdt_pairs.sort(
                key=lambda x: float(x.get("quoteVolume", 0)), 
                reverse=descending
            )
        else:
            usdt_pairs.sort(
                key=lambda x: float(x.get("priceChangePercent", 0)),
                reverse=descending
            )

        return usdt_pairs[:limit] if limit else usdt_pairs

    except Exception as e:
        LOG.error(f"Ticker verisi alınırken hata: {e}")
        return []


def format_report(data: List[Dict[str, Any]], title: str) -> str:
    """
    Ticker verilerini okunabilir bir rapor formatına dönüştürür.
    
    Args:
        data: Ticker verileri
        title: Rapor başlığı
        
    Returns:
        Formatlanmış rapor metni
    """
    if not data:
        return "Gösterilecek veri yok."

    lines: List[str] = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]

    for i, coin in enumerate(data, start=1):
        try:
            symbol: str = coin.get("symbol", "").replace("USDT", "")
            change: float = float(coin.get("priceChangePercent", 0))
            vol_usd: float = float(coin.get("quoteVolume", 0))
            price: float = float(coin.get("lastPrice", 0))

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

        except (KeyError, ValueError, TypeError) as e:
            LOG.warning(f"Veri formatlama hatası: {e}, coin: {coin.get('symbol', 'unknown')}")
            continue

    return "\n".join(lines)


async def p_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /P komutunu işler ve kripto para verilerini gösterir.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
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
        LOG.error(f"/P komutu işlenirken hata: {e}", exc_info=True)
        await update.message.reply_text("Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


def register(application: Application) -> None:
    """
    Telegram botu için komut işleyicilerini kaydeder.
    
    Args:
        application: Telegram Application instance
    """
    try:
        application.add_handler(CommandHandler("p", p_handler))
        application.add_handler(CommandHandler("P", p_handler))
        LOG.info("P handler başarıyla kaydedildi.")
    except Exception as e:
        LOG.error(f"P handler kaydedilirken hata: {e}")
