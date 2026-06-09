from fastapi import APIRouter, HTTPException, Body
from typing import List
from api.schemas.portfolio import OrderRequest, OrderResponse, AccountResponse, PositionItem
from processing.portfolio.manager import PortfolioManager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

portfolio_manager = PortfolioManager()

@router.get("/account", response_model=AccountResponse)
async def get_account():
    """
    Get the current broker account summary (buying power, portfolio value).
    """
    try:
        account = await portfolio_manager.get_account_summary()
        if "error" in account:
            raise HTTPException(status_code=400, detail=account["error"])
            
        return AccountResponse(
            portfolio_value=account.get("portfolio_value", "0.0"),
            buying_power=account.get("buying_power", "0.0"),
            cash=account.get("cash", "0.0"),
            currency=account.get("currency", "USD")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve account details")

@router.get("/positions", response_model=List[PositionItem])
async def get_positions():
    """
    Get all open positions in the broker account.
    """
    try:
        positions = await portfolio_manager.get_current_positions()
        
        # Alpaca returns a list of dictionaries. If it returned a dict with error, handle it.
        if isinstance(positions, dict) and "error" in positions:
            raise HTTPException(status_code=400, detail=positions["error"])
            
        formatted_positions = []
        for p in positions:
            formatted_positions.append(PositionItem(
                symbol=p.get("symbol", ""),
                qty=p.get("qty", "0"),
                market_value=p.get("market_value", "0.0"),
                unrealized_pl=p.get("unrealized_pl", "0.0"),
                unrealized_plpc=p.get("unrealized_plpc", "0.0")
            ))
            
        return formatted_positions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve positions")

@router.post("/order", response_model=OrderResponse)
async def submit_order(request: OrderRequest = Body(...)):
    """
    Submit an execution order (Market).
    If quantity is not provided, the portfolio manager calculates the position size 
    based on account risk parameters.
    """
    try:
        if request.quantity is not None and request.quantity > 0:
            # Manual sizing bypass
            logger.info(f"Manual order: {request.action} {request.quantity} of {request.ticker}")
            side = "buy" if request.action in ["BUY", "STRONG_BUY"] else "sell"
            order = await portfolio_manager.broker.submit_order(request.ticker, request.quantity, side)
            if "error" in order:
                return OrderResponse(status="FAILED", error=order["error"])
            return OrderResponse(status="SUCCESS", action=request.action, shares=request.quantity, order_details=order)
        else:
            # Auto sizing based on risk
            if not request.current_price:
                raise HTTPException(status_code=400, detail="current_price is required for auto position sizing")
                
            result = await portfolio_manager.execute_trade(
                symbol=request.ticker,
                signal=request.action,
                current_price=request.current_price,
                atr=request.atr
            )
            
            if result.get("status") == "FAILED":
                return OrderResponse(status="FAILED", error=result.get("error"))
                
            return OrderResponse(
                status=result.get("status", "SUCCESS"),
                action=result.get("action"),
                shares=result.get("shares"),
                order_details=result.get("order")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance(period: str = "1M", timeframe: str = "1D"):
    """
    Get portfolio performance history over time.
    """
    try:
        history = await portfolio_manager.get_portfolio_history(period, timeframe)
        if "error" in history:
            raise HTTPException(status_code=400, detail=history["error"])
        return history
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio performance: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve performance history")
