from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
import logging
from ingestion.base import BaseDataConnector
from ingestion.market_data.polygon import PolygonConnector
from ingestion.market_data.alpaca import AlpacaConnector
from ingestion.market_data.yfinance_connector import YFinanceConnector

logger = logging.getLogger(__name__)

class MarketDataRouter(BaseDataConnector):
    """
    Router/Orchestrator that attempts to fetch data from multiple providers with automatic fallback.
    Order: Polygon -> Alpaca -> YFinance
    """
    def __init__(self):
        # Initialize providers. In a real system, we might only initialize those with API keys.
        self.providers: List[BaseDataConnector] = []
        
        try:
            self.providers.append(PolygonConnector())
        except Exception as e:
            logger.warning(f"Could not initialize PolygonConnector: {e}")
            
        try:
            self.providers.append(AlpacaConnector())
        except Exception as e:
            logger.warning(f"Could not initialize AlpacaConnector: {e}")
            
        # YFinance is always available (no API key required)
        self.providers.append(YFinanceConnector())

    async def get_ohlcv(self, ticker: str, start: datetime, end: datetime, interval: str = "1d") -> pd.DataFrame:
        errors = []
        for provider in self.providers:
            # Skip provider if API keys are missing, which is handled gracefully in their methods or we can check before
            try:
                # Basic check if it's healthy or has keys
                if not await provider.health_check():
                    continue
                    
                df = await provider.get_ohlcv(ticker, start, end, interval)
                if not df.empty:
                    # Successfully fetched data
                    return df
            except Exception as e:
                provider_name = provider.__class__.__name__
                logger.warning(f"{provider_name} failed for {ticker}: {e}")
                errors.append(f"{provider_name}: {e}")
                
        raise Exception(f"All data providers failed to fetch OHLCV for {ticker}. Errors: {errors}")

    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        errors = []
        for provider in self.providers:
            try:
                if not await provider.health_check():
                    continue
                    
                quote = await provider.get_quote(ticker)
                if quote and quote.get('last') is not None:
                    return quote
            except Exception as e:
                provider_name = provider.__class__.__name__
                logger.warning(f"{provider_name} failed to fetch quote for {ticker}: {e}")
                errors.append(f"{provider_name}: {e}")
                
        raise Exception(f"All data providers failed to fetch quote for {ticker}. Errors: {errors}")

    async def health_check(self) -> bool:
        # Healthy if at least one provider is healthy
        for provider in self.providers:
            if await provider.health_check():
                return True
        return False
