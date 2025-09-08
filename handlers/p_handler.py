"""
p_handler.py - Price Scanner Handler for Binance Data
-----------------------------------------------------
Handles /p commands to display cryptocurrency price data from Binance.
Binance API'sinden 24 saatlik ticker verilerini çeker
- Async/await compatible
- Aiogram 3.x Router pattern
- Type hints + PEP8 compliant
- Singleton BinanceAPI integration
- Error handling + logging
- Supports multiple command variations
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from utils.binance.binance_a import BinanceAPI
from utils.binance.binance_request import BinanceHTTPClient
from utils.binance.binance_circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Router instance
router = Router(name="price_scanner")

# Global BinanceAPI instance
_binance_api: Optional[BinanceAPI] = None

async def get_binance_api() -> BinanceAPI:
    """
    Get or create BinanceAPI singleton instance.
    
    Returns:
        BinanceAPI instance
    """
    global _binance_api
    if _binance_api is None:
        # Initialize HTTP client and circuit breaker
        http_client = BinanceHTTPClient(
            api_key="",  # Public endpoints don't require API key
            secret_key=""
        )
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            half_open_max_requests=2
        )
        _binance_api = BinanceAPI(http_client, circuit_breaker)
        logger.info("✅ BinanceAPI initialized for price scanner")
    return _binance_api

async def fetch_all_tickers() -> List[Dict[str, Any]]:
    """
    Fetch all ticker data from Binance.
    
    Returns:
        List of ticker data
    """
    try:
        binance = await get_binance_api()
        tickers = await binance.public.get_all_24h_tickers()
        return tickers if isinstance(tickers, list) else []
    except Exception as e:
        logger.error(f"❌ Failed to fetch tickers: {e}")
        return []

async def filter_symbols(symbols: List[str], tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter tickers based on requested symbols.
    
    Args:
        symbols: List of symbol patterns to filter
        tickers: All available tickers
        
    Returns:
        Filtered ticker data
    """
    if not symbols:
        return tickers
    
    filtered = []
    symbol_patterns = [s.upper() for s in symbols]
    
    for ticker in tickers:
        symbol = ticker.get('symbol', '')
        for pattern in symbol_patterns:
            # Match exact symbol or symbol ending with pattern (e.g., BTC matches BTCUSDT)
            if symbol == pattern or symbol.endswith(pattern):
                filtered.append(ticker)
                break
    
    return filtered

async def format_ticker_data(ticker: Dict[str, Any]) -> str:
    """
    Format individual ticker data for display.
    
    Args:
        ticker: Ticker data dictionary
        
    Returns:
        Formatted string
    """
    symbol = ticker.get('symbol', 'N/A')
    price_change_percent = float(ticker.get('priceChangePercent', 0))
    volume = float(ticker.get('volume', 0))
    last_price = float(ticker.get('lastPrice', 0))
    
    # Format volume (convert to millions/billions)
    if volume >= 1_000_000_000:
        volume_str = f"${volume/1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        volume_str = f"${volume/1_000_000:.1f}M"
    else:
        volume_str = f"${volume:,.0f}"
    
    # Format price change with color indicator
    change_emoji = "🟢" if price_change_percent >= 0 else "🔴"
    change_str = f"{price_change_percent:+.2f}%"
    
    # Format price (appropriate decimal places)
    if last_price >= 1000:
        price_str = f"{last_price:,.1f}"
    elif last_price >= 1:
        price_str = f"{last_price:,.2f}"
    else:
        price_str = f"{last_price:.6f}".rstrip('0').rstrip('.')
    
    return f"{change_emoji} {symbol}: {change_str} | {volume_str} | {price_str}"

async def generate_price_message(tickers: List[Dict[str, Any]], title: str, limit: int = 20) -> str:
    """
    Generate formatted price message.
    
    Args:
        tickers: List of ticker data
        title: Message title
        limit: Maximum number of coins to display
        
    Returns:
        Formatted message string
    """
    if not tickers:
        return "❌ Veri alınamadı. Lütfen daha sonra tekrar deneyin."
    
    # Sort by volume (descending)
    tickers.sort(key=lambda x: float(x.get('volume', 0)), reverse=True)
    
    # Apply limit
    display_tickers = tickers[:limit]
    
    lines = [f"📈 {title}", "⚡Coin | Değişim | Hacim | Fiyat", ""]
    
    for i, ticker in enumerate(display_tickers, 1):
        formatted = await format_ticker_data(ticker)
        lines.append(f"{i}. {formatted}")
    
    return "\n".join(lines)

