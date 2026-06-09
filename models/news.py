from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from .database import Base

class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=True, index=True) # Optional if global news
    title = Column(String, nullable=False)
    content = Column(Text)
    url = Column(String, unique=True)
    published_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String)
    sentiment_score = Column(Float) # -1.0 to 1.0
    sentiment_label = Column(String) # POSITIVE, NEUTRAL, NEGATIVE
    tags = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
