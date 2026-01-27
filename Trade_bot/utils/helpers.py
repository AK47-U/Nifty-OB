"""
Utility functions for the trading signal generator
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
from loguru import logger

def format_currency(amount: float, currency: str = "₹") -> str:
    """
    Format currency amounts with proper formatting
    
    Args:
        amount: Amount to format
        currency: Currency symbol
    
    Returns:
        Formatted currency string
    """
    return f"{currency}{amount:,.2f}"

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values
    
    Args:
        old_value: Previous value
        new_value: Current value
    
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def is_trading_day(date: datetime) -> bool:
    """
    Check if a given date is a trading day (Monday-Friday)
    
    Args:
        date: Date to check
    
    Returns:
        True if trading day, False otherwise
    """
    return date.weekday() < 5  # Monday=0, Sunday=6

def get_next_trading_day(date: datetime) -> datetime:
    """
    Get the next trading day from given date
    
    Args:
        date: Starting date
    
    Returns:
        Next trading day
    """
    next_day = date + timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day

def calculate_volatility(prices: List[float], period: int = 20) -> float:
    """
    Calculate price volatility
    
    Args:
        prices: List of prices
        period: Period for volatility calculation
    
    Returns:
        Annualized volatility
    """
    if len(prices) < period:
        return 0.0
    
    returns = []
    for i in range(1, len(prices)):
        return_val = (prices[i] - prices[i-1]) / prices[i-1]
        returns.append(return_val)
    
    # Calculate standard deviation of returns
    returns_std = np.std(returns[-period:])
    
    # Annualize (assuming 252 trading days)
    annualized_vol = returns_std * np.sqrt(252) * 100
    
    return annualized_vol

def save_signals_to_file(signals: Dict[str, Any], filename: str = None) -> str:
    """
    Save signals to JSON file
    
    Args:
        signals: Signal dictionary
        filename: Optional filename (auto-generated if None)
    
    Returns:
        Filename used
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"signals_{timestamp}.json"
    
    try:
        # Convert datetime objects to strings for JSON serialization
        signals_copy = json.loads(json.dumps(signals, default=str))
        
        with open(filename, 'w') as f:
            json.dump(signals_copy, f, indent=2)
        
        logger.info(f"Signals saved to {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error saving signals to file: {e}")
        return ""

def load_signals_from_file(filename: str) -> Optional[Dict[str, Any]]:
    """
    Load signals from JSON file
    
    Args:
        filename: File to load
    
    Returns:
        Signals dictionary or None if error
    """
    try:
        with open(filename, 'r') as f:
            signals = json.load(f)
        
        logger.info(f"Signals loaded from {filename}")
        return signals
        
    except Exception as e:
        logger.error(f"Error loading signals from file: {e}")
        return None

def create_summary_table(data: Dict[str, Any]) -> str:
    """
    Create a formatted summary table
    
    Args:
        data: Dictionary with data to display
    
    Returns:
        Formatted table string
    """
    table_lines = []
    table_lines.append("+" + "-" * 50 + "+")
    
    for key, value in data.items():
        key_str = str(key).replace('_', ' ').title()[:20]
        value_str = str(value)[:25]
        line = f"| {key_str:<20} | {value_str:<25} |"
        table_lines.append(line)
    
    table_lines.append("+" + "-" * 50 + "+")
    
    return "\n".join(table_lines)

def validate_signal_strength(strength: float) -> bool:
    """
    Validate signal strength is within acceptable range
    
    Args:
        strength: Signal strength value
    
    Returns:
        True if valid, False otherwise
    """
    return 0.0 <= strength <= 1.0

def filter_strong_signals(signals: Dict[str, Any], min_strength: float = 0.7) -> Dict[str, Any]:
    """
    Filter signals to only include strong ones
    
    Args:
        signals: Signal dictionary
        min_strength: Minimum strength threshold
    
    Returns:
        Filtered signals
    """
    filtered = signals.copy()
    
    signal_data = filtered.get('signals', {})
    
    # Filter call signals
    if 'call' in signal_data:
        call_strength = signal_data['call'].get('strength', 0)
        if call_strength < min_strength:
            signal_data['call']['action'] = 'hold'
    
    # Filter put signals
    if 'put' in signal_data:
        put_strength = signal_data['put'].get('strength', 0)
        if put_strength < min_strength:
            signal_data['put']['action'] = 'hold'
    
    return filtered

def calculate_risk_reward_ratio(entry_price: float, stop_loss: float, target: float) -> float:
    """
    Calculate risk-reward ratio for a trade
    
    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        target: Target price
    
    Returns:
        Risk-reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(target - entry_price)
    
    if risk == 0:
        return 0.0
    
    return reward / risk

def format_time_duration(seconds: int) -> str:
    """
    Format time duration in human-readable format
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

class PerformanceTracker:
    """
    Class to track and analyze performance metrics
    """
    
    def __init__(self):
        self.trades = []
        self.signals_history = []
    
    def add_trade(self, trade_data: Dict[str, Any]):
        """Add a trade to tracking"""
        trade_data['timestamp'] = datetime.now()
        self.trades.append(trade_data)
    
    def add_signal(self, signal_data: Dict[str, Any]):
        """Add a signal to history"""
        signal_data['timestamp'] = datetime.now()
        self.signals_history.append(signal_data)
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate from trades"""
        if not self.trades:
            return 0.0
        
        winning_trades = sum(1 for trade in self.trades if trade.get('pnl', 0) > 0)
        return (winning_trades / len(self.trades)) * 100
    
    def calculate_average_return(self) -> float:
        """Calculate average return per trade"""
        if not self.trades:
            return 0.0
        
        total_return = sum(trade.get('return_pct', 0) for trade in self.trades)
        return total_return / len(self.trades)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        return {
            'total_trades': len(self.trades),
            'total_signals': len(self.signals_history),
            'win_rate': self.calculate_win_rate(),
            'avg_return': self.calculate_average_return(),
            'last_trade': self.trades[-1]['timestamp'] if self.trades else None,
            'last_signal': self.signals_history[-1]['timestamp'] if self.signals_history else None
        }