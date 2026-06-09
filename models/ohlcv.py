from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from .database import Base

class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    source = Column(String, default="yfinance")

    # Hypertable indices (TimescaleDB best practices)
    __table_args__ = (
        Index('ix_ohlcv_ticker_time', 'ticker_id', 'timestamp', unique=True),
    )
