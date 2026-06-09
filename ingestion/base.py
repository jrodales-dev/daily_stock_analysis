from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime

class BaseDataConnector(ABC):
    """
    Abstract base class for all data ingestion connectors.
    Ensures a standardized interface across different data providers.
    """
    
    @abstractmethod
    async def get_ohlcv(self, ticker: str, start: datetime, end: datetime, interval: str = "1d") -> pd.DataFrame:
        """
        Fetch historical OHLCV data.
        Returns a DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        pass
    
    @abstractmethod
    async def get_quote(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch real-time quote data.
        Returns a dictionary with keys like: 'last', 'bid', 'ask', 'volume', 'timestamp'
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the data provider API is reachable and responding.
        """
        pass
