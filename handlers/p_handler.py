"""
handlers/p_handler.py
Binance API ile coin verilerini çeken /p komutu handler'ı.

Aiogram 3.x Router pattern'ine uygun, async/await yapısında,
type hints + docstring + logging ile geliştirilmiştir.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import re

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.markdown import code

from config import get_config
from utils.binance.binance_api import get_or_create_binance_api

logger = logging.getLogger(__name__)

# Router oluştur
router = Router(name="p_handler")

# Global BinanceAPI instance
_binance_instance = None

# Emoji constants for better visual representation
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_NEUTRAL = "⚪"
EMOJI_COIN = "💰"
EMOJI_CHART = "📈"
EMOJI_CHART_DOWN = "📉"
EMOJI_FIRE = "🔥"
EMOJI_WARNING = "⚠️"
EMOJI_CLOCK = "🕒"
EMOJI_ROCKET = "🚀"
EMOJI_ARROW_UP = "⬆️"
EMOJI_ARROW_DOWN = "⬇️"

async def get_binance() -> Any:
    """BinanceAPI instance'ını al veya oluştur."""
    global _binance_instance
    if _binance_instance is None:
        try:
            config = await get_config()
            
            _binance_instance = await get_or_create_binance_api(
                api_key=config.BINANCE_API_KEY,
                api_secret=config.BINANCE_API_SECRET,
                cache_ttl=30,
                base_url=config.BINANCE_BASE_URL,
                fapi_url=config.BINANCE_FAPI_URL,
                failure_threshold=config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                reset_timeout=config.CIRCUIT_BREAKER_RESET_TIMEOUT
            )
            
            logger.info("✅ BinanceAPI instance created for p_handler")
            
        except Exception as e:
            logger.error(f"❌ BinanceAPI instance oluşturulamadı: {e}", exc_info=True)
            raise
    
    return _binance_instance

async def fetch_tickers_with_retry(max_retries: int = 3) -> List[Dict[str, Any]]:
    """Retry mekanizmalı ticker veri çekme."""
    for attempt in range(max_retries):
        try:
            binance = await get_binance()
            tickers = await binance.get_all_24h_tickers()
            
            if tickers and len(tickers) > 0:
                logger.info(f"✅ {attempt + 1}. denemede {len(tickers)} ticker alındı")
                return tickers
                
            logger.warning(f"⚠️ Boş veri, {attempt + 1}. deneme")
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ {attempt + 1}. deneme başarısız: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    logger.error(f"❌ Tüm {max_retries} deneme başarısız oldu")
    return []

def format_volume(volume: float) -> str:
    """Hacim değerini uygun formatta gösterir."""
    if volume >= 1_000_000_000:
        return f"${volume/1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume/1_000:.1f}K"
    else:
        return f"${volume:.0f}"

def format_price(price: float) -> str:
    """Fiyat değerini uygun formatta gösterir."""
    if price >= 1000:
        return f"{price:,.0f}"
    elif price >= 1:
        return f"{price:.2f}"
    elif price >= 0.01:
        return f"{price:.4f}"
    elif price >= 0.0001:
        return f"{price:.6f}"
    else:
        return f"{price:.8f}"

def format_percentage(change: float) -> str:
    """Yüzde değişimi formatlar ve emoji ekler."""
    if change > 5:
        emoji = EMOJI_ROCKET
    elif change > 2:
        emoji = EMOJI_FIRE
    elif change > 0:
        emoji = EMOJI_ARROW_UP
    elif change < -5:
        emoji = EMOJI_WARNING
    elif change < 0:
        emoji = EMOJI_ARROW_DOWN
    else:
        emoji = EMOJI_NEUTRAL
    
    return f"{emoji} {change:+.2f}%"

def get_change_emoji(change: float) -> str:
    """Değişim yüzdesine göre emoji döndürür."""
    if change > 10:
        return "🚀"
    elif change > 5:
        return "🔥"
    elif change > 2:
        return "⬆️"
    elif change > 0:
        return "↗️"
    elif change == 0:
        return "➡️"
    elif change > -2:
        return "↘️"
    elif change > -5:
        return "⬇️"
    elif change > -10:
        return "💥"
    else:
        return "📉"

def parse_command_args(text: str) -> Tuple[str, List[str], int]:
    """
    Komut argümanlarını parse eder.
    
    Returns:
        (mode, symbols, limit)
    """
    args = text.split()[1:]  # /p'den sonraki argümanlar
    
    if not args:
        return "default", [], 0
    
    # Sayısal argüman kontrolü (/p20, /p50 gibi)
    if len(args) == 1 and args[0].isdigit():
        limit = min(int(args[0]), 50)
        return "gainers", [], limit
    
    # Düşen coinler (/pd veya /pd 30)
    if args[0].lower() in ['d', 'down', 'losers']:
        limit = 20
        if len(args) > 1 and args[1].isdigit():
            limit = min(int(args[1]), 50)
        return "losers", [], limit
    
    # Özel sembol listesi
    symbols = []
    for arg in args:
        if arg.strip():
            clean_arg = arg.upper().strip()
            if not clean_arg.endswith('USDT'):
                clean_arg += 'USDT'
            symbols.append(clean_arg)
    
    return "custom", symbols, 0

