# handlers/p_handler.py
# handlers/p_handler.py
#- 	/p →CONFIG.SCAN_SYMBOLS default(filtre ekler btc ile btcusdt sonuç verir)
#- 	/P n → sayı girilirse limit = n oluyor.
#- 	/P d → düşenler.
#- 	/P coin1 coin2... → manuel seçili coinler.

import logging
import os
from typing import List, Optional, Dict, Any
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils.binance.binance_a import get_binance_client

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

COMMAND = "P"
HELP = (
    "/P → ENV'deki SCAN_SYMBOLS listesi (hacme göre sıralı)\n"
    "/P n → En çok yükselen n coin (varsayılan 20)\n"
    "/P d → En çok düşen 20 coin\n"
    "/P coin1 coin2 ... → Belirtilen coin(ler)"
)

# ENV'den SCAN_SYMBOLS oku
SCAN_SYMBOLS = os.getenv(
    "SCAN_SYMBOLS",
    "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,TRXUSDT,CAKEUSDT,SUIUSDT,PEPEUSDT,ARPAUSDT,TURBOUSDT"
).split(",")


def normalize_symbol(sym: str) -> str:
    """
    Sembol adını normalize eder (büyük harfe çevirir ve USDT ekler).
    
    Args:
        sym: Normalize edilecek sembol adı
        
    Returns:
        Normalize edilmiş sembol adı (örn: 'BTC' → 'BTCUSDT')
    """
    sym = sym.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    return sym


async def fetch_ticker_data(
    symbols: Optional[List[str]] = None, 
    descending: bool = True, 
    sort_by: str = "change"
) -> List[Dict[str, Any]]:
    """
    Binance'ten ticker verilerini alır ve filtreler/sıralar.
    
    Args:
        symbols: İstenen sembol listesi (None ise tüm USDT çiftleri)
        descending: Sıralama yönü (True: azalan, False: artan)
        sort_by: Sıralama kriteri ("change" veya "volume")
        
    Returns:
        Filtrelenmiş ve sıralanmış ticker verileri listesi
    """
    try:
        api = get_binance_client(None, None)  # Global instance
        data = await api.get_all_24h_tickers()
        
        if not data:
            LOG.warning("Binance'ten veri alınamadı")
            return []
            
        # Sadece USDT pariteleri
        usdt_pairs = [d for d in data if d["symbol"].endswith("USDT")]
        
        # İstenen coinler varsa filtrele
        if symbols:
            wanted = {normalize_symbol(s) for s in symbols}
            usdt_pairs = [d for d in usdt_pairs if d["symbol"] in wanted]
            
        # Sıralama
        if sort_by == "volume":
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
        else:
            usdt_pairs.sort(
                key=lambda x: float(x["priceChangePercent"]), 
                reverse=descending
            )
            
        return usdt_pairs[:20]
        
    except Exception as e:
        LOG.error(f"Ticker verisi alınırken hata: {e}")
        return []


def format_report(data: List[Dict[str, Any]], title: str) -> str:
    """
    Ticker verilerini okunabilir bir rapor formatına dönüştürür.
    
    Args:
        data: Ticker verileri listesi
        title: Rapor başlığı
        
    Returns:
        Biçimlendirilmiş rapor metni
    """
    if not data:
        return "Gösterilecek veri yok."
        
    lines = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat"]
    
    for i, coin in enumerate(data, start=1):
        try:
            symbol = coin["symbol"].replace("USDT", "")
            change = float(coin["priceChangePercent"])
            vol_usd = float(coin["quoteVolume"])
            price = float(coin["lastPrice"])
            
            # Hacim M veya B formatı
            if vol_usd >= 1_000_000_000:
                vol_fmt = f"${vol_usd/1_000_000_000:.1f}B"
            else:
                vol_fmt = f"${vol_usd/1_000_000:.1f}M"
                
            lines.append(f"{i}. {symbol}: {change:.2f}% | {vol_fmt} | {price}")
            
        except (KeyError, ValueError) as e:
            LOG.warning(f"Veri formatlama hatası: {e}")
            continue
            
    return "\n".join(lines)


async def p_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /P komutunu işler ve kripto para verilerini gösterir.
    
    Args:
        update: Telegram güncelleme nesnesi
        context: Telegram bağlam nesnesi
    """
    try:
        args = context.args
        
        if not args:
            # /P → ENV'deki SCAN_SYMBOLS, hacme göre sıralı
            data = await fetch_ticker_data(symbols=SCAN_SYMBOLS, sort_by="volume")
            title = "SCAN_SYMBOLS (Hacme Göre)"
        elif args[0].lower() == "d":
            data = await fetch_ticker_data(descending=False)
            title = "Düşüş Trendindeki Coinler"
        elif args[0].isdigit():
            n = int(args[0])
            data = await fetch_ticker_data(descending=True)
            data = data[:n] if n <= len(data) else data
            title = f"En Çok Yükselen {n} Coin"
        else:
            data = await fetch_ticker_data(symbols=args)
            title = "Seçili Coinler"
            
        if not data:
            await update.message.reply_text("Veri alınamadı veya eşleşen sembol bulunamadı.")
            return
            
        report = format_report(data, title)
        await update.message.reply_text(report)
        
    except Exception as e:
        LOG.error(f"/P komutu işlenirken hata: {e}")
        await update.message.reply_text("Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


def register(application) -> None:
    """
    Telegram botu için komut işleyicilerini kaydeder.
    
    Args:
        application: Telegram bot uygulama nesnesi
    """
    try:
        for cmd in ("P", "p"):  # Büyük/küçük harf desteği
            application.add_handler(CommandHandler(cmd, p_handler))
            
        LOG.info("P handler başarıyla kaydedildi.")
        
    except Exception as e:
        LOG.error(f"P handler kaydedilirken hata: {e}")
