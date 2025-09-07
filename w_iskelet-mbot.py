
✅ Telegram Bot Yapısı
Katmanlı Mimari: Her katmanın sorumluluğu net
Separation of Concerns: İş mantığı, veri erişimi ve presentation katmanları ayrılmış
Modülerlik: Her modül bağımsız çalışabilir
Scalability: Yeni özellikler kolayca eklenebilir

#
🟨GELİŞTİRME AŞAMASI🟨
* main.py
* utils/handler_loader.py
* handlers/dar_handler.py
* utils/binance
* →  handlers/→ binance ham veri sorgulama
* utils/analysis
* →  handlers/→ analysis ham veri analizi





proje(telegram botu)/
├── __init__.py
├── main.py
├── config.py
│
├── jobs/
│
├── handlers/
│   ├── __init__.py
│   ├── base_handler.py  # ⭐ YENİ: Temel handler sınıfı
│   ├── command_handlers/
│   │   ├── __init__.py
│   │   ├── start_handler.py
│   │   └── help_handler.py
│   ├── analysis_handlers/
│   │   ├── __init__.py
│ 	│   ├── ..
│   │   └── tremo_handler.py
│   │ 
│   ├── p_handler.py 
│   ├── dar_handler.py  #/dar + dosya bilgileri tek kod yapısında
│   └── error_handler.py # ⭐ YENİ: Hata yönetimi
│   
│   
├── services/# ⭐ Business logic katmanı
│   ├── __init__.py
│   ├── binance_service.py    # Binance operasyonlarını sarmalar
│   ├── analysis_service.py   # Analiz işlemlerini yönetir
│   ├── notification_service.py # Bildirim yönetimi
│   └── cache_service.py      # Önbellek yönetimi
│  
│   
├── models/          # ⭐ Veri modelleri
│   ├── __init__.py
│   ├── user.py           # Kullanıcı modeli
│   ├── analysis_result.py # Analiz sonuç modeli
│   ├── market_data.py    # Piyasa veri modeli
│   └── enums.py          # Enum'lar
│
│   
├── utils/
│ 	├── binance/						
│ 	│   ├── __init__.py						
│ 	│   ├── binance_a.py              # ⭐ Ana aggregator						
│ 	│   ├── binance_request.py        # HTTP request mekanizması						
│ 	│   ├── binance_public.py         # Public endpoints						
│ 	│   ├── binance_private.py        # Private endpoints (API key gerektiren)						
│ 	│   ├── binance_websocket.py      # WebSocket yönetimi						
│ 	│   ├── binance_circuit_breaker.py # Circuit breaker pattern						
│ 	│   ├── binance_utils.py          # Yardımcı fonksiyonlar						
│ 	│   ├── binance_constants.py      # Sabitler ve enum'lar						
│ 	│   ├── binance_metrics.py        # Metrik sınıfları						
│ 	│   └── binance_exceptions.py     # Özel exception'lar						
│ 	│   └── binance_types.py          # Type definitions						
│ 	│							
│ 	│ 		
│ 	├── analysis/						
│ 	│   │		
│ 	│   ├── analysis_a.py 	   # ⭐ → Ana aggregator			
│ 	│   ├── tremo.py           # A. Trend & Momentum					
│ 	│   ├── regime.py          # B. Rejim/Volatilite					
│ 	│   ├── derivs.py          # C. Derivatives	(türev ürünler)				
│ 	│   ├── orderflow.py       # D. Order Flow					
│ 	│   ├── causality.py       # E. Korelasyon & Lead-Lag					
│ 	│   ├── onchain.py         # F. On-Chain → ileri seviye (veri erişimi zor olabilir).					
│ 	│   ├── risk.py            # G. Risk Yönetimi (BETA - Koruma)					
│ 	│   └── score.py           # H. → Skor hesaplama & model birleşimi & 	alt analizlerin sonuçlarıyla  karma skor üretme, trade sinyali çıkarma
│ 	│		
│ 	│
│   └── handler_loader.py      # otomotik handler yükleyici
│ 
└── w_iskelet-mbot.py
  
🔄 Akış Şeması:
text
User → Telegram → Handler → Service → Utils → Binance API
                                      ↓
                                Analysis Modules
                                      ↓
User ← Telegram ← Handler ← Service ← Results
