from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings

# Import routers once they are created
from api.routers import market, fundamentals, news, signals, backtest, reports, portfolio

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add Rate Limit Middleware
from api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Routers
app.include_router(market.router, prefix=f"{settings.API_V1_STR}/market", tags=["market"])
app.include_router(fundamentals.router, prefix=f"{settings.API_V1_STR}/fundamentals", tags=["fundamentals"])
app.include_router(news.router, prefix=f"{settings.API_V1_STR}/news", tags=["news"])
app.include_router(signals.router, prefix=f"{settings.API_V1_STR}/signals", tags=["signals"])
app.include_router(backtest.router, prefix=f"{settings.API_V1_STR}/backtest", tags=["backtest"])
app.include_router(reports.router, prefix=f"{settings.API_V1_STR}/reports", tags=["reports"])
app.include_router(portfolio.router, prefix=f"{settings.API_V1_STR}/portfolio", tags=["portfolio"])

@app.get("/health", tags=["health"])
async def health_check():
    """
    Check if the API is running and healthy.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "project": settings.PROJECT_NAME
    }
