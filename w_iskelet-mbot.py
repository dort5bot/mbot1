
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
mbot1/
├── .github/                  # GHCR yapı dosyası
│   └── workflows/
│       └── docker-deploy.yml
├── Dockerfile               # GHCR yapı dosyası
├── .dockerignore            # GHCR yapı dosyası
│
│
🟥🟥🟥 GHCR ayarları SAYFA ALTINDA YER ALMAKTADIR   
🟥 
🟥 
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


🟥🟥🟥🟥🟥
🟥  GitHub Secrets Ayarlama
GitHub repository settings → Secrets and variables → Actions sayfasında:
GITHUB_TOKEN (otomatik olarak gelir, eklemenize gerek yok)
RENDER_DEPLOY_HOOK (Render webhook URL'i, opsiyonel)
ORACLE_HOST (Oracle VPS IP adresi, opsiyonel)
ORACLE_SSH_KEY (SSH private key, opsiyonel)
ORACLE_USER (SSH kullanıcı adı, genellikle "ubuntu", opsiyonel)

🟥 Health Endpoint Ekleme main.py içine
🟥 Değişiklikleri GitHub'a push edin:
      git add .
      git commit -m "GHCR docker deployment setup"
      git push origin main   

🟥🟪 RENDER için Ek Adımlar:
>> Render Dashboard'da:
"New +" → "Web Service"
GitHub repo'nu bağla
Build Command: docker build -t mbot1 .
Start Command: docker run -p 10000:3000 mbot1
Plan: Free
>> Environment Variables:
bash
PORT=3000
PYTHONUNBUFFERED=1
>> Webhook'u al:
Settings → "Manual Deploy Hook" → Copy URL
GitHub Secrets'a RENDER_DEPLOY_HOOK olarak ekle

🟥🟦 RAILWAY için Ek Adımlar:
Railway Dashboard'da:
"New Project" → "Deploy from GitHub"
Repo'yu seç
Variables: Otomatik environment variables
Webhook oluştur:
Settings → "Deploy Hooks" → "Create Deploy Hook"
URL'yi GitHub Secrets'a RAILWAY_DEPLOY_HOOK olarak ekle


🟥🟧 ORACLE VPS için Ek Adımlar:
VPS'de Docker Kurulumu:HEPSİ KOD

# Oracle Ubuntu VPS'ye bağlan
ssh ubuntu@your-oracle-ip

# Docker kur
sudo apt update
sudo apt install docker.io
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Docker Compose kur (opsiyonel)
sudo apt install docker-compose
GHCR Login (VPS'de):

# Personal Access Token ile login
echo $GHCR_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
SSH Key Oluşturma:

# Lokalde SSH key pair oluştur
ssh-keygen -t rsa -b 4096 -f oracle_deploy_key

# Public key'i VPS'ye ekle
ssh-copy-id -i oracle_deploy_key.pub ubuntu@your-oracle-ip


🟥🟧🟥🟧GitHub Secrets Ayarları:
Secret Adı	Değer	Platform
RENDER_DEPLOY_HOOK	https://api.render.com/deploy/...	Render
RAILWAY_DEPLOY_HOOK	https://api.railway.app/...	Railway
ORACLE_HOST	123.45.67.89	Oracle VPS
ORACLE_SSH_KEY	-----BEGIN PRIVATE KEY-----...	Oracle VPS
ORACLE_USER	ubuntu	Oracle VPS
GHCR_TOKEN	github_pat_...	Tümü (opsiyonel)
Platforma Özel Secrets:
            
Secret Adı	Platform	Nasıl Alınır?
RENDER_DEPLOY_HOOK	:	Render Dashboard → Web Service → Settings → Manual Deploy Hook
RAILWAY_TOKEN :	Railway Dashboard → Settings → API → Generate Token
ORACLE_HOST	Oracle VPS	VPS IP adresi (örn: 123.45.67.89)
ORACLE_SSH_KEY	Oracle VPS	SSH private key içeriği
