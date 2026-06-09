import httpx
import logging
from typing import Dict, Any, List
from execution.base import BaseBrokerConnector
from core.config import settings

logger = logging.getLogger(__name__)

class AlpacaBrokerConnector(BaseBrokerConnector):
    """
    Broker implementation for Alpaca Trade API.
    Uses async httpx for high performance.
    """
    
    def __init__(self):
        self.api_key = settings.ALPACA_API_KEY
        self.secret_key = settings.ALPACA_SECRET_KEY
        
        # Determine if we are using paper trading or live based on URL or key
        # Default to paper trading endpoint for safety if not explicitly set
        self.base_url = "https://paper-api.alpaca.markets/v2" 
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    async def get_account(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Alpaca API keys not configured"}
            
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/account", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Alpaca API Error: {response.text}")
                return {"error": response.text}

    async def get_positions(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
            
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/positions", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Alpaca API Error: {response.text}")
                return []

    async def submit_order(self, symbol: str, qty: float, side: str, order_type: str = "market", time_in_force: str = "gtc", limit_price: float = None) -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Alpaca API keys not configured"}
            
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force
        }
        
        if order_type == "limit" and limit_price is not None:
            payload["limit_price"] = limit_price
            
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/orders", json=payload, headers=self.headers)
            if response.status_code in (200, 201):
                return response.json()
            else:
                logger.error(f"Alpaca API Error submitting order: {response.text}")
                return {"error": response.json().get("message", "Unknown error")}

    async def cancel_order(self, order_id: str) -> bool:
        if not self.api_key:
            return False
            
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/orders/{order_id}", headers=self.headers)
            return response.status_code in (200, 204)

    async def get_portfolio_history(self, period="1M", timeframe="1D") -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Alpaca API keys not configured"}
            
        async with httpx.AsyncClient() as client:
            params = {
                "period": period,
                "timeframe": timeframe
            }
            response = await client.get(f"{self.base_url}/account/portfolio/history", headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Alpaca API Error fetching portfolio history: {response.text}")
                return {"error": response.text}