@router.message(Command("p"))
async def handle_price_command(message: Message) -> None:
    """
    Handle /p command - show default symbol prices.
    
    Args:
        message: Telegram message object
    """
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Get all tickers
        all_tickers = await fetch_all_tickers()
        if not all_tickers:
            await message.reply("❌ Binance verileri alınamadı.")
            return
        
        # Get default symbols from config (simplified for example)
        # In real implementation, you might have a config module
        default_symbols = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX", "MATIC"]
        
        # Filter tickers for default symbols
        filtered_tickers = await filter_symbols(default_symbols, all_tickers)
        
        # Generate and send message
        response = await generate_price_message(
            filtered_tickers, 
            "SCAN_SYMBOLS (Hacme Göre)",
            limit=len(default_symbols)
        )
        
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"❌ Error in /p command: {e}")
        await message.reply("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@router.message(Command("p"), F.text.regexp(r'^/p(\d+)$'))
async def handle_price_top_n(message: Message, regexp: re.Match) -> None:
    """
    Handle /pN command - show top N coins by volume.
    
    Args:
        message: Telegram message object
        regexp: Regex match object containing the number
    """
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Extract number from command
        n = int(regexp.group(1))
        if n <= 0:
            await message.reply("❌ Geçersiz sayı. Pozitif bir sayı girin.")
            return
        
        # Limit to reasonable number to avoid message too long
        n = min(n, 50)
        
        # Get all tickers
        all_tickers = await fetch_all_tickers()
        if not all_tickers:
            await message.reply("❌ Binance verileri alınamadı.")
            return
        
        # Generate and send message
        response = await generate_price_message(
            all_tickers, 
            f"En Çok Yükselen {n} Coin",
            limit=n
        )
        
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"❌ Error in /pN command: {e}")
        await message.reply("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@router.message(Command("pd"))
async def handle_price_decliners(message: Message) -> None:
    """
    Handle /pd command - show declining coins.
    
    Args:
        message: Telegram message object
    """
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Get all tickers
        all_tickers = await fetch_all_tickers()
        if not all_tickers:
            await message.reply("❌ Binance verileri alınamadı.")
            return
        
        # Filter for declining coins (negative price change)
        declining_tickers = [
            ticker for ticker in all_tickers 
            if float(ticker.get('priceChangePercent', 0)) < 0
        ]
        
        # Sort by worst performers first
        declining_tickers.sort(key=lambda x: float(x.get('priceChangePercent', 0)))
        
        # Generate and send message
        response = await generate_price_message(
            declining_tickers, 
            "Düşüş Trendindeki Coinler",
            limit=20
        )
        
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"❌ Error in /pd command: {e}")
        await message.reply("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@router.message(Command("pd"), F.text.regexp(r'^/pd\s+(\d+)$'))
async def handle_price_decliners_n(message: Message, regexp: re.Match) -> None:
    """
    Handle /pd N command - show top N declining coins.
    
    Args:
        message: Telegram message object
        regexp: Regex match object containing the number
    """
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Extract number from command
        n = int(regexp.group(1))
        if n <= 0:
            await message.reply("❌ Geçersiz sayı. Pozitif bir sayı girin.")
            return
        
        # Limit to reasonable number
        n = min(n, 50)
        
        # Get all tickers
        all_tickers = await fetch_all_tickers()
        if not all_tickers:
            await message.reply("❌ Binance verileri alınamadı.")
            return
        
        # Filter for declining coins
        declining_tickers = [
            ticker for ticker in all_tickers 
            if float(ticker.get('priceChangePercent', 0)) < 0
        ]
        
        # Sort by worst performers first
        declining_tickers.sort(key=lambda x: float(x.get('priceChangePercent', 0)))
        
        # Generate and send message
        response = await generate_price_message(
            declining_tickers, 
            f"Düşüş Trendindeki {n} Coin",
            limit=n
        )
        
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"❌ Error in /pd N command: {e}")
        await message.reply("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@router.message(Command("p"), F.text.regexp(r'^/p\s+([a-zA-Z0-9\s]+)$'))
async def handle_price_custom(message: Message, regexp: re.Match) -> None:
    """
    Handle /p coin1 coin2... command - show custom selected coins.
    
    Args:
        message: Telegram message object
        regexp: Regex match object containing the symbols
    """
    try:
        # Show typing action
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Extract symbols from command
        symbols_text = regexp.group(1).strip()
        symbols = symbols_text.split()
        
        if not symbols:
            await message.reply("❌ Geçersiz sembol listesi.")
            return
        
        # Get all tickers
        all_tickers = await fetch_all_tickers()
        if not all_tickers:
            await message.reply("❌ Binance verileri alınamadı.")
            return
        
        # Filter for requested symbols
        filtered_tickers = await filter_symbols(symbols, all_tickers)
        
        if not filtered_tickers:
            await message.reply("❌ İstenen semboller bulunamadı.")
            return
        
        # Generate and send message
        response = await generate_price_message(
            filtered_tickers, 
            "Seçili Coinler",
            limit=len(symbols)
        )
        
        await message.reply(response)
        
    except Exception as e:
        logger.error(f"❌ Error in /p custom command: {e}")
        await message.reply("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

async def register_handlers(dispatcher: Dispatcher) -> None:
    """
    Register handlers with dispatcher.
    
    Args:
        dispatcher: Aiogram dispatcher instance
    """
    dispatcher.include_router(router)
    logger.info("✅ Price scanner handlers registered")

# For handler_loader compatibility
async def register_handlers(dispatcher: Dispatcher) -> None:
    """Register handlers with dispatcher (for handler_loader)."""
    dispatcher.include_router(router)
    logger.info("✅ Price scanner handlers registered")

# Router instance for direct import
router = router
