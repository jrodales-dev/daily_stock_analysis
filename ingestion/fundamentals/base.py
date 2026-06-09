from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd

class BaseFundamentalsConnector(ABC):
    """
    Abstract base class for fundamental data connectors (FMP, SimFin, etc).
    """
    
    @abstractmethod
    async def get_profile(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch company profile details (industry, sector, description, etc).
        """
        pass
        
    @abstractmethod
    async def get_financials(self, ticker: str, period: str = "annual", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch income statement, balance sheet, or cash flow statements.
        """
        pass
        
    @abstractmethod
    async def get_key_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch key financial metrics (PE, PB, ROE, etc).
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the connector is healthy and authenticated.
        """
        pass
