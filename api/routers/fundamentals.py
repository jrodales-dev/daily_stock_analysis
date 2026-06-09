from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Any
from api.schemas.fundamentals import CompanyProfile, KeyMetrics, FinancialsResponse
from ingestion.fundamentals.base import BaseFundamentalsConnector
from ingestion.fundamentals.fmp import FMPConnector
from ingestion.fundamentals.simfin import SimFinConnector
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class FundamentalsRouter(BaseFundamentalsConnector):
    """
    Fallback router for fundamental data.
    """
    def __init__(self):
        self.providers: List[BaseFundamentalsConnector] = []
        try:
            self.providers.append(FMPConnector())
        except Exception as e:
            logger.warning(f"Could not init FMP: {e}")
            
        try:
            self.providers.append(SimFinConnector())
        except Exception as e:
            logger.warning(f"Could not init SimFin: {e}")
            
    async def get_profile(self, ticker: str) -> Dict[str, Any]:
        for provider in self.providers:
            try:
                if await provider.health_check():
                    return await provider.get_profile(ticker)
            except Exception as e:
                logger.warning(f"{provider.__class__.__name__} profile failed for {ticker}: {e}")
        raise HTTPException(status_code=503, detail="All fundamental providers failed to fetch profile")

    async def get_financials(self, ticker: str, period: str = "annual", limit: int = 5) -> List[Dict[str, Any]]:
        for provider in self.providers:
            try:
                if await provider.health_check():
                    return await provider.get_financials(ticker, period, limit)
            except Exception as e:
                logger.warning(f"{provider.__class__.__name__} financials failed for {ticker}: {e}")
        raise HTTPException(status_code=503, detail="All fundamental providers failed to fetch financials")

    async def get_key_metrics(self, ticker: str) -> Dict[str, Any]:
        for provider in self.providers:
            try:
                if await provider.health_check():
                    return await provider.get_key_metrics(ticker)
            except Exception as e:
                logger.warning(f"{provider.__class__.__name__} metrics failed for {ticker}: {e}")
        raise HTTPException(status_code=503, detail="All fundamental providers failed to fetch metrics")
        
    async def health_check(self) -> bool:
        for provider in self.providers:
            if await provider.health_check():
                return True
        return False

def get_fundamentals_connector():
    return FundamentalsRouter()

@router.get("/profile", response_model=CompanyProfile)
async def get_profile(
    ticker: str = Query(..., description="Stock ticker symbol"),
    connector: FundamentalsRouter = Depends(get_fundamentals_connector)
):
    return await connector.get_profile(ticker)

@router.get("/metrics", response_model=KeyMetrics)
async def get_key_metrics(
    ticker: str = Query(..., description="Stock ticker symbol"),
    connector: FundamentalsRouter = Depends(get_fundamentals_connector)
):
    return await connector.get_key_metrics(ticker)

@router.get("/financials", response_model=FinancialsResponse)
async def get_financials(
    ticker: str = Query(..., description="Stock ticker symbol"),
    period: str = Query("annual", description="annual or quarter"),
    limit: int = Query(5, description="Number of periods"),
    connector: FundamentalsRouter = Depends(get_fundamentals_connector)
):
    data = await connector.get_financials(ticker, period, limit)
    return FinancialsResponse(ticker=ticker, period=period, data=data)
