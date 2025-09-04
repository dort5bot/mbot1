"""
# main.py
* .env dahil edilmiş yapı

"""
from utils.config import get_config
from utils.handler_loader import load_handlers    #plugin handler loader

def main():
    # ✅ Config'i yükle (default değerler + .env override'lar)
    config = get_config()
    
    # 🔐 GÜVENLİK - .env'den (ZORUNLU)
    print(f"API Key: {config.api_key}")
    
    # ⚙️ TECHNICAL - Default değerler
    print(f"Request Timeout: {config.REQUEST_TIMEOUT}")
    print(f"Max Requests: {config.MAX_REQUESTS_PER_SECOND}")
    
    # 📊 BUSINESS - Default değerler veya .env override
    print(f"Scan Symbols: {config.SCAN_SYMBOLS}")
    print(f"Alert Threshold: {config.ALERT_PRICE_CHANGE_PERCENT}%")
    
    # Örnek: Tüm symbol'leri tarama
    for symbol in config.SCAN_SYMBOLS:
        print(f"Scanning: {symbol}")

    
    # Handler yükle
    load_handlers(app)


if __name__ == "__main__":
    main()
