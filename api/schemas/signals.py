from pydantic import BaseModel
from typing import Optional

class SignalRequest(BaseModel):
    ticker: str
    sentiment_label: Optional[str] = "neutral"
    technical_weight: Optional[float] = 0.7
    sentiment_weight: Optional[float] = 0.3

class SignalResponse(BaseModel):
    ticker: str
    action: str
    unified_score: float
    technical_score: float
    sentiment_score: float
    close_price: float
    timestamp: str
