from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime, timedelta
from api.schemas.market import QuoteResponse, OHLCVResponse
from ingestion.market_data.router import MarketDataRouter
import json

router = APIRouter()

# Dependency to get the active connector
def get_market_connector():
    return MarketDataRouter()

@router.get("/quote", response_model=QuoteResponse)
async def get_quote(
    ticker: str = Query(..., description="Stock ticker symbol"),
    connector: MarketDataRouter = Depends(get_market_connector)
):
    """
    Get real-time (or delayed) quote for a given ticker.
    """
    try:
        quote = await connector.get_quote(ticker)
        if not quote or quote.get('last') is None:
            raise HTTPException(status_code=404, detail=f"Quote not found for ticker {ticker}")
        return quote
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    ticker: str = Query(..., description="Stock ticker symbol"),
    start_date: Optional[datetime] = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (defaults to today)"),
    interval: str = Query("1d", description="Data interval (e.g., 1d, 1h, 15m)"),
    connector: MarketDataRouter = Depends(get_market_connector)
):
    """
    Get historical OHLCV data for a given ticker.
    """
    try:
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        df = await connector.get_ohlcv(ticker, start_date, end_date, interval)
        
        if df.empty:
            return {"ticker": ticker, "data": [], "source": "yfinance"}
            
        # Convert DataFrame to list of dicts safely handling NaNs
        # Using json to handle NaNs/NaTs properly 
        df_json = df.to_json(orient="records", date_format="iso")
        data_records = json.loads(df_json)
        
        return {
            "ticker": ticker,
            "data": data_records,
            "source": "yfinance"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
