from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from .database import Base

class Fundamentals(Base):
    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    roe = Column(Float)
    debt_to_equity = Column(Float)
    free_cash_flow = Column(Float)
    raw_data = Column(JSON) # To store provider specific data
    source = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
