import pandas as pd
from typing import Dict, Any
from datetime import datetime
from ingestion.base import BaseDataConnector
from core.config import settings
import httpx

class AlpacaConnector(BaseDataConnector):
    """
    Data connector for Alpaca Market Data API v2.
    """
    def __init__(self):
        self.api_key = settings.ALPACA_API_KEY
        self.secret_key = settings.ALPACA_SECRET_KEY
        self.base_url = "https://data.alpaca.markets/v2"
        self.headers = {
            "APCA-API-KEY-ID": self.api_key or "",
            "APCA-API-SECRET-KEY": self.secret_key or ""
        }
        
    async def get_ohlcv(self, ticker: str, start: datetime, end: datetime, interval: str = "1d") -> pd.DataFrame:
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API keys not configured")
            
        timeframe = "1Day"
        if interval == "1h":
            timeframe = "1Hour"
        elif interval == "15m":
            timeframe = "15Min"
            
        url = f"{self.base_url}/stocks/{ticker}/bars"
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeframe": timeframe,
            "adjustment": "all"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                raise Exception(f"Alpaca API Error: {response.text}")
                
            data = response.json()
            if "bars" not in data or not data["bars"]:
                return pd.DataFrame()
                
            df = pd.DataFrame(data["bars"])
            
            # Map Alpaca columns: t (timestamp), o (open), h (high), l (low), c (close), v (volume)
            df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                't': 'timestamp'
            }, inplace=True)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API keys not configured")
            
        url = f"{self.base_url}/stocks/{ticker}/quotes/latest"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            
            if response.status_code != 200:
                # Alpaca provides separate trade/quote endpoints. For simple quote we use latest trade as well to get last price.
                trade_url = f"{self.base_url}/stocks/{ticker}/trades/latest"
                trade_resp = await client.get(trade_url, headers=self.headers)
                if trade_resp.status_code != 200:
                    raise Exception(f"Alpaca API Error: {response.text}")
                data = trade_resp.json()
                trade_price = data.get("trade", {}).get("p")
                return {
                    'ticker': ticker,
                    'last': trade_price,
                    'bid': None,
                    'ask': None,
                    'volume': None,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'alpaca'
                }
                
            quote_data = response.json().get("quote", {})
            
            # Fetch latest trade to get the actual last price
            trade_url = f"{self.base_url}/stocks/{ticker}/trades/latest"
            trade_resp = await client.get(trade_url, headers=self.headers)
            last_price = None
            if trade_resp.status_code == 200:
                last_price = trade_resp.json().get("trade", {}).get("p")
            
            return {
                'ticker': ticker,
                'last': last_price,
                'bid': quote_data.get('bp'),
                'ask': quote_data.get('ap'),
                'volume': None, # Latest quote doesn't include cumulative volume by default in this endpoint
                'timestamp': datetime.now().isoformat(),
                'source': 'alpaca'
            }
            
    async def health_check(self) -> bool:
        if not self.api_key or not self.secret_key:
            return False
        try:
            quote = await self.get_quote("SPY")
            return quote.get('last') is not None or quote.get('bid') is not None
        except Exception:
            return False
