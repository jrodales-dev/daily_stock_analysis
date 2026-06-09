from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class QuoteResponse(BaseModel):
    ticker: str
    last: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[float]
    timestamp: str
    source: str

class OHLCVDataPoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class OHLCVResponse(BaseModel):
    ticker: str
    data: List[OHLCVDataPoint]
    source: str
