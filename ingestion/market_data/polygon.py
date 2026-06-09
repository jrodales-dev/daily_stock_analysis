import pandas as pd
from typing import Dict, Any
from datetime import datetime
from ingestion.base import BaseDataConnector
from core.config import settings
import httpx

class PolygonConnector(BaseDataConnector):
    """
    Data connector for Polygon.io API.
    """
    def __init__(self):
        self.api_key = settings.POLYGON_API_KEY
        self.base_url = "https://api.polygon.io"
        
    async def get_ohlcv(self, ticker: str, start: datetime, end: datetime, interval: str = "1d") -> pd.DataFrame:
        if not self.api_key:
            raise ValueError("Polygon API key not configured")
            
        # Map our interval to Polygon's multiplier and timespan
        # Simple mapping for MVP (1d, 1h, 15m)
        multiplier = 1
        timespan = "day"
        if interval == "1h":
            timespan = "hour"
        elif interval == "15m":
            multiplier = 15
            timespan = "minute"
            
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start_str}/{end_str}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "apiKey": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                raise Exception(f"Polygon API Error: {response.text}")
                
            data = response.json()
            if "results" not in data or not data["results"]:
                return pd.DataFrame()
                
            df = pd.DataFrame(data["results"])
            
            # Map Polygon columns to standard format
            # Polygon uses: v (volume), o (open), c (close), h (high), l (low), t (timestamp in ms)
            df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                't': 'timestamp'
            }, inplace=True)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("Polygon API key not configured")
            
        url = f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        params = {"apiKey": self.api_key}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise Exception(f"Polygon API Error: {response.text}")
                
            data = response.json()
            if "ticker" not in data or not data.get("ticker"):
                raise ValueError("Quote not found in Polygon response")
                
            ticker_data = data["ticker"]
            last_quote = ticker_data.get("lastQuote", {})
            last_trade = ticker_data.get("lastTrade", {})
            
            return {
                'ticker': ticker,
                'last': last_trade.get('p'),
                'bid': last_quote.get('p'),
                'ask': last_quote.get('P'),
                'volume': ticker_data.get('day', {}).get('v'),
                'timestamp': datetime.now().isoformat(),
                'source': 'polygon'
            }
            
    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            quote = await self.get_quote("SPY")
            return quote.get('last') is not None
        except Exception:
            return False
