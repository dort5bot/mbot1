# analytics/causality.py

"""
Causality Analyzer - Lider-Takipçi Dinamiği Modülü

Bu modül, BTC Dominance, ETH/BTC korelasyonu ve 
Granger Causality (BTC->ALT) analizini yapar. 
Sonuçlar -1 (Altcoin Bear) ile +1 (Altcoin Bull) arasında normalize edilir.

Kullanım:
    from utils.analytics.causality import CausalityAnalyzer

    analyzer = CausalityAnalyzer()
    score = await analyzer.get_causality_score("ETHUSDT")

🔧 Özellikler:
- Singleton pattern
- Async/await uyumlu
- Aiogram 3.x Router pattern ile entegre edilebilir
- Type hints + docstring
- Logging
- PEP8 uyumlu
"""

import logging
from typing import Optional, Dict
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests

# Rate limiting - HTTP (Binance API tarafı ile entegre edilecek)
from utils.binance.binance_a import BinanceAPI

logger = logging.getLogger(__name__)


class CausalityAnalyzer:
    """BTC liderliği ve altcoin takibi için Granger causality tabanlı analiz."""

    _instance: Optional["CausalityAnalyzer"] = None

    def __new__(cls) -> "CausalityAnalyzer":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
            logger.info("✅ CausalityAnalyzer singleton instance created")
        return cls._instance

    def _initialize(self) -> None:
        """Instance initialize."""
        self.binance: Optional[BinanceAPI] = None

    def set_binance_api(self, binance: BinanceAPI) -> None:
        """
        Binance API instance set et.
        
        Args:
            binance: BinanceAPI instance
        """
        self.binance = binance

    async def _get_btc_dominance(self) -> float:
        """
        BTC dominansını hesapla.
        Basit yaklaşım: BTCUSDT market cap / toplam market cap (proxy).
        """
        try:
            btc_price = await self.binance.get_price("BTCUSDT")
            eth_price = await self.binance.get_price("ETHUSDT")

            # Proxy: Sadece BTC ve ETH kullanarak dominance (basitleştirilmiş)
            dominance = btc_price / (btc_price + eth_price)
            return float(dominance)
        except Exception as e:
            logger.error(f"❌ BTC dominance hesaplama hatası: {e}")
            return 0.0

    async def _get_eth_btc_corr(self, window: int = 100) -> float:
        """
        ETH/BTC korelasyonunu getir.
        
        Args:
            window: Korelasyon için kullanılacak kline sayısı
        """
        try:
            btc_klines = await self.binance.get_klines("BTCUSDT", interval="1h", limit=window)
            eth_klines = await self.binance.get_klines("ETHUSDT", interval="1h", limit=window)

            btc_closes = np.array([float(k[4]) for k in btc_klines])  # close fiyatı
            eth_closes = np.array([float(k[4]) for k in eth_klines])

            corr = np.corrcoef(btc_closes, eth_closes)[0, 1]
            return float(corr)
        except Exception as e:
            logger.error(f"❌ ETH/BTC korelasyon hesaplama hatası: {e}")
            return 0.0

    async def _get_granger_causality(self, symbol: str, maxlag: int = 2) -> float:
        """
        BTC -> Altcoin Granger Causality testi.
        
        Args:
            symbol: Altcoin sembolü (ör: "ETHUSDT")
            maxlag: Maksimum gecikme
        """
        try:
            btc_klines = await self.binance.get_klines("BTCUSDT", interval="1h", limit=200)
            alt_klines = await self.binance.get_klines(symbol, interval="1h", limit=200)

            btc_closes = np.array([float(k[4]) for k in btc_klines])
            alt_closes = np.array([float(k[4]) for k in alt_klines])

            data = np.column_stack([alt_closes, btc_closes])
            result = grangercausalitytests(data, maxlag=maxlag, verbose=False)

            # p-value ortalamasını al
            p_values = [result[i + 1][0]['ssr_ftest'][1] for i in range(maxlag)]
            score = 1 - np.mean(p_values)  # düşük p-value → yüksek etki
            return float(score)
        except Exception as e:
            logger.error(f"❌ Granger causality hesaplama hatası: {e}")
            return 0.0

    async def get_causality_score(self, symbol: str) -> Dict[str, float]:
        """
        Lider-takipçi dinamiği skorunu getir.
        
        Args:
            symbol: Altcoin sembolü (ör: "ETHUSDT")

        Returns:
            Dict[str, float]: {"dominance": x, "correlation": y, "granger": z, "score": final}
        """
        dominance = await self._get_btc_dominance()
        correlation = await self._get_eth_btc_corr()
        granger = await self._get_granger_causality(symbol)

        # Normalize scoring: -1 (Bear) ile +1 (Bull) arası
        final_score = np.tanh((dominance + correlation + granger) / 3)

        result = {
            "dominance": dominance,
            "correlation": correlation,
            "granger": granger,
            "score": final_score,
        }

        logger.info(f"📊 Causality Score for {symbol}: {result}")
        return result
