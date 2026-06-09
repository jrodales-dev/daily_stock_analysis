from pydantic import BaseModel
from typing import Optional, List

class SentimentScore(BaseModel):
    positive: float
    negative: float
    neutral: float
    label: str

class NewsArticle(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    ticker: Optional[str] = None
    sentiment: Optional[SentimentScore] = None

class NewsListResponse(BaseModel):
    ticker: str
    articles: List[NewsArticle]

class AnalyzeTextRequest(BaseModel):
    texts: List[str]

class AnalyzeTextResponse(BaseModel):
    results: List[SentimentScore]
