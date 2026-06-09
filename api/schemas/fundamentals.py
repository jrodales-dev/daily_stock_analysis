from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CompanyProfile(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    market_cap: Optional[float] = None
    source: str

class KeyMetrics(BaseModel):
    ticker: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    eps: Optional[float] = None
    source: str

class FinancialsResponse(BaseModel):
    ticker: str
    period: str
    data: List[Dict[str, Any]]
