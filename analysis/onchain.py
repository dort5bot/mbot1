# analysis/onchain.py
"""
On-chain Analiz Modülü - Güncellenmiş Singleton Pattern

Bu modül, Stablecoin Supply Ratio, Exchange Net Flow ve ETF Flows gibi
ana on-chain metrikleri hesaplar. 
Çıktılar -1 (Bearish) ile +1 (Bullish) arasında normalize edilir.

Güncellemeler:
- Singleton pattern düzeltildi
- BinanceAPI parametre olarak alınıyor
- Daha iyi error handling
- Config entegrasyonu için hazır
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp
import numpy as np

from utils.binance.binance_a import BinanceAPI

logger = logging.getLogger(__name__)

class OnchainAnalyzer:
    """
    On-chain analizlerini yürüten Singleton sınıf.
    BinanceAPI instance'ını parametre olarak alır.
    """

    _instance: Optional["OnchainAnalyzer"] = None
    _initialized: bool = False

    def __new__(cls, binance_api: Optional[BinanceAPI] = None) -> "OnchainAnalyzer":
        """
        Singleton instance döndürür.
        
        Args:
            binance_api: BinanceAPI instance (opsiyonel, sonradan set edilebilir)
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(binance_api)
        return cls._instance

    def _initialize(self, binance_api: Optional[BinanceAPI] = None) -> None:
        """Instance'ı başlat"""
        if not self._initialized:
            self.binance = binance_api
            self.session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
            logger.info("OnchainAnalyzer initialized")

    def set_binance_api(self, binance_api: BinanceAPI) -> None:
        """
        Binance API instance set et.
        
        Args:
            binance_api: BinanceAPI instance
        """
        self.binance = binance_api
        logger.info("BinanceAPI set for OnchainAnalyzer")

    async def _ensure_session(self) -> None:
        """HTTP session'ı başlat"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            logger.debug("HTTP session created")

    async def _get_glassnode_data(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Glassnode API'den veri çek (placeholder - gerçek API key gerekli)
        
        Args:
            endpoint: API endpoint
            params: Query parametreleri
            
        Returns:
            API response veya None
        """
        try:
            await self._ensure_session()
            
            # Gerçek implementasyon için GLASSNODE_API_KEY environment variable'dan alınmalı
            glassnode_api_key = "your_glassnode_api_key_here"  # TODO: Config'ten al
            
            url = f"https://api.glassnode.com/v1/{endpoint}"
            params['api_key'] = glassnode_api_key
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Glassnode API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Glassnode fetch error: {e}")
            return None

    # ----------------------------
    # Stablecoin Supply Ratio (SSR)
    # ----------------------------
    async def stablecoin_supply_ratio(self) -> float:
        """
        Stablecoin Supply Ratio hesaplar.
        SSR = BTC Market Cap / Stablecoin Market Cap
        Daha yüksek SSR → daha az stablecoin likiditesi → Bearish.
        
        Returns:
            Normalize edilmiş skor (-1 ile +1 arası)
        """
        try:
            if not self.binance:
                logger.error("BinanceAPI not set for OnchainAnalyzer")
                return 0.0
            
            # Gerçek SSR verisi için Glassnode API
            ssr_data = await self._get_glassnode_data("metrics/indicators/ssr", {
                'a': 'BTC',
                'i': '24h',
                's': int(asyncio.get_event_loop().time()) - 86400,  # 24 saat önce
                'u': int(asyncio.get_event_loop().time())
            })
            
            if ssr_data and len(ssr_data) > 0:
                latest_ssr = ssr_data[-1]['v']
                # Tarihsel normallere göre normalize et
                # SSR > 20 → bearish, SSR < 5 → bullish
                if latest_ssr > 20:
                    return -1.0
                elif latest_ssr < 5:
                    return 1.0
                else:
                    return (10 - latest_ssr) / 5  # Linear normalization
            else:
                # Fallback: Basit yaklaşım
                btc_data = await self.binance.get_price("BTCUSDT")
                # USDT market cap proxy (basitleştirilmiş)
                usdt_market_cap = 80_000_000_000  # Yaklaşık USDT market cap
                btc_market_cap = btc_data * 19_500_000  # BTC circulating supply
                
                ssr = btc_market_cap / usdt_market_cap
                # Normalize: 5-20 aralığında
                normalized_ssr = max(-1.0, min(1.0, (10 - ssr) / 5))
                
                logger.debug(f"SSR hesaplandı: {ssr:.2f}, normalize: {normalized_ssr:.3f}")
                return normalized_ssr
                
        except Exception as e:
            logger.error(f"SSR hesaplanırken hata: {e}")
            return 0.0

    # ----------------------------
    # Exchange Net Flow
    # ----------------------------
    async def exchange_net_flow(self) -> float:
        """
        Borsalara giren/çıkan net BTC akışını hesaplar.
        Pozitif net flow → Bearish (satış baskısı).
        
        Returns:
            Normalize edilmiş skor (-1 ile +1 arası)
        """
        try:
            # Glassnode'dan net flow verisi
            netflow_data = await self._get_glassnode_data(
                "metrics/transactions/transfers_volume_exchanges_net", 
                {
                    'a': 'BTC',
                    'i': '24h',
                    's': int(asyncio.get_event_loop().time()) - 86400,
                    'u': int(asyncio.get_event_loop().time())
                }
            )
            
            if netflow_data and len(netflow_data) > 0:
                latest_netflow = netflow_data[-1]['v']
                # Büyük giriş → bearish, büyük çıkış → bullish
                if latest_netflow > 1000:  # +1000 BTC giriş
                    return -1.0
                elif latest_netflow < -1000:  # -1000 BTC çıkış
                    return 1.0
                else:
                    return -latest_netflow / 1000  # Linear normalization
            else:
                # Fallback: Basit yaklaşım
                # Burada daha sofistike bir fallback mekanizması eklenebilir
                return 0.0
                
        except Exception as e:
            logger.error(f"Net Flow hesaplanırken hata: {e}")
            return 0.0

    # ----------------------------
    # ETF Flows
    # ----------------------------
    async def etf_flows(self) -> float:
        """
        ETF giriş/çıkışlarını analiz eder.
        Net giriş → Bullish (+1), Net çıkış → Bearish (-1).
        
        Returns:
            Normalize edilmiş skor (-1 ile +1 arası)
        """
        try:
            # Gerçek ETF flow verisi için premium data source gerekli
            # Burada placeholder implementasyon
            
            # Örnek: Son 24 saat için tahmini ETF flow
            # Gerçek implementasyonda Glassnode veya alternatif API kullanılmalı
            etf_flow_data = await self._get_glassnode_data(
                "metrics/indicators/etf_flows", 
                {
                    'a': 'BTC',
                    'i': '24h'
                }
            )
            
            if etf_flow_data and len(etf_flow_data) > 0:
                latest_flow = etf_flow_data[-1]['v']
                # Normalize: ±50M USD aralığında
                return max(-1.0, min(1.0, latest_flow / 50_000_000))
            else:
                # Fallback: Rastgele değil, nötr döndür
                return 0.0
                
        except Exception as e:
            logger.error(f"ETF flow hesaplanırken hata: {e}")
            return 0.0

    # ----------------------------
    # Fear & Greed Index
    # ----------------------------
    async def fear_greed_index(self) -> float:
        """
        Fear & Greed Index'i getir.
        
        Returns:
            Normalize edilmiş skor (-1 ile +1 arası)
        """
        try:
            await self._ensure_session()
            
            url = "https://api.alternative.me/fng/"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    score = int(data['data'][0]['value'])
                    # 0-100 → -1 to +1 arasına normalize et
                    return (score - 50) / 50
                else:
                    logger.warning("Fear & Greed API error")
                    return 0.0
                    
        except Exception as e:
            logger.error(f"Fear & Greed index error: {e}")
            return 0.0

    # ----------------------------
    # Genel analiz skoru
    # ----------------------------
    async def aggregate_score(self) -> Dict[str, Any]:
        """
        Tüm metrikleri çalıştırır ve birleşik skor üretir.
        
        Returns:
            Tüm metrik skorları ve aggregate skor
        """
        try:
            # Tüm metrikleri paralel çalıştır
            tasks = [
                self.stablecoin_supply_ratio(),
                self.exchange_net_flow(),
                self.etf_flows(),
                self.fear_greed_index()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Exception handling
            ssr = results[0] if not isinstance(results[0], Exception) else 0.0
            net_flow = results[1] if not isinstance(results[1], Exception) else 0.0
            etf = results[2] if not isinstance(results[2], Exception) else 0.0
            fear_greed = results[3] if not isinstance(results[3], Exception) else 0.0

            # Ağırlıklı ortalama (config'ten alınabilir)
            total_score = (ssr * 0.3 + net_flow * 0.3 + etf * 0.2 + fear_greed * 0.2)
            total_score = round(total_score, 3)

            result = {
                "stablecoin_supply_ratio": ssr,
                "exchange_net_flow": net_flow,
                "etf_flows": etf,
                "fear_greed_index": fear_greed,
                "aggregate": total_score,
            }
            
            logger.info(f"On-chain analiz sonucu: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Aggregate score hesaplanırken hata: {e}")
            # Fallback result
            return {
                "stablecoin_supply_ratio": 0.0,
                "exchange_net_flow": 0.0,
                "etf_flows": 0.0,
                "fear_greed_index": 0.0,
                "aggregate": 0.0,
            }

    async def close(self) -> None:
        """Kaynakları temizle"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("OnchainAnalyzer resources cleaned up")

    def __del__(self) -> None:
        """Destructor - cleanup"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
            else:
                loop.run_until_complete(self.close())
        except Exception:
            pass

# Aiogram 3.x Router entegrasyonu
from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text.lower() == "onchain")
async def onchain_handler(message: Message) -> None:
    """
    Telegram bot için On-chain analiz handler.
    """
    try:
        # BinanceAPI instance'ını bot context'inden al
        binance_api = getattr(message.bot, 'binance_api', None)
        if not binance_api:
            await message.answer("Binance API bağlantısı kurulamadı")
            return
        
        analyzer = OnchainAnalyzer(binance_api)
        result = await analyzer.aggregate_score()

        text = (
            "🔗 On-Chain Analiz:\n"
            f"- Stablecoin Supply Ratio: {result['stablecoin_supply_ratio']:.3f}\n"
            f"- Exchange Net Flow: {result['exchange_net_flow']:.3f}\n"
            f"- ETF Flows: {result['etf_flows']:.3f}\n"
            f"- Fear & Greed: {result['fear_greed_index']:.3f}\n"
            f"📊 Genel Skor: {result['aggregate']:.3f}"
        )

        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Onchain handler error: {e}")
        await message.answer("On-chain analiz sırasında hata oluştu")

# Singleton instance getter
def get_onchain_analyzer(binance_api: Optional[BinanceAPI] = None) -> OnchainAnalyzer:
    """
    OnchainAnalyzer singleton instance'ını döndürür.
    
    Args:
        binance_api: BinanceAPI instance (opsiyonel)
        
    Returns:
        OnchainAnalyzer instance
    """
    return OnchainAnalyzer(binance_api)

# Test için
async def test_onchain_analyzer():
    """Test function"""
    from utils.binance.binance_request import BinanceHTTPClient
    from utils.binance.binance_circuit_breaker import CircuitBreaker
    
    # Mock veya gerçek BinanceAPI
    http_client = BinanceHTTPClient(api_key="test", secret_key="test")
    cb = CircuitBreaker()
    binance_api = BinanceAPI(http_client, cb)
    
    analyzer = get_onchain_analyzer(binance_api)
    result = await analyzer.aggregate_score()
    print("On-chain analysis result:", result)
    
    await analyzer.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_onchain_analyzer())