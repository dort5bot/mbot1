NOT > ANA BİLGİ İSKELET İÇİNDE
#
/analys
/io
/ap
#
#

handlers/p_handler.py
Binance datasında küçük/büyük fark olsa da eşleşir.
async uyumlu + PEP8 + type hints + docstring + async yapı + singleton + logging olacak
/p<n|d> <coin|sayı>
/p →CONFIG.SCAN_SYMBOLS default(filtre ekler btc ile btcusdt sonuç verir)
/Pn → sayı girilirse limit = n, hacimli ilk n coin.
/Pd → düşenler. default 20 tane
/Pd 30 → düşenler 30 tane
/P coin1 coin2... → manuel seçili coinler.


örnek:
/p

Debot2🟢, [7.09.2025 17:08]
📈 SCAN_SYMBOLS (Hacme Göre)
⚡Coin | Değişim | Hacim | Fiyat
1. ETH: 0.23% | $888.8M | 4308.17
2. BTC: 0.37% | $657.1M | 111353.1
3. TRX: 0.21% | $340.8M | 0.3312
4. SOL: 0.70% | $268.1M | 203.75
...


/pd
📈 Düşüş Trendindeki Coinler
⚡Coin | Değişim | Hacim | Fiyat
1. BETA: -64.00% | $0.3M | 0.00036
2. VIB: -63.26% | $0.4M | 0.00223
3. WTC: -56.54% | $0.5M | 0.0103
...


/p eth bnb sol

📈 Seçili Coinler
⚡Coin | Değişim | Hacim | Fiyat
1. BNB: 1.45% | $107.2M | 873.7
2. SOL: 0.73% | $269.2M | 203.78
3. ETH: 0.23% | $889.4M | 4307.04
