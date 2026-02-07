"""
Real-time 15-minute trend analyzer for intraday direction detection.
Detects UP/DOWN/NEUTRAL trends to filter out counter-trend trade setups.
"""

import pandas as pd
from typing import Literal


class TrendAnalyzer:
    """Analyzes 15-min NIFTY trend to prevent counter-trend trading."""

    def __init__(self):
        self.fast_ema_period = 9
        self.slow_ema_period = 21
        
    def get_15min_trend(self, current_df=None) -> dict:
        """
        Detect trend direction from current price data.
        Uses EMA crossover on available 5-min candle data.
        
        Args:
            current_df: DataFrame with OHLC candle data
        
        Returns:
        {
            'trend': 'UP' | 'DOWN' | 'NEUTRAL',
            'strength': 0.0-1.0 (how strong the trend is),
            'fast_ema': float,
            'slow_ema': float,
            'last_close': float
        }
        """
        try:
            if current_df is None or len(current_df) < 21:
                return {
                    'trend': 'NEUTRAL',
                    'strength': 0.0,
                    'fast_ema': None,
                    'slow_ema': None,
                    'last_close': None,
                    'reason': 'Insufficient data'
                }
            
            # Use last 50 candles for trend
            df = current_df.tail(50).copy()
            
            # Get close prices
            if 'close' in df.columns:
                close_col = 'close'
            elif 'close_price' in df.columns:
                df['close'] = df['close_price'].astype(float)
                close_col = 'close'
            else:
                return {
                    'trend': 'NEUTRAL',
                    'strength': 0.0,
                    'fast_ema': None,
                    'slow_ema': None,
                    'last_close': None,
                    'reason': 'No close price column'
                }
            
            # Calculate EMAs
            df['fast_ema'] = df[close_col].ewm(span=self.fast_ema_period, adjust=False).mean()
            df['slow_ema'] = df[close_col].ewm(span=self.slow_ema_period, adjust=False).mean()
            
            fast_ema = df['fast_ema'].iloc[-1]
            slow_ema = df['slow_ema'].iloc[-1]
            last_close = df[close_col].iloc[-1]
            
            # Determine trend
            ema_diff = fast_ema - slow_ema
            ema_strength = abs(ema_diff) / slow_ema if slow_ema != 0 else 0
            
            if fast_ema > slow_ema and last_close > fast_ema:
                trend = 'UP'
                strength = min(ema_strength * 100, 1.0)
            elif fast_ema < slow_ema and last_close < fast_ema:
                trend = 'DOWN'
                strength = min(ema_strength * 100, 1.0)
            else:
                trend = 'NEUTRAL'
                strength = 0.0
            
            return {
                'trend': trend,
                'strength': strength,
                'fast_ema': round(fast_ema, 2),
                'slow_ema': round(slow_ema, 2),
                'last_close': round(last_close, 2),
                'signal_aligned': True,  # Will be checked against signal direction
                'reason': 'Real-time 15-min analysis'
            }
            
        except Exception as e:
            return {
                'trend': 'NEUTRAL',
                'strength': 0.0,
                'fast_ema': None,
                'slow_ema': None,
                'last_close': None,
                'signal_aligned': False,
                'reason': f'Error fetching 15-min trend: {str(e)}'
            }
    
    def is_aligned_with_trend(self, signal_direction: str, trend: dict) -> bool:
        """
        Check if signal direction aligns with current trend.
        
        Args:
            signal_direction: 'UP' | 'DOWN' (from model prediction)
            trend: dict from get_15min_trend()
        
        Returns:
            True if aligned, False otherwise
        """
        trend_type = trend.get('trend', 'NEUTRAL')
        
        if trend_type == 'NEUTRAL':
            # Neutral trend is always OK
            return True
        
        # Align signal with trend
        if signal_direction == 'UP' and trend_type == 'UP':
            return True
        elif signal_direction == 'DOWN' and trend_type == 'DOWN':
            return True
        
        return False
    
    def get_trend_strength_multiplier(self, trend: dict) -> float:
        """
        Get confidence multiplier based on trend strength.
        Strong trends = higher multiplier, weak trends = lower multiplier.
        
        Returns:
            0.5 (weak) to 1.0 (strong)
        """
        strength = trend.get('strength', 0.0)
        
        if strength > 0.8:
            return 1.0  # Very strong trend
        elif strength > 0.5:
            return 0.9  # Strong trend
        elif strength > 0.2:
            return 0.8  # Moderate trend
        else:
            return 0.6  # Weak/No trend
