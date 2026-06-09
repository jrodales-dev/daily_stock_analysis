import pytest
from datetime import datetime, timedelta
from ingestion.market_data.yfinance_connector import YFinanceConnector

@pytest.mark.asyncio
async def test_yfinance_health_check():
    connector = YFinanceConnector()
    is_healthy = await connector.health_check()
    assert is_healthy is True

@pytest.mark.asyncio
async def test_yfinance_get_quote():
    connector = YFinanceConnector()
    quote = await connector.get_quote("AAPL")
    
    assert quote is not None
    assert quote["ticker"] == "AAPL"
    assert "last" in quote
    assert "volume" in quote

@pytest.mark.asyncio
async def test_yfinance_get_ohlcv():
    connector = YFinanceConnector()
    end = datetime.now()
    start = end - timedelta(days=5)
    
    df = await connector.get_ohlcv("AAPL", start, end)
    
    assert not df.empty
    assert "timestamp" in df.columns
    assert "open" in df.columns
    assert "close" in df.columns
