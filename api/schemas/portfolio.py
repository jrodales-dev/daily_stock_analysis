from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class OrderRequest(BaseModel):
    ticker: str
    action: str  # BUY or SELL
    quantity: Optional[int] = None # If None, calculates automatically based on risk
    current_price: Optional[float] = None
    atr: Optional[float] = None

class OrderResponse(BaseModel):
    status: str
    action: Optional[str] = None
    shares: Optional[int] = None
    error: Optional[str] = None
    order_details: Optional[Dict[str, Any]] = None

class AccountResponse(BaseModel):
    portfolio_value: str
    buying_power: str
    cash: str
    currency: str

class PositionItem(BaseModel):
    symbol: str
    qty: str
    market_value: str
    unrealized_pl: str
    unrealized_plpc: str
