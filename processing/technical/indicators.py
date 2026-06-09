import pandas as pd
import numpy as np

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all basic technical indicators to a DataFrame.
    DataFrame must have 'close', 'high', 'low', 'volume' columns.
    """
    if df.empty or 'close' not in df.columns:
        return df
        
    df = df.copy()
    
    # Simple Moving Averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Exponential Moving Averages
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    # Relative Strength Index (RSI) - 14 periods
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_line'] = ema_12 - ema_26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd_line'] - df['macd_signal']
    
    # Bollinger Bands (20 periods, 2 std dev)
    std_20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma_20'] + (std_20 * 2)
    df['bb_lower'] = df['sma_20'] - (std_20 * 2)
    
    # Average True Range (ATR) - 14 periods
    if 'high' in df.columns and 'low' in df.columns:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr_14'] = true_range.rolling(14).mean()
        
    return df
