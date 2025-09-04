"""Binance yardımcı fonksiyonlar."""

import pandas as pd
from typing import List, Any, Union

def klines_to_dataframe(klines: List[List[Any]]) -> pd.DataFrame:
    """Kline verisini pandas DataFrame'e dönüştür."""
    try:
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    
    except Exception as e:
        # Fallback: boş DataFrame döndür
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])