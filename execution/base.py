from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseBrokerConnector(ABC):
    """
    Abstract base class for broker connectors.
    All broker integrations must implement these methods.
    """
    
    @abstractmethod
    async def get_account(self) -> Dict[str, Any]:
        """Get account details (balance, buying power, etc.)"""
        pass
        
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        pass
        
    @abstractmethod
    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = "market", time_in_force: str = "gtc", limit_price: float = None) -> Dict[str, Any]:
        """Submit a new order"""
        pass
        
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        pass
