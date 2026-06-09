import pandas as pd
import numpy as np
from typing import Dict, Any, List
from processing.technical.indicators import add_all_indicators
from processing.signals.engine import SignalEngine
import logging

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Vectorized Backtesting Engine using Pandas for fast performance.
    Evaluates the SignalEngine logic over historical data.
    """
    
    def __init__(self, initial_capital: float = 10000.0, transaction_cost: float = 0.001):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost

    def run(self, df: pd.DataFrame, technical_weight: float = 0.7, sentiment_weight: float = 0.3, mock_sentiment: str = "neutral") -> Dict[str, Any]:
        """
        Runs the backtest over the provided OHLCV dataframe.
        Because we don't have historical sentiment data in the MVP easily aligned with daily OHLCV, 
        we use a `mock_sentiment` to demonstrate how the unified signal works historically.
        In a real scenario, `df` would have a 'sentiment' column.
        """
        if df.empty or len(df) < 50:
            return {"error": "Not enough data for backtesting (need at least 50 periods for SMA50)"}

        # Calculate indicators
        df = add_all_indicators(df).copy()
        
        # We need to simulate the signal logic over the entire dataframe vectorially
        # This is a vectorized approximation of the SignalEngine logic for speed
        df['score'] = 0.0
        
        # RSI Logic
        df.loc[df['rsi_14'] < 30, 'score'] += 0.3
        df.loc[df['rsi_14'] > 70, 'score'] -= 0.3
        
        # MACD Logic
        df.loc[df['macd_hist'] > 0, 'score'] += 0.2
        df.loc[df['macd_hist'] < 0, 'score'] -= 0.2
        
        # Moving Average Crossover
        df.loc[(df['sma_20'] > df['sma_50']) & (df['close'] > df['sma_20']), 'score'] += 0.3
        df.loc[(df['sma_20'] < df['sma_50']) & (df['close'] < df['sma_20']), 'score'] -= 0.3
        
        # Bound scores
        df['tech_score'] = df['score'].clip(lower=-1.0, upper=1.0)
        
        # Sentiment score (Mocked for historical vectorized run)
        engine = SignalEngine()
        sent_score = engine.map_sentiment_to_score(mock_sentiment)
        df['sent_score'] = sent_score
        
        # Unified score
        df['unified_score'] = (df['tech_score'] * technical_weight) + (df['sent_score'] * sentiment_weight)
        
        # Generate Trading Signals: +1 (Buy/Long), -1 (Sell/Short), 0 (Cash/Hold)
        # Using simple thresholds based on the unified score
        df['position'] = 0
        df.loc[df['unified_score'] >= 0.15, 'position'] = 1
        df.loc[df['unified_score'] <= -0.15, 'position'] = -1
        
        # Shift position by 1 because we calculate signal at close and trade at next open
        df['position'] = df['position'].shift(1).fillna(0)
        
        # Calculate Returns
        df['returns'] = df['close'].pct_change()
        
        # Strategy Returns = position * returns - transaction costs on trades
        # Trades happen when position changes
        df['trades'] = df['position'].diff().abs()
        df['strategy_returns'] = (df['position'] * df['returns']) - (df['trades'] * self.transaction_cost)
        
        # Equity Curve
        df['equity_curve'] = self.initial_capital * (1 + df['strategy_returns']).cumprod()
        
        # Metrics Calculation
        total_return = (df['equity_curve'].iloc[-1] / self.initial_capital) - 1
        annualized_return = (1 + total_return) ** (252 / len(df)) - 1
        
        # Max Drawdown
        cumulative_max = df['equity_curve'].cummax()
        drawdown = (df['equity_curve'] / cumulative_max) - 1
        max_drawdown = drawdown.min()
        
        # Sharpe Ratio (Assuming Risk Free Rate = 0)
        daily_volatility = df['strategy_returns'].std()
        sharpe_ratio = (df['strategy_returns'].mean() / daily_volatility) * np.sqrt(252) if daily_volatility != 0 else 0
        
        # Win Rate
        winning_trades = len(df[df['strategy_returns'] > 0])
        total_active_days = len(df[df['position'] != 0])
        win_rate = winning_trades / total_active_days if total_active_days > 0 else 0
        
        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(df['equity_curve'].iloc[-1], 2),
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(annualized_return * 100, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "win_rate_pct": round(win_rate * 100, 2),
            "total_trades": int(df['trades'].sum() / 2), # divide by 2 since entry/exit is 2 changes
            "days_analyzed": len(df)
        }
