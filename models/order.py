from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from models.database import Base
import datetime

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    broker_order_id = Column(String, unique=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"))
    action = Column(String) # BUY / SELL
    qty = Column(Float)
    filled_qty = Column(Float, default=0.0)
    limit_price = Column(Float, nullable=True)
    filled_avg_price = Column(Float, nullable=True)
    status = Column(String) # PENDING, FILLED, CANCELED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
