from fastapi import APIRouter, Depends, HTTPException, Body
from api.schemas.backtest import BacktestRequest, BacktestRunResponse, BacktestStatusResponse
from workers.tasks import run_backtest_task
from celery.result import AsyncResult
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRequest = Body(...)):
    """
    Enqueues a backtesting job to Celery.
    """
    try:
        # Dispatch task to Celery
        task = run_backtest_task.delay(
            ticker=request.ticker,
            days=request.days,
            technical_weight=request.technical_weight,
            sentiment_weight=request.sentiment_weight,
            mock_sentiment=request.mock_sentiment
        )
        
        return BacktestRunResponse(
            task_id=task.id,
            status="PENDING",
            message="Backtest queued successfully. Use /status endpoint to check progress."
        )
    except Exception as e:
        logger.error(f"Error queueing backtest: {e}")
        raise HTTPException(status_code=500, detail="Could not queue backtest task")

@router.get("/status/{task_id}", response_model=BacktestStatusResponse)
async def get_backtest_status(task_id: str):
    """
    Check the status and result of a backtesting job.
    """
    try:
        task_result = AsyncResult(task_id)
        
        if task_result.state == "PENDING":
            return BacktestStatusResponse(task_id=task_id, status="PENDING")
        elif task_result.state == "SUCCESS":
            # The task returns a dict with status and results or error
            result_data = task_result.result
            if result_data.get("status") == "FAILED":
                return BacktestStatusResponse(task_id=task_id, status="FAILED", result={"error": result_data.get("error")})
                
            return BacktestStatusResponse(task_id=task_id, status="SUCCESS", result=result_data)
        elif task_result.state == "FAILURE":
            return BacktestStatusResponse(task_id=task_id, status="FAILED", result={"error": str(task_result.info)})
        else:
            return BacktestStatusResponse(task_id=task_id, status=task_result.state)
            
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve task status")
