
✅ Telegram Bot Yapısı
Katmanlı Mimari: Her katmanın sorumluluğu net
Separation of Concerns: İş mantığı, veri erişimi ve presentation katmanları ayrılmış
Modülerlik: Her modül bağımsız çalışabilir
Scalability: Yeni özellikler kolayca eklenebilir

bot/
├── __init__.py
├── main.py
├── config.py
├── handlers/
│   ├── __init__.py
│   ├── base_handler.py
│   ├── command_handlers/
│   │   ├── __init__.py
│   │   ├── start_handler.py
│   │   └── help_handler.py
│   ├── analysis_handlers/
│   │   ├── __init__.py
│   │   ├── dar_handler.py
│   │   ├── p_handler.py
│   │   └── tremo_handler.py
│   └── error_handler.py
├── jobs/
│   ├── __init__.py
│   ├── worker_a.py
│   └── worker_b.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── analysis_result.py
│   ├── market_data.py
│   └── enums.py
├── services/
│   ├── __init__.py
│   ├── binance_service.py
│   ├── analysis_service.py
│   ├── notification_service.py
│   └── cache_service.py
├── utils/
│   ├── binance/
│   │   ├── __init__.py
│   │   ├── binance_a.py
│   │   ├── binance_request.py
│   │   ├── binance_public.py
│   │   ├── binance_private.py
│   │   ├── binance_websocket.py
│   │   ├── binance_circuit_breaker.py
│   │   ├── binance_utils.py
│   │   ├── binance_constants.py
│   │   ├── binance_metrics.py
│   │   ├── binance_exceptions.py
│   │   └── binance_types.py
│   └── analysis/
│       ├── __init__.py
│       ├── tremo.py
│       ├── regime.py
│       ├── derivs.py
│       ├── orderflow.py
│       ├── causality.py
│       ├── onchain.py
│       ├── risk.py
│       └── score.py
└── logs/




  🔄 Akış Şeması:
text
User → Telegram → Handler → Service → Utils → Binance API
                                      ↓
                                Analysis Modules
                                      ↓
User ← Telegram ← Handler ← Service ← Results
