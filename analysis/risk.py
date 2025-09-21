# analysis/risk.py
"""
analysis/risk.py
Glassnode API Key alın ve environment variable olarak ayarlayın
Risk parametrelerini bot stratejinize göre tuning edin
Cache timeout değerlerini ihtiyaca göre ayarlayın
Makro ağırlığını (macro_weight) backtest ile optimize edin
sağlam risk yönetimini koruyor
"""

from __future__ import annotations

import asyncio
import logging
from math import erf, sqrt
from statistics import mean, pstdev
from typing import Dict, List, Optional, Sequence, Tuple, Union
from dataclasses import dataclass
import aiohttp
import pandas as pd

from .binance_a import BinanceAPI

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Glassnode API entegrasyonu için config (environment variables'dan alınmalı)
GLASSNODE_API_KEY = "your_glassnode_api_key_here"  # TODO: Environment variable'dan al

@dataclass
class MacroMarketSignal:
    """Makro piyasa sinyallerini tutan veri sınıfı"""
    ssr_score: float = 0.0  # -1 (bearish) to +1 (bullish)
    netflow_score: float = 0.0
    etf_flow_score: float = 0.0
    fear_greed_score: float = 0.0  # Yeni eklenen metrik
    overall_score: float = 0.0
    confidence: float = 0.0  # Sinyal güvenilirliği 0-1 arası

class RiskManager:
    """
    Geliştirilmiş Risk Manager with macro market analysis integration.
    
    Yeni Özellikler:
    - Glassnode API entegrasyonu (SSR, Netflow için gerçek veri)
    - Fear & Greed Index entegrasyonu
    - Makro sinyallerin risk skoruna ağırlıklı entegrasyonu
    - Daha detaylı logging ve monitoring
    - Configurable parameters via dataclass
    """

    _instance: Optional["RiskManager"] = None

    def __new__(cls, binance: BinanceAPI) -> "RiskManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(binance)
            logger.info("Geliştirilmiş RiskManager singleton created")
        return cls._instance

    def _initialize(self, binance: BinanceAPI) -> None:
        self.binance = binance
        self.session = aiohttp.ClientSession()  # Glassnode API calls için
        
        # Default params - yapılandırılabilir hale getirilebilir
        self.atr_period = 14
        self.k_atr_stop = 3.0
        self.var_confidence = 0.95
        self.macro_weight = 0.15  # Makro sinyallerin risk skorundaki ağırlığı
        
        # Cache mekanizmaları
        self._klines_cache: Dict[Tuple[str, str, int, bool], List[dict]] = {}
        self._macro_cache: Dict[str, MacroMarketSignal] = {}
        self._macro_cache_timeout = 3600  # 1 saat cache
        
        logger.debug("Geliştirilmiş RiskManager initialized")

    # -------------------------
    # GLASSNODE ENTEGRASYONU - KOD1 fikirlerinin gerçek implementasyonu
    # -------------------------
    async def _fetch_glassnode_data(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Glassnode API'den veri çekme"""
        try:
            url = f"https://api.glassnode.com/v1/{endpoint}"
            params['api_key'] = GLASSNODE_API_KEY
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.warning(f"Glassnode API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Glassnode fetch error: {e}")
            return None

    async def get_ssr_metric(self) -> float:
        """Gerçek SSR metriği - Glassnode implementasyonu"""
        try:
            data = await self._fetch_glassnode_data("metrics/indicators/ssr", {
                'a': 'BTC',
                'i': '24h'
            })
            
            if data and len(data) > 0:
                latest_ssr = data[-1]['v']
                # Normalize: Tarihsel verilere göre ayarlanabilir
                if latest_ssr > 20: return -1.0
                elif latest_ssr < 5: return 1.0
                return (10 - latest_ssr) / 5
            return 0.0
        except Exception as e:
            logger.error(f"SSR metric error: {e}")
            return 0.0

    async def get_netflow_metric(self) -> float:
        """Gerçek Netflow metriği - Glassnode implementasyonu"""
        try:
            data = await self._fetch_glassnode_data("metrics/transactions/transfers_volume_exchanges_net", {
                'a': 'BTC',
                'i': '24h'
            })
            
            if data and len(data) > 0:
                latest_netflow = data[-1]['v']
                # Normalize: Tarihsel standart sapmaya göre ayarlanabilir
                if latest_netflow > 1000: return -1.0  # Büyük giriş → bearish
                elif latest_netflow < -1000: return 1.0  # Büyük çıkış → bullish
                return -latest_netflow / 1000  # Linear normalization
            return 0.0
        except Exception as e:
            logger.error(f"Netflow metric error: {e}")
            return 0.0

    async def get_fear_greed_index(self) -> float:
        """Fear & Greed Index - Alternative.me API'si"""
        try:
            url = "https://api.alternative.me/fng/"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    score = int(data['data'][0]['value'])
                    # 0-100 → -1 to +1 arasına normalize et
                    return (score - 50) / 50
            return 0.0
        except Exception as e:
            logger.error(f"Fear & Greed index error: {e}")
            return 0.0

    async def get_macro_market_signal(self) -> MacroMarketSignal:
        """Tüm makro metrikleri toplu olarak hesaplar"""
        # Cache kontrolü
        cache_key = "macro_signal"
        if cache_key in self._macro_cache:
            return self._macro_cache[cache_key]
        
        # Paralel olarak tüm metrikleri hesapla
        ssr, netflow, fear_greed = await asyncio.gather(
            self.get_ssr_metric(),
            self.get_netflow_metric(),
            self.get_fear_greed_index(),
            return_exceptions=True
        )
        
        # Exception handling
        ssr = ssr if not isinstance(ssr, Exception) else 0.0
        netflow = netflow if not isinstance(netflow, Exception) else 0.0
        fear_greed = fear_greed if not isinstance(fear_greed, Exception) else 0.0
        
        # ETF flow placeholder (KOD1'den) - gerçek API bulunana kadar
        etf_flow = 0.0  # Gerçek implementasyon için premium veri kaynağı gerekli
        
        overall_score = (ssr + netflow + fear_greed + etf_flow) / 4
        
        signal = MacroMarketSignal(
            ssr_score=ssr,
            netflow_score=netflow,
            etf_flow_score=etf_flow,
            fear_greed_score=fear_greed,
            overall_score=overall_score,
            confidence=0.7  # Basit confidence metric
        )
        
        self._macro_cache[cache_key] = signal
        # Cache'i temizleme için background task eklenebilir
        return signal

    # -------------------------
    # MEVCUT RISK METRIKLERI (KOD2'den geliştirilerek)
    # -------------------------
    # Orijinal KOD2 metotları burada kalacak, sadece combined_risk_score geliştirilecek
    # [compute_atr, suggest_stop_loss, liquidation_proximity, correlation_risk, portfolio_var metotları aynen kalacak]

    async def combined_risk_score(
        self,
        symbol: str,
        *,
        account_positions: Optional[List[dict]] = None,
        portfolio_symbols: Optional[Sequence[str]] = None,
        interval: str = "1h",
        lookback: int = 250,
        futures: bool = False,
        include_macro: bool = True  # Yeni parametre: makro sinyalleri dahil et
    ) -> Dict[str, float]:
        """
        Geliştirilmiş risk skoru - makro piyasa sinyallerini entegre eder.
        """
        try:
            # Mevcut mikro metrikleri hesapla
            price = await self.binance.get_price(symbol, futures=futures)
            atr = await self.compute_atr(symbol, interval=interval, futures=futures)
            vol_metric = min(1.0, (price / atr) / 100.0) if atr > 0 else 0.0
            
            pos = None
            if account_positions:
                for p in account_positions:
                    if p.get("symbol", "").upper() == symbol.upper():
                        pos = p
                        break
            liq_prox = await self.liquidation_proximity(symbol, pos) if pos else 1.0
            corr_penalty = 0.0
            if portfolio_symbols:
                corr_penalty = await self.correlation_risk(symbol, portfolio_symbols, interval=interval, futures=futures)
            var = await self.portfolio_var(list(portfolio_symbols or [symbol]), lookback=lookback, interval=interval, futures=futures)

            # Makro sinyalleri al (isteğe bağlı)
            macro_signal = await self.get_macro_market_signal() if include_macro else None
            
            # Ağırlıkları ayarla
            w_vol = 0.30  # Önceki 0.35
            w_liq = 0.20  # Önceki 0.25  
            w_corr = 0.20  # Aynı
            w_var = 0.20  # Aynı
            w_macro = self.macro_weight if include_macro and macro_signal else 0.0
            
            # Mikro metrikleri normalize et
            vol_norm = vol_metric
            liq_norm = liq_prox
            corr_norm = 1.0 - corr_penalty
            var_norm = 1.0 - var
            macro_norm = macro_signal.overall_score if macro_signal else 0.0

            # Ağırlıkları normalize et (toplam 1 olacak şekilde)
            total_weight = w_vol + w_liq + w_corr + w_var + w_macro
            w_vol /= total_weight
            w_liq /= total_weight
            w_corr /= total_weight
            w_var /= total_weight
            w_macro /= total_weight

            # Nihai skoru hesapla
            score = (
                w_vol * vol_norm + 
                w_liq * liq_norm + 
                w_corr * corr_norm + 
                w_var * var_norm +
                w_macro * macro_norm
            )
            score = max(0.0, min(1.0, score))
            
            logger.info(f"Geliştirilmiş risk skoru için {symbol} = {score:.3f} (macro: {macro_norm:.3f})")
            
            return {
                "symbol": symbol.upper(),
                "price": float(price),
                "atr": float(atr),
                "vol_metric": float(vol_norm),
                "liquidation_proximity": float(liq_norm),
                "correlation_penalty": float(corr_penalty),
                "portfolio_var": float(var),
                "macro_score": float(macro_norm) if macro_signal else 0.0,
                "macro_confidence": float(macro_signal.confidence) if macro_signal else 0.0,
                "score": float(score),
                "score_without_macro": float(score - w_macro * macro_norm) if macro_signal else float(score),
            }
            
        except Exception as exc:
            logger.exception(f"Geliştirilmiş risk skoru hesaplama hatası {symbol}: {exc}")
            return {
                "symbol": symbol.upper(),
                "price": 0.0,
                "atr": 0.0,
                "vol_metric": 0.0,
                "liquidation_proximity": 0.0,
                "correlation_penalty": 1.0,
                "portfolio_var": 1.0,
                "macro_score": 0.0,
                "macro_confidence": 0.0,
                "score": 0.0,
                "score_without_macro": 0.0,
            }

    # -------------------------
    # YENI OZELLIKLER
    # -------------------------
    async def get_market_regime(self) -> str:
        """
        Piyasa rejimini belirler: BULL, BEAR, veya NEUTRAL
        """
        try:
            macro_signal = await self.get_macro_market_signal()
            if macro_signal.overall_score > 0.3:
                return "BULL"
            elif macro_signal.overall_score < -0.3:
                return "BEAR"
            else:
                return "NEUTRAL"
        except Exception as e:
            logger.error(f"Market regime analysis error: {e}")
            return "NEUTRAL"

    async def adaptive_position_sizing(
        self,
        symbol: str,
        base_fraction: float,
        *,
        risk_budget: float = 0.01,
        account_balance: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Piyasa rejimine göre adaptif pozisyon büyüklüğü önerir.
        """
        market_regime = await self.get_market_regime()
        
        # Piyasa rejimine göre adjustment
        regime_multiplier = {
            "BULL": 1.2,    # Bull piyasada daha agresif
            "NEUTRAL": 1.0, # Normal risk
            "BEAR": 0.6     # Bear piyasada daha korunmacı
        }.get(market_regime, 1.0)
        
        adjusted_fraction = base_fraction * regime_multiplier
        adjusted_fraction = max(0.0, min(1.0, adjusted_fraction))
        
        result = {
            "base_fraction": base_fraction,
            "market_regime": market_regime,
            "regime_multiplier": regime_multiplier,
            "adjusted_fraction": adjusted_fraction,
            "recommendation": "AGGRESSIVE" if regime_multiplier > 1.0 else "CONSERVATIVE" if regime_multiplier < 1.0 else "NEUTRAL"
        }
        
        # Max notional hesaplaması (mevcut logic)
        if account_balance:
            price = await self.binance.get_price(symbol)
            atr = await self.compute_atr(symbol)
            stop_distance = self.k_atr_stop * atr if atr > 0 else price * 0.01
            if stop_distance > 0:
                max_risk_value = account_balance * risk_budget
                position_notional = max_risk_value * price / stop_distance
                result["max_notional"] = position_notional * adjusted_fraction
        
        return result

    # -------------------------
    # CLEANUP
    # -------------------------
    async def close(self):
        """Resource cleanup"""
        await self.session.close()
        logger.info("RiskManager resources cleaned up")

# Usage example ve aiogram entegrasyonu
try:
    from aiogram import Router
    from aiogram.types import Message

    router = Router()

    @router.message(commands=["advanced_risk"])
    async def cmd_advanced_risk(message: Message) -> None:
        """Geliştirilmiş risk analiz komutu"""
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.answer("Usage: /advanced_risk SYMBOL (e.g. /advanced_risk BTCUSDT)")
            return

        symbol = parts[1].upper()
        try:
            BINANCE = getattr(message.bot, "binance_api", None)
            if BINANCE is None:
                await message.answer("Binance API not configured.")
                return
                
            rm = RiskManager(BINANCE)
            summary = await rm.combined_risk_score(
                symbol, 
                portfolio_symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
                include_macro=True
            )
            
            # Makro analiz sonuçlarını da getir
            macro = await rm.get_macro_market_signal()
            regime = await rm.get_market_regime()
            
            text = (
                f"🎯 **Gelişmiş Risk Analizi - {summary['symbol']}**\n\n"
                f"📊 **Temel Metrikler:**\n"
                f"• Price: ${summary['price']:,.2f}\n"
                f"• ATR: {summary['atr']:.4f}\n"
                f"• Volatility Score: {summary['vol_metric']:.3f}\n"
                f"• Liquidation Safety: {summary['liquidation_proximity']:.3f}\n"
                f"• Correlation Penalty: {summary['correlation_penalty']:.3f}\n"
                f"• Portfolio VaR: {summary['portfolio_var']:.3f}\n\n"
                f"🌍 **Makro Piyasa:**\n"
                f"• SSR Score: {macro.ssr_score:.3f}\n"
                f"• Netflow Score: {macro.netflow_score:.3f}\n"
                f"• Fear & Greed: {macro.fear_greed_score:.3f}\n"
                f"• Overall Macro: {macro.overall_score:.3f}\n"
                f"• Market Regime: {regime}\n\n"
                f"📈 **Risk Skorları:**\n"
                f"• Micro-Only Score: {summary['score_without_macro']:.3f}\n"
                f"• Final Score: {summary['score']:.3f}\n"
                f"• Confidence: {summary['macro_confidence']:.3f}"
            )
            
            await message.answer(text)
            
        except Exception as exc:
            logger.exception("Advanced risk command error: %s", exc)
            await message.answer("Risk analiz hatası. Loglara bakın.")

except ImportError:
    router = None