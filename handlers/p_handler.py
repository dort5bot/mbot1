"""handlers/p_handler.py
Binance API ile coin verilerini çeken /p komutu handler'ı.

Aiogram 3.x Router pattern'ine uygun, async/await yapısında,
type hints + docstring + logging ile geliştirilmiştir.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.markdown import code

from config import get_config
from utils.binance.binance_a import BinanceAPI
from utils.binance.binance_request import BinanceHTTPClient
from utils.binance.binance_circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Router oluştur - HANDLER_LOADER İÇİN GEREKLİ
router = Router(name="p_handler")

# Global BinanceAPI instance
_binance_instance: Optional[BinanceAPI] = None


async def get_binance() -> BinanceAPI:
    """BinanceAPI singleton instance'ını döndürür."""
    global _binance_instance
    if _binance_instance is None:
        config = await get_config()
        
        # HTTP client ve circuit breaker oluştur
        http_client = BinanceHTTPClient(
            api_key=config.BINANCE_API_KEY,
            secret_key=config.BINANCE_API_SECRET,
            base_url=config.BINANCE_BASE_URL,
            fapi_url=config.BINANCE_FAPI_URL
        )
        
        circuit_breaker = CircuitBreaker(
            max_requests=config.MAX_REQUESTS_PER_MINUTE,
            timeout=config.REQUEST_TIMEOUT
        )
        
        _binance_instance = BinanceAPI(http_client, circuit_breaker)
        logger.info("✅ BinanceAPI instance created for p_handler")
    
    return _binance_instance


async def fetch_all_tickers() -> List[Dict[str, Any]]:
    """Tüm ticker verilerini Binance'tan çeker."""
    try:
        binance = await get_binance()
        tickers = await binance.public.get_all_24h_tickers()
        return tickers
    except Exception as e:
        logger.error(f"❌ Ticker verileri çekilemedi: {e}")
        return []


def format_volume(volume: float) -> str:
    """Hacim değerini formatlar (Milyon/Bilyon)."""
    if volume >= 1_000_000_000:
        return f"${volume/1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume/1_000:.1f}K"
    else:
        return f"${volume:.1f}"


def format_price(price: float) -> str:
    """Fiyat değerini uygun formatta gösterir."""
    if price >= 1000:
        return f"{price:,.1f}"
    elif price >= 1:
        return f"{price:.2f}"
    elif price >= 0.01:
        return f"{price:.4f}"
    else:
        return f"{price:.8f}"


def format_percentage(change: float) -> str:
    """Yüzde değişimi formatlar."""
    return f"{change:+.2f}%"


async def generate_price_message(tickers: List[Dict[str, Any]], 
                               mode: str = "default",
                               limit: int = 20,
                               custom_symbols: Optional[List[str]] = None) -> str:
    """Fiyat mesajını oluşturur."""
    if not tickers:
        return "❌ Veri alınamadı. Lütfen daha sonra tekrar deneyin."
    
    # Filtreleme ve sıralama
    if mode == "default":
        # CONFIG.SCAN_SYMBOLS ile eşleşenleri bul
        config = await get_config()
        target_symbols = [symbol.upper() for symbol in config.SCAN_SYMBOLS]
        filtered_tickers = [t for t in tickers if t.get('symbol') in target_symbols]
        
        # Hacme göre sırala (büyükten küçüğe)
        filtered_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        title = "📈 SCAN_SYMBOLS (Hacme Göre)"
        
    elif mode == "gainers":
        # Yükselenleri bul ve yüzde değişime göre sırala
        filtered_tickers = [t for t in tickers if float(t.get('priceChangePercent', 0)) > 0]
        filtered_tickers.sort(key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)
        title = f"📈 En Çok Yükselen {limit} Coin"
        
    elif mode == "losers":
        # Düşenleri bul ve yüzde değişime göre sırala
        filtered_tickers = [t for t in tickers if float(t.get('priceChangePercent', 0)) < 0]
        filtered_tickers.sort(key=lambda x: float(x.get('priceChangePercent', 0)))
        title = f"📉 Düşüş Trendindeki {limit} Coin"
        
    elif mode == "custom" and custom_symbols:
        # Özel sembol listesi
        target_symbols = [symbol.upper() for symbol in custom_symbols]
        filtered_tickers = [t for t in tickers if t.get('symbol') in target_symbols]
        
        # Hacme göre sırala
        filtered_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        title = "📈 Seçili Coinler"
        
    else:
        return "❌ Geçersiz mod!"
    
    # Limit uygula
    filtered_tickers = filtered_tickers[:limit]
    
    if not filtered_tickers:
        return "❌ Eşleşen coin bulunamadı."
    
    # Mesajı oluştur
    lines = []
    lines.append(title)
    lines.append("⚡Coin | Değişim | Hacim | Fiyat")
    
    for i, ticker in enumerate(filtered_tickers, 1):
        symbol = ticker.get('symbol', 'N/A')
        change_percent = float(ticker.get('priceChangePercent', 0))
        volume = float(ticker.get('quoteVolume', 0))
        price = float(ticker.get('lastPrice', 0))
        
        # Sembolü kısalt (USDT'yi kaldır)
        display_symbol = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol
        
        line = (f"{i}. {display_symbol}: "
                f"{format_percentage(change_percent)} | "
                f"{format_volume(volume)} | "
                f"{format_price(price)}")
        lines.append(line)
    
    # Son güncelleme zamanı
    lines.append(f"\n🕒 Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")
    
    return "\n".join(lines)


