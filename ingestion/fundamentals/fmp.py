import httpx
from typing import Dict, Any, List
from ingestion.fundamentals.base import BaseFundamentalsConnector
from core.config import settings

class FMPConnector(BaseFundamentalsConnector):
    """
    Financial Modeling Prep (FMP) connector for fundamental data.
    """
    def __init__(self):
        self.api_key = settings.FMP_API_KEY
        self.base_url = "https://financialmodelingprep.com/api/v3"
        
    async def get_profile(self, ticker: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("FMP API key not configured")
            
        url = f"{self.base_url}/profile/{ticker}"
        params = {"apikey": self.api_key}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                return {}
            
            profile = data[0]
            return {
                "ticker": ticker,
                "company_name": profile.get("companyName"),
                "industry": profile.get("industry"),
                "sector": profile.get("sector"),
                "description": profile.get("description"),
                "market_cap": profile.get("mktCap"),
                "source": "fmp"
            }
            
    async def get_financials(self, ticker: str, period: str = "annual", limit: int = 5) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("FMP API key not configured")
            
        # For MVP we will just fetch the income statement
        url = f"{self.base_url}/income-statement/{ticker}"
        params = {"apikey": self.api_key, "period": period, "limit": limit}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
    async def get_key_metrics(self, ticker: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("FMP API key not configured")
            
        url = f"{self.base_url}/key-metrics-ttm/{ticker}"
        params = {"apikey": self.api_key}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                return {}
                
            metrics = data[0]
            return {
                "ticker": ticker,
                "pe_ratio": metrics.get("peRatioTTM"),
                "pb_ratio": metrics.get("pbRatioTTM"),
                "roe": metrics.get("roeTTM"),
                "eps": metrics.get("netIncomePerShareTTM"),
                "source": "fmp"
            }

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            profile = await self.get_profile("AAPL")
            return bool(profile)
        except Exception:
            return False
