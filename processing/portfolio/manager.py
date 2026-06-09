import logging
from typing import Dict, Any
from execution.alpaca_broker import AlpacaBrokerConnector

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Handles portfolio state, risk management, and position sizing.
    Uses the broker connector to execute the logic.
    """
    def __init__(self, broker=None):
        self.broker = broker or AlpacaBrokerConnector()
        # Default risk per trade: 1% of total portfolio value
        self.max_risk_per_trade_pct = 0.01 

    async def get_account_summary(self) -> Dict[str, Any]:
        """Returns the current account balance and buying power."""
        return await self.broker.get_account()

    async def get_current_positions(self):
        """Returns current open positions."""
        return await self.broker.get_positions()

    def calculate_position_size(self, account_value: float, current_price: float, atr: float = None) -> int:
        """
        Calculate how many shares to buy based on risk.
        If ATR is provided, it uses Volatility-Based Position Sizing (e.g. Stop Loss = 2 * ATR).
        If no ATR, it defaults to allocating a fixed percentage of buying power.
        """
        if current_price <= 0:
            return 0
            
        risk_amount = account_value * self.max_risk_per_trade_pct
        
        if atr and atr > 0:
            # Stop loss distance is 2 * ATR
            stop_loss_dist = 2 * atr
            shares = int(risk_amount / stop_loss_dist)
        else:
            # Simplified sizing: just use the risk amount directly as capital allocated
            # (In reality, risk_amount is the amount we are willing to lose, not invest, 
            # but without a stop loss, we just allocate the risk_amount entirely)
            shares = int(risk_amount / current_price)
            
        return shares

    async def execute_trade(self, symbol: str, signal: str, current_price: float, atr: float = None) -> Dict[str, Any]:
        """
        High-level function to execute a trade based on a generated signal (BUY/SELL).
        """
        if signal not in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
            return {"status": "IGNORED", "message": f"Signal {signal} does not trigger execution"}

        account = await self.get_account_summary()
        if "error" in account:
            return {"status": "FAILED", "error": account["error"]}
            
        buying_power = float(account.get("buying_power", 0))
        portfolio_value = float(account.get("portfolio_value", 0))
        
        if signal in ["BUY", "STRONG_BUY"]:
            shares = self.calculate_position_size(portfolio_value, current_price, atr)
            cost = shares * current_price
            
            if shares <= 0:
                return {"status": "FAILED", "error": "Calculated position size is 0"}
                
            if cost > buying_power:
                # Adjust shares to max buying power
                shares = int(buying_power / current_price)
                if shares <= 0:
                    return {"status": "FAILED", "error": "Insufficient buying power"}
                    
            logger.info(f"Submitting BUY order for {shares} shares of {symbol}")
            order = await self.broker.submit_order(symbol, shares, "buy")
            return {"status": "SUCCESS", "action": "BUY", "shares": shares, "order": order}
            
        elif signal in ["SELL", "STRONG_SELL"]:
            # Check if we own it
            positions = await self.get_current_positions()
            owned_shares = 0
            for p in positions:
                if p.get("symbol") == symbol:
                    owned_shares = int(p.get("qty", 0))
                    break
                    
            if owned_shares <= 0:
                return {"status": "FAILED", "error": f"No open position for {symbol} to sell"}
                
            logger.info(f"Submitting SELL order for {owned_shares} shares of {symbol}")
            order = await self.broker.submit_order(symbol, owned_shares, "sell")
            return {"status": "SUCCESS", "action": "SELL", "shares": owned_shares, "order": order}

        return {"status": "UNKNOWN"}

    async def get_portfolio_history(self, period="1M", timeframe="1D") -> Dict[str, Any]:
        """Returns the portfolio performance history."""
        if hasattr(self.broker, "get_portfolio_history"):
            return await self.broker.get_portfolio_history(period, timeframe)
        return {"error": "Broker does not support portfolio history"}
