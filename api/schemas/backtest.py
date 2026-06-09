from pydantic import BaseModel
from typing import Optional, Dict, Any

class BacktestRequest(BaseModel):
    ticker: str
    days: Optional[int] = 365
    technical_weight: Optional[float] = 0.7
    sentiment_weight: Optional[float] = 0.3
    mock_sentiment: Optional[str] = "neutral"

class BacktestRunResponse(BaseModel):
    task_id: str
    status: str
    message: str

class BacktestStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
