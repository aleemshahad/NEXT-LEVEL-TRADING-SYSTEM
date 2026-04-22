from loguru import logger
from typing import Dict

class RiskManager:
    """Risk Management System"""
    
    def __init__(self, config: Dict):
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.02)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_drawdown = config.get('max_drawdown', 0.15)
        self.daily_pnl = 0.0
        self._session_start_balance = 0.0  # Set on first update

    def update_daily_pnl(self, current_balance: float):
        """FIX #2: Called every cycle from live_trading run loop to keep daily_pnl live."""
        if self._session_start_balance == 0.0:
            self._session_start_balance = current_balance
        self.daily_pnl = current_balance - self._session_start_balance
        
    def calculate_position_size(self, account_balance: float, entry_price: float, 
                              stop_loss: float, symbol: str) -> float:
        """Calculate optimal position size"""
        try:
            # Risk amount
            risk_amount = account_balance * self.max_risk_per_trade
            
            # Price difference
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                return 0.01  # Minimum position size
            
            # FIX #1: Correct asset class detection order (XAG was falling to forex branch)
            if 'XAG' in symbol:
                # Silver: ~50 USD/point per lot
                position_size = min(risk_amount / (price_diff * 50), 1.0)
            elif 'XAU' in symbol:
                # Gold: ~100 USD/point per lot
                position_size = min(risk_amount / (price_diff * 100), 0.5)
            elif 'BTC' in symbol or 'ETH' in symbol:
                # Crypto: small lot sizes
                position_size = min(risk_amount / (price_diff * 10), 0.1)
            else:
                # Forex pairs
                position_size = min(risk_amount / (price_diff * 100000), 1.0)
            
            # Round to valid lot size
            position_size = round(position_size, 2)
            
            # Ensure minimum and maximum limits
            return max(0.01, min(position_size, 1.0))
            
        except Exception as e:
            logger.error(f"Position size calculation error: {e}")
            return 0.01
    
    def check_risk_limits(self, account_balance: float, current_drawdown: float) -> bool:
        """Check if trading is allowed based on risk limits"""
        # Check daily loss limit
        if abs(self.daily_pnl) > account_balance * self.max_daily_loss:
            logger.warning("Daily loss limit reached")
            return False
            
        # Check maximum drawdown
        if current_drawdown > self.max_drawdown:
            logger.warning("Maximum drawdown limit reached")
            return False
            
        return True
