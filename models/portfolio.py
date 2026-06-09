from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from models.database import Base
import datetime

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_value = Column(Float)
    buying_power = Column(Float)
    cash = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
