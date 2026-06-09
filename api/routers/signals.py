from fastapi import APIRouter, Depends, HTTPException, Body
from api.schemas.signals import SignalRequest, SignalResponse
from ingestion.market_data.router import MarketDataRouter
from processing.technical.indicators import add_all_indicators
from processing.signals.engine import SignalEngine
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Reusing the market data router from Phase 2
market_connector_instance = MarketDataRouter()

def get_market_connector():
    return market_connector_instance

@router.post("/generate", response_model=SignalResponse)
async def generate_signal(
    request: SignalRequest = Body(...),
    connector: MarketDataRouter = Depends(get_market_connector)
):
    """
    Generate a unified trading signal based on recent OHLCV data and provided sentiment.
    """
    try:
        # Fetch last 60 days of data to properly calculate indicators like SMA50
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        df = await connector.get_ohlcv(request.ticker, start_date, end_date)
        if df.empty:
            raise HTTPException(status_code=404, detail="No market data found for ticker")
            
        # Apply technical indicators
        df_ind = add_all_indicators(df)
        
        # Instantiate signal engine with user weights
        engine = SignalEngine(
            technical_weight=request.technical_weight, 
            sentiment_weight=request.sentiment_weight
        )
        
        # Calculate unified signal
        signal_data = engine.calculate_unified_signal(df_ind, request.sentiment_label)
        
        if "error" in signal_data:
            raise HTTPException(status_code=500, detail=signal_data["error"])
            
        return SignalResponse(
            ticker=request.ticker,
            **signal_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
