import pandas as pd
from typing import Dict, Any

class SignalEngine:
    """
    Engine to generate unified signals combining Technical Analysis and Sentiment.
    Output scale is typically from -1.0 (Strong Sell) to 1.0 (Strong Buy).
    """
    
    def __init__(self, technical_weight: float = 0.7, sentiment_weight: float = 0.3):
        self.technical_weight = technical_weight
        self.sentiment_weight = sentiment_weight

    def generate_technical_signal(self, row: pd.Series) -> float:
        """
        Generate a technical score from -1.0 to 1.0 based on a single row of indicators.
        """
        score = 0.0
        
        # RSI Logic
        rsi = row.get('rsi_14', 50)
        if pd.notna(rsi):
            if rsi < 30:
                score += 0.3  # Oversold -> Bullish
            elif rsi > 70:
                score -= 0.3  # Overbought -> Bearish
                
        # MACD Logic
        macd = row.get('macd_hist', 0)
        if pd.notna(macd):
            if macd > 0:
                score += 0.2
            elif macd < 0:
                score -= 0.2
                
        # Moving Average Crossover (SMA 20 vs SMA 50)
        sma_20 = row.get('sma_20')
        sma_50 = row.get('sma_50')
        close = row.get('close')
        if pd.notna(sma_20) and pd.notna(sma_50) and pd.notna(close):
            if sma_20 > sma_50 and close > sma_20:
                score += 0.3
            elif sma_20 < sma_50 and close < sma_20:
                score -= 0.3
                
        # Normalize score to [-1.0, 1.0] range
        score = max(-1.0, min(1.0, score))
        return score
        
    def map_sentiment_to_score(self, sentiment_label: str) -> float:
        if sentiment_label.lower() == "positive":
            return 1.0
        elif sentiment_label.lower() == "negative":
            return -1.0
        return 0.0

    def calculate_unified_signal(
        self, 
        df_indicators: pd.DataFrame, 
        sentiment_label: str = "neutral"
    ) -> Dict[str, Any]:
        """
        Calculates the unified signal using the latest row in the OHLCV dataframe 
        and the provided recent sentiment label.
        """
        if df_indicators.empty:
            return {"error": "Empty dataframe"}
            
        latest_row = df_indicators.iloc[-1]
        
        tech_score = self.generate_technical_signal(latest_row)
        sent_score = self.map_sentiment_to_score(sentiment_label)
        
        unified_score = (tech_score * self.technical_weight) + (sent_score * self.sentiment_weight)
        
        # Determine human-readable action
        if unified_score >= 0.5:
            action = "STRONG_BUY"
        elif unified_score >= 0.15:
            action = "BUY"
        elif unified_score <= -0.5:
            action = "STRONG_SELL"
        elif unified_score <= -0.15:
            action = "SELL"
        else:
            action = "HOLD"
            
        return {
            "action": action,
            "unified_score": round(unified_score, 4),
            "technical_score": round(tech_score, 4),
            "sentiment_score": round(sent_score, 4),
            "close_price": float(latest_row.get("close", 0)),
            "timestamp": str(latest_row.name if latest_row.name else "latest")
        }
