from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_get_quote():
    response = client.get("/api/v1/market/quote?ticker=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert "last" in data

def test_get_ohlcv():
    response = client.get("/api/v1/market/ohlcv?ticker=AAPL&interval=1d")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert isinstance(data["data"], list)
