import yfinance as yf
import pandas as pd
from typing import Dict, Any
from datetime import datetime
from ingestion.base import BaseDataConnector

class YFinanceConnector(BaseDataConnector):
    """
    Data connector for Yahoo Finance using the yfinance library.
    """
    
    async def get_ohlcv(self, ticker: str, start: datetime, end: datetime, interval: str = "1d") -> pd.DataFrame:
        """
        Fetch historical OHLCV data.
        """
        # Convert datetime to string for yfinance
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        
        # yfinance is synchronous, but we are wrapping it. 
        # In a fully production system we might use loop.run_in_executor
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(start=start_str, end=end_str, interval=interval)
        
        if df.empty:
            return pd.DataFrame()
            
        # Standardize columns
        df = df.reset_index()
        # Handle different index names (Date or Datetime)
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'timestamp'}, inplace=True)
        elif 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'timestamp'}, inplace=True)
            
        df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }, inplace=True)
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch real-time (or delayed) quote data.
        """
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        # Determine the last price
        last_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        
        return {
            'ticker': ticker,
            'last': last_price,
            'bid': info.get('bid'),
            'ask': info.get('ask'),
            'volume': info.get('volume'),
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        }
    
    async def health_check(self) -> bool:
        """
        Check if yfinance can fetch a basic quote.
        """
        try:
            quote = await self.get_quote("SPY")
            return quote.get('last') is not None
        except Exception:
            return False
