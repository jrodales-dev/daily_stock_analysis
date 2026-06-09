from workers.celery_app import celery_app
from backtesting.engine import BacktestEngine
from ingestion.market_data.router import MarketDataRouter
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

def fetch_data_sync(ticker: str, start_date: datetime, end_date: datetime):
    """
    Helper to run async code inside the sync Celery worker.
    """
    async def fetch():
        connector = MarketDataRouter()
        return await connector.get_ohlcv(ticker, start_date, end_date)
        
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch())

@celery_app.task(bind=True, name="run_backtest")
def run_backtest_task(self, ticker: str, days: int, technical_weight: float, sentiment_weight: float, mock_sentiment: str):
    """
    Celery task to run a backtest.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 1. Fetch data synchronously (using asyncio helper)
        logger.info(f"Task {self.request.id}: Fetching OHLCV data for {ticker} over {days} days")
        df = fetch_data_sync(ticker, start_date, end_date)
        
        if df.empty:
            return {"status": "FAILED", "error": f"No data found for {ticker}"}
            
        # 2. Run Backtest
        logger.info(f"Task {self.request.id}: Running backtest engine")
        engine = BacktestEngine()
        results = engine.run(
            df, 
            technical_weight=technical_weight, 
            sentiment_weight=sentiment_weight,
            mock_sentiment=mock_sentiment
        )
        
        if "error" in results:
            return {"status": "FAILED", "error": results["error"]}
            
        results["ticker"] = ticker
        results["status"] = "SUCCESS"
        return results
        
    except Exception as e:
        logger.error(f"Task {self.request.id} failed: {e}")
        return {"status": "FAILED", "error": str(e)}