@router.message(Command("p"))
async def p_command_handler(message: Message):
    """Ana /p komutu handler'ı."""
    try:
        # Rate limiting - HTTP istek sınırlaması circuit breaker ile yönetiliyor
        tickers = await fetch_all_tickers()
        
        if not tickers:
            await message.answer("❌ Binance API'den veri alınamadı. Lütfen daha sonra tekrar deneyin.")
            return
        
        # Komut argümanlarını parse et
        args = message.text.split()[1:]  # /p'den sonraki argümanlar
        
        if not args:
            # /p → SCAN_SYMBOLS default
            response = await generate_price_message(tickers, mode="default")
            
        elif args[0].isdigit():
            # /p20 → ilk 20 coin
            limit = min(int(args[0]), 100)  # Maksimum 100 coin
            response = await generate_price_message(tickers, mode="gainers", limit=limit)
            
        elif args[0].lower() == 'd':
            # /pd veya /pd 30
            limit = 20  # Default
            if len(args) > 1 and args[1].isdigit():
                limit = min(int(args[1]), 100)
            response = await generate_price_message(tickers, mode="losers", limit=limit)
            
        else:
            # /p eth bnb sol → özel sembol listesi
            custom_symbols = []
            for arg in args:
                # Sembolü temizle ve USDT ekle
                clean_arg = arg.upper().strip()
                if not clean_arg.endswith('USDT'):
                    clean_arg += 'USDT'
                custom_symbols.append(clean_arg)
            
            response = await generate_price_message(tickers, mode="custom", custom_symbols=custom_symbols)
        
        # Mesajı code formatında gönder (düzgün hizalama için)
        await message.answer(code(response))
        
    except Exception as e:
        logger.error(f"❌ /p komutu işlenirken hata: {e}")
        await message.answer("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


# Optional: /p komutuna yardımcı diğer varyasyonlar
@router.message(Command("pg"))
async def pg_command_handler(message: Message):
    """/pg → Yükselen coinler (gainers)"""
    try:
        tickers = await fetch_all_tickers()
        args = message.text.split()[1:]
        limit = min(int(args[0]), 100) if args and args[0].isdigit() else 20
        
        response = await generate_price_message(tickers, mode="gainers", limit=limit)
        await message.answer(code(response))
    except Exception as e:
        logger.error(f"❌ /pg komutu işlenirken hata: {e}")
        await message.answer("❌ Bir hata oluştu.")


@router.message(Command("pl"))
async def pl_command_handler(message: Message):
    """/pl → Düşen coinler (losers)"""
    try:
        tickers = await fetch_all_tickers()
        args = message.text.split()[1:]
        limit = min(int(args[0]), 100) if args and args[0].isdigit() else 20
        
        response = await generate_price_message(tickers, mode="losers", limit=limit)
        await message.answer(code(response))
    except Exception as e:
        logger.error(f"❌ /pl komutu işlenirken hata: {e}")
        await message.answer("❌ Bir hata oluştu.")


# Handler_loader için gerekli değil ama iyi practice
async def register_p_handler(main_router: Router):
    """Ana router'a bu router'ı ekler (manuel kayıt için)."""
    main_router.include_router(router)
    logger.info("✅ P handler registered")