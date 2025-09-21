"""
analysis/analysis_a.py
Ana analiz aggregator modülü - Tüm analiz modüllerini koordine eder ve sinyal üretir
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache

from config import BotConfig, get_config
from utils.binance.binance_a import BinanceAPI

# Analiz modüllerini import et
from .causality import CausalityAnalyzer
from .derivs import compute_derivatives_sentiment
#from .onchain import OnchainAnalyzer
from analysis.onchain import get_onchain_analyzer

from .orderflow import OrderflowAnalyzer
from .regime import RegimeAnalyzer
from .risk import RiskManager
from .tremo import TremoAnalyzer

logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    symbol: str
    timestamp: float
    module_scores: Dict[str, float]
    alpha_signal_score: float
    position_risk_score: float
    gnosis_signal: float
    recommendation: str
    position_size: float

class AnalysisAggregator:
    """Ana analiz aggregator sınıfı"""
    
    _instance = None
    
    def __new__(cls, binance_api: BinanceAPI):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(binance_api)
        return cls._instance
    
    def _initialize(self, binance_api: BinanceAPI):
        self.binance = binance_api
        self.config = None
        self._cache = {}
        
        # Analiz modüllerini initialize et
        self.causality = CausalityAnalyzer()
        self.causality.set_binance_api(binance_api)
        
        #self.onchain = OnchainAnalyzer()
        self.onchain = get_onchain_analyzer(binance_api)    # Artık set_binance_api() çağrısı gerekmiyor
        self.orderflow = OrderflowAnalyzer(binance_api)
        
        #self.regime = RegimeAnalyzer(binance_api)
        self.regime = get_regime_analyzer(binance_api)
        self.risk = RiskManager(binance_api)
        self.tremo = TremoAnalyzer(binance_api)
    
    async def _get_config(self):
        if self.config is None:
            self.config = await get_config()
        return self.config
    
    @lru_cache(maxsize=100)
    async def _get_cached_analysis(self, symbol: str, cache_key: str):
        """1 dakikalık cache mekanizması"""
        current_time = time.time()
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if current_time - timestamp < 60:  # 1 dakika cache
                return cached_data
        return None
    
    async def run_analysis(self, symbol: str) -> AnalysisResult:
        """Tüm analiz modüllerini çalıştır ve sonuçları aggregate et"""
        config = await self._get_config()
        cache_key = f"analysis_{symbol}"
        
        # Cache kontrolü
        cached = await self._get_cached_analysis(symbol, cache_key)
        if cached:
            return cached
        
        module_scores = {}
        
        try:
            # Tüm modülleri paralel çalıştır
            tasks = [
                self._run_causality(symbol),
                self._run_derivs(symbol),
                self._run_onchain(),
                self._run_orderflow(symbol),
                self._run_regime(symbol),
                self._run_tremo(symbol)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Sonuçları işle
            module_names = ["causality", "derivs", "onchain", "orderflow", "regime", "tremo"]
            for i, (name, result) in enumerate(zip(module_names, results)):
                if isinstance(result, Exception):
                    logger.error(f"{name} modülü hatası: {result}")
                    module_scores[name] = 0.0
                else:
                    module_scores[name] = result if isinstance(result, (int, float)) else result.get("score", 0.0)
        
        except Exception as e:
            logger.error(f"Analiz sırasında hata: {e}")
            # Fallback: nötr skorlar
            module_scores = {name: 0.0 for name in module_names}
        
        # Alpha signal score hesapla (ağırlıklı ortalama)
        weights = config.MODULE_WEIGHTS
        alpha_signal_score = sum(
            module_scores.get(module, 0.0) * weights.get(module, 0.0)
            for module in weights
        )
        
        # Risk skoru hesapla
        risk_result = await self.risk.combined_risk_score(symbol)
        position_risk_score = risk_result.get("score", 0.6)  # Default 0.6
        
        # Gnosis signal hesapla
        gnosis_signal = alpha_signal_score * position_risk_score
        
        # Öneri ve pozisyon büyüklüğü
        recommendation, position_size = self._get_recommendation(gnosis_signal, config)
        
        result = AnalysisResult(
            symbol=symbol,
            timestamp=time.time(),
            module_scores=module_scores,
            alpha_signal_score=alpha_signal_score,
            position_risk_score=position_risk_score,
            gnosis_signal=gnosis_signal,
            recommendation=recommendation,
            position_size=position_size
        )
        
        # Cache'e kaydet
        self._cache[cache_key] = (result, time.time())
        
        logger.info(f"Analiz tamamlandı: {symbol} - Gnosis: {gnosis_signal:.3f}")
        return result
    
    def _get_recommendation(self, gnosis_signal: float, config) -> Tuple[str, float]:
        """Sinyal skoruna göre öneri ve pozisyon büyüklüğü belirle"""
        thresholds = config.SIGNAL_THRESHOLDS
        
        if gnosis_signal >= thresholds["strong_bull"]:
            return "FULL_BUY", 1.0  # %100 pozisyon
        elif gnosis_signal >= thresholds["bull"]:
            return "BUY", 0.6  # %60 pozisyon
        elif gnosis_signal <= thresholds["strong_bear"]:
            return "FULL_SELL", 1.0  # %100 short
        elif gnosis_signal <= thresholds["bear"]:
            return "SELL", 0.6  # %60 short
        else:
            return "NEUTRAL", 0.0  # Bekle
    
    async def _run_causality(self, symbol: str) -> float:
        """Causality analizini çalıştır"""
        try:
            result = await self.causality.get_causality_score(symbol)
            return result.get("score", 0.0)
        except Exception as e:
            logger.error(f"Causality analiz hatası: {e}")
            return 0.0
    
    async def _run_derivs(self, symbol: str) -> float:
        """Derivatives analizini çalıştır"""
        try:
            result = await compute_derivatives_sentiment(self.binance, symbol)
            return result.get("combined_score", 0.0)
        except Exception as e:
            logger.error(f"Derivs analiz hatası: {e}")
            return 0.0
    
    async def _run_onchain(self) -> float:
        """On-chain analizini çalıştır"""
        try:
            result = await self.onchain.aggregate_score()
            return result.get("aggregate", 0.0)
        except Exception as e:
            logger.error(f"On-chain analiz hatası: {e}")
            return 0.0
    
    async def _run_orderflow(self, symbol: str) -> float:
        """Orderflow analizini çalıştır"""
        try:
            result = await self.orderflow.compute_orderflow_score(symbol)
            return result.get("pressure_score", 0.0)
        except Exception as e:
            logger.error(f"Orderflow analiz hatası: {e}")
            return 0.0
    
    async def _run_regime(self, symbol: str) -> float:
        """Regime analizini çalıştır"""
        try:
            #result = await self.regime.analyze(symbol)
            #return result.get("Score", 0.0)
            result = await self.regime.analyze(symbol)
            return result.score
        except Exception as e:
            logger.error(f"Regime analiz hatası: {e}")
            return 0.0
    
    async def _run_tremo(self, symbol: str) -> float:
        """Tremo analizini çalıştır"""
        try:
            result = await self.tremo.analyze(symbol)
            return result.signal_score
        except Exception as e:
            logger.error(f"Tremo analiz hatası: {e}")
            return 0.0

# Singleton instance
def get_analysis_aggregator(binance_api: BinanceAPI) -> AnalysisAggregator:
    return AnalysisAggregator(binance_api)