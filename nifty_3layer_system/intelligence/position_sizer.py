"""
Position sizer - enforces capital preservation rules.
Ensures no more than 2 trades/day and max daily loss of 900 rupees.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Tuple


class PositionSizer:
    """Manages position sizing and capital preservation."""

    def __init__(self, 
                 total_capital: float = 15000,
                 max_daily_loss: float = 900,
                 lot_size: int = 65,
                 db_path: str = 'data/trading_metrics.db'):
        self.total_capital = total_capital
        self.max_daily_loss = max_daily_loss
        self.lot_size = lot_size  # NIFTY lot
        self.risk_per_point = lot_size  # 65 rupees per point
        self.max_sl_points = max_daily_loss / self.risk_per_point  # 14 points
        self.max_trades_per_day = 2
        self.db_path = db_path
    
    def get_today_loss(self) -> Tuple[float, int]:
        """
        Query database for today's actual loss.
        
        Returns:
            (total_loss, trade_count)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date()
            
            # Sum actual losses from closed trades
            cursor.execute("""
                SELECT 
                    COUNT(*) as trade_count,
                    COALESCE(SUM(CASE WHEN sl_hit = 1 THEN risk_points * ? ELSE 0 END), 0) as total_loss
                FROM level_signals
                WHERE DATE(timestamp) = ?
                AND (target_hit = 1 OR sl_hit = 1)
            """, (self.risk_per_point, today.isoformat()))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return (float(result[1]), result[0])
            return (0.0, 0)
            
        except Exception as e:
            print(f"Error querying daily loss: {e}")
            return (0.0, 0)
    
    def can_take_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed based on capital constraints.
        
        Returns:
            (can_trade: bool, reason: str)
        """
        today_loss, trade_count = self.get_today_loss()
        
        # Check trade count
        if trade_count >= self.max_trades_per_day:
            return False, f"⛔ DAILY LIMIT: {trade_count}/{self.max_trades_per_day} trades used"
        
        # Check daily loss
        remaining_loss = self.max_daily_loss - today_loss
        if remaining_loss <= 0:
            return False, f"⛔ LOSS LIMIT: Daily loss {today_loss:.0f}/{self.max_daily_loss:.0f} rupees reached"
        
        # Check if SL fits in remaining loss
        max_possible_sl = remaining_loss / self.risk_per_point
        if max_possible_sl < 5:
            return False, f"⛔ INSUFFICIENT CAPITAL: Only {max_possible_sl:.0f} points left, need min 5"
        
        return True, f"✅ CAN TRADE: {self.max_trades_per_day - trade_count} slots left, ₹{remaining_loss:.0f} loss available"
    
    def validate_position_sizing(self, risk_points: float) -> Tuple[bool, str]:
        """
        Validate if calculated SL fits within capital constraints.
        
        Args:
            risk_points: SL distance in points
        
        Returns:
            (is_valid: bool, reason: str)
        """
        # Check against max allowed SL
        if risk_points > self.max_sl_points:
            return False, f"SL too large: {risk_points:.1f} points > {self.max_sl_points:.1f} max"
        
        # Check remaining loss capacity
        today_loss, _ = self.get_today_loss()
        remaining_loss = self.max_daily_loss - today_loss
        loss_if_hit = risk_points * self.risk_per_point
        
        if loss_if_hit > remaining_loss:
            return False, f"Would exceed daily loss limit (risk: ₹{loss_if_hit:.0f} > available: ₹{remaining_loss:.0f})"
        
        return True, f"✅ Position valid: {risk_points:.1f} pt SL = ₹{loss_if_hit:.0f} loss"
    
    def get_position_limits(self) -> Dict:
        """
        Get current position sizing limits.
        
        Returns:
        {
            'total_capital': 15000,
            'max_daily_loss': 900,
            'max_sl_points': 14,
            'risk_per_point': 65,
            'max_trades_per_day': 2,
            'today_loss': float,
            'today_trades': int,
            'remaining_loss': float,
            'remaining_trades': int,
            'remaining_sl_points': float
        }
        """
        today_loss, trade_count = self.get_today_loss()
        remaining_loss = self.max_daily_loss - today_loss
        
        return {
            'total_capital': self.total_capital,
            'max_daily_loss': self.max_daily_loss,
            'max_sl_points': self.max_sl_points,
            'risk_per_point': self.risk_per_point,
            'max_trades_per_day': self.max_trades_per_day,
            'today_loss': round(today_loss, 2),
            'today_trades': trade_count,
            'remaining_loss': round(remaining_loss, 2),
            'remaining_trades': self.max_trades_per_day - trade_count,
            'remaining_sl_points': round(remaining_loss / self.risk_per_point, 1)
        }
    
    def log_trade_outcome(self, 
                         signal_id: int,
                         direction: str,
                         entry: float,
                         exit: float,
                         target_hit: bool,
                         sl_hit: bool):
        """Update trade outcome in database (handled by level_tracker)."""
        # This is already handled by level_tracker.py
        # Just provided here for API consistency
        pass