async def generate_price_report(mode: str = "default", 
                              custom_symbols: Optional[List[str]] = None,
                              limit: int = 20) -> str:
    """
    Fiyat raporu oluşturur.
    
    Args:
        mode: Çalışma modu (default, gainers, losers, custom)
        custom_symbols: Özel sembol listesi
        limit: Limit sayısı
    
    Returns:
        Formatlanmış rapor metni
    """
    try:
        binance = await get_binance()
        
        if mode == "default":
            # Config'teki semboller
            config = await get_config()
            tickers = await binance.get_custom_symbols_data(config.SCAN_SYMBOLS)
            tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            title = f"{EMOJI_CHART} SCAN_SYMBOLS (Hacme Göre)"
            
        elif mode == "gainers":
            # En çok yükselenler
            tickers = await binance.get_top_gainers_with_volume(
                limit=limit * 2,  # Daha fazla çekip filtrelemek için
                min_volume_usdt=1_000_000
            )
            title = f"{EMOJI_ROCKET} En Çok Yükselen {len(tickers)} Coin (Min. $1M Hacim)"
            
        elif mode == "losers":
            # En çok düşenler
            tickers = await binance.get_top_losers_with_volume(
                limit=limit * 2,
                min_volume_usdt=1_000_000
            )
            title = f"{EMOJI_CHART_DOWN} En Çok Düşen {len(tickers)} Coin (Min. $1M Hacim)"
            
        elif mode == "custom" and custom_symbols:
            # Özel sembol listesi
            tickers = await binance.get_custom_symbols_data(custom_symbols)
            tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            title = f"{EMOJI_COIN} Seçili Coinler"
            
        else:
            return f"{EMOJI_WARNING} Geçersiz mod!"
        
        if not tickers:
            return f"{EMOJI_WARNING} Eşleşen coin bulunamadı."
        
        # Raporu oluştur
        lines = []
        lines.append(title)
        lines.append(f"{EMOJI_FIRE}Coin | Değişim | Hacim | Fiyat")
        
        for i, ticker in enumerate(tickers[:limit], 1):
            symbol = ticker.get('symbol', 'N/A')
            change_percent = float(ticker.get('priceChangePercent', 0))
            volume = float(ticker.get('quoteVolume', 0))
            price = float(ticker.get('lastPrice', 0))
            
            # Sembolü kısalt
            display_symbol = symbol.replace('USDT', '')
            
            line = (f"{i}. {display_symbol}: "
                    f"{format_percentage(change_percent)} | "
                    f"{format_volume(volume)} | "
                    f"{format_price(price)}")
            lines.append(line)
        
        # İstatistikler
        total_volume = sum(float(t.get('quoteVolume', 0)) for t in tickers[:limit])
        avg_change = sum(float(t.get('priceChangePercent', 0)) for t in tickers[:limit]) / len(tickers[:limit])
        
        lines.append("")
        lines.append(f"📊 Toplam Hacim: {format_volume(total_volume)}")
        lines.append(f"📈 Ortalama Değişim: {format_percentage(avg_change)}")
        lines.append(f"{EMOJI_CLOCK} Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"❌ Rapor oluşturulamadı: {e}")
        return f"{EMOJI_WARNING} Veri işlenirken hata oluştu."

async def generate_compact_report(mode: str, tickers: List[Dict[str, Any]], limit: int = 10) -> str:
    """
    Kompakt rapor oluşturur (daha az detay).
    """
    if not tickers:
        return f"{EMOJI_WARNING} Veri bulunamadı."
    
    if mode == "gainers":
        title = f"{EMOJI_ROCKET} TOP {limit} YÜKSELEN"
    elif mode == "losers":
        title = f"{EMOJI_CHART_DOWN} TOP {limit} DÜŞEN"
    else:
        title = f"{EMOJI_CHART} COIN LİSTESİ"
    
    lines = [title]
    
    for i, ticker in enumerate(tickers[:limit], 1):
        symbol = ticker.get('symbol', 'N/A').replace('USDT', '')
        change = float(ticker.get('priceChangePercent', 0))
        price = float(ticker.get('lastPrice', 0))
        
        emoji = get_change_emoji(change)
        lines.append(f"{i}. {emoji} {symbol}: {change:+.1f}% - {format_price(price)}")
    
    lines.append(f"{EMOJI_CLOCK} {datetime.now().strftime('%H:%M')}")
    return "\n".join(lines)

@router.message(Command("p"))
async def p_command_handler(message: Message):
    """Ana /p komutu handler'ı."""
    try:
        # Argümanları parse et
        mode, symbols, limit = parse_command_args(message.text)
        
        # Retry mekanizmalı veri çekme
        tickers = await fetch_tickers_with_retry()
        
        if not tickers:
            error_msg = (
                f"{EMOJI_WARNING} Binance API'den veri alınamadı.\n"
                f"Lütfen birkaç dakika sonra tekrar deneyin."
            )
            await message.answer(error_msg)
            return
        
        # Rapor oluştur
        if mode == "default" and not symbols:
            config = await get_config()
            symbols = config.SCAN_SYMBOLS
        
        response = await generate_price_report(mode, symbols, limit or 20)
        
        # Mesajı gönder (Telegram mesaj sınırına dikkat)
        if len(response) > 4000:
            response = await generate_compact_report(mode, tickers, min(limit or 10, 15))
        
        await message.answer(code(response))
        
    except Exception as e:
        logger.error(f"❌ /p komutu işlenirken hata: {e}", exc_info=True)
        error_msg = (
            f"{EMOJI_WARNING} Bir hata oluştu.\n"
            f"Lütfen daha sonra tekrar deneyin.\n"
            f"Hata: {str(e)[:100]}..."
        )
        await message.answer(error_msg)

@router.message(Command("pg"))
async def pg_command_handler(message: Message):
    """/pg → Yükselen coinler (gainers)"""
    try:
        args = message.text.split()[1:]
        limit = min(int(args[0]), 30) if args and args[0].isdigit() else 15
        
        tickers = await fetch_tickers_with_retry()
        if not tickers:
            await message.answer(f"{EMOJI_WARNING} Binance API'den veri alınamadı.")
            return
        
        gainers = await (await get_binance()).get_top_gainers_with_volume(limit=limit*2, min_volume_usdt=500000)
        response = await generate_compact_report("gainers", gainers, limit)
        
        await message.answer(code(response))
        
    except Exception as e:
        logger.error(f"❌ /pg komutu işlenirken hata: {e}")
        await message.answer(f"{EMOJI_WARNING} Bir hata oluştu.")

@router.message(Command("pl"))
async def pl_command_handler(message: Message):
    """/pl → Düşen coinler (losers)"""
    try:
        args = message.text.split()[1:]
        limit = min(int(args[0]), 30) if args and args[0].isdigit() else 15
        
        tickers = await fetch_tickers_with_retry()
        if not tickers:
            await message.answer(f"{EMOJI_WARNING} Binance API'den veri alınamadı.")
            return
        
        losers = await (await get_binance()).get_top_losers_with_volume(limit=limit*2, min_volume_usdt=500000)
        response = await generate_compact_report("losers", losers, limit)
        
        await message.answer(code(response))
        
    except Exception as e:
        logger.error(f"❌ /pl komutu işlenirken hata: {e}")
        await message.answer(f"{EMOJI_WARNING} Bir hata oluştu.")

@router.message(Command("test_api"))
async def test_api_handler(message: Message):
    """API bağlantı testi."""
    try:
        binance = await get_binance()
        health = await binance.system_health_check()
        
        response = (
            f"{EMOJI_COIN} API Test Sonuçları:\n\n"
            f"✅ Ping: {'Başarılı' if health.get('ping') else 'Başarısız'}\n"
            f"🔑 API Keys: {'Geçerli' if health.get('api_keys_valid') else 'Geçersiz'}\n"
            f"🕒 Server Time: {health.get('server_time', 'N/A')}\n"
            f"⚡ Circuit Breaker: {health.get('circuit_breaker_state', 'N/A')}\n"
            f"📊 Cache Stats: {health.get('cache_stats', {}).get('size', 0)} items\n"
            f"📈 System Status: {health.get('system_status', 'unknown')}"
        )
        
        await message.answer(code(response))
        
    except Exception as e:
        logger.error(f"❌ API test hatası: {e}")
        await message.answer(f"{EMOJI_WARNING} API Test Hatası: {str(e)[:100]}")

@router.message(Command("p_help"))
async def p_help_handler(message: Message):
    """Yardım mesajı."""
    help_text = (
        f"{EMOJI_COIN} /p Komut Kullanımı:\n\n"
        f"/p - Varsayılan coin listesi\n"
        f"/p20 - İlk 20 yükselen coin\n"
        f"/p d - İlk 20 düşen coin\n"
        f"/p d 30 - İlk 30 düşen coin\n"
        f"/p btc eth - Özel coin listesi\n"
        f"/pg - Hızlı yükselenler\n"
        f"/pl - Hızlı düşenler\n"
        f"/test_api - API durum testi\n\n"
        f"{EMOJI_CLOCK} Veriler anlık olarak Binance API'den çekilir."
    )
    
    await message.answer(help_text)

# Hata durumu için fallback
@router.message(F.text.startswith('/p'))
async def p_fallback_handler(message: Message):
    """Bilinmeyen /p komutları için fallback."""
    await message.answer(
        f"{EMOJI_WARNING} Geçersiz komut. "
        f"Kullanım: /p_help"
    )

async def register_p_handler(main_router: Router):
    """Ana router'a bu router'ı ekler."""
    main_router.include_router(router)
    logger.info("✅ P handler registered successfully")