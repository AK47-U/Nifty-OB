"""
Entry quality filter - checks if entry price is near key support/resistance levels.
Prevents poor entry quality signals that lead to quick SL hits.
"""

import pandas as pd
from typing import Tuple, Dict


class EntryQualityFilter:
    """Validates if signal entry is at good quality level."""

    def __init__(self):
        self.support_resistance_period = 20  # 20 candles = ~100 min (5-min candles)
        
    def get_support_resistance_levels(self, candles: list) -> Dict[str, float]:
        """
        Calculate support and resistance levels from last 20 5-min candles.
        
        Returns:
        {
            'resistance': float,
            'support': float,
            'midpoint': float,
            'range': float
        }
        """
        try:
            if not candles or len(candles) < self.support_resistance_period:
                return None
            
            df = pd.DataFrame(candles)
            df['high'] = df['high_price'].astype(float)
            df['low'] = df['low_price'].astype(float)
            df['close'] = df['close_price'].astype(float)
            
            # Get last 20 candles
            recent = df.tail(self.support_resistance_period)
            
            resistance = recent['high'].max()
            support = recent['low'].min()
            midpoint = (resistance + support) / 2
            range_size = resistance - support
            
            return {
                'resistance': round(resistance, 2),
                'support': round(support, 2),
                'midpoint': round(midpoint, 2),
                'range': round(range_size, 2)
            }
        except Exception as e:
            return None
    
    def evaluate_entry_quality(self, 
                              current_price: float, 
                              signal_direction: str,
                              sr_levels: Dict) -> dict:
        """
        Check if entry price is at good quality location.
        
        Returns:
        {
            'quality': 'GOOD' | 'FAIR' | 'POOR',
            'distance_to_support': float,  # For BUY
            'distance_to_resistance': float,  # For SELL
            'is_at_threshold': bool,
            'reason': str
        }
        """
        if sr_levels is None:
            return {
                'quality': 'FAIR',
                'distance_to_support': 0,
                'distance_to_resistance': 0,
                'is_at_threshold': False,
                'reason': 'SR levels unavailable'
            }
        
        support = sr_levels['support']
        resistance = sr_levels['resistance']
        midpoint = sr_levels['midpoint']
        range_size = sr_levels['range']
        
        # Define threshold as 20% from support/resistance
        threshold = range_size * 0.20
        
        if signal_direction == 'UP':
            # For BUY: should be near support
            dist_to_support = current_price - support
            
            if dist_to_support <= threshold:
                quality = 'GOOD'
                reason = f'Near support (distance: {dist_to_support:.2f})'
            elif dist_to_support <= threshold * 1.5:
                quality = 'FAIR'
                reason = f'Slightly above support (distance: {dist_to_support:.2f})'
            else:
                quality = 'POOR'
                reason = f'Far from support (distance: {dist_to_support:.2f}), risky entry'
            
            return {
                'quality': quality,
                'distance_to_support': round(dist_to_support, 2),
                'distance_to_resistance': 0,
                'is_at_threshold': dist_to_support <= threshold,
                'reason': reason
            }
        
        else:  # signal_direction == 'DOWN'
            # For SELL: should be near resistance
            dist_to_resistance = resistance - current_price
            
            if dist_to_resistance <= threshold:
                quality = 'GOOD'
                reason = f'Near resistance (distance: {dist_to_resistance:.2f})'
            elif dist_to_resistance <= threshold * 1.5:
                quality = 'FAIR'
                reason = f'Slightly below resistance (distance: {dist_to_resistance:.2f})'
            else:
                quality = 'POOR'
                reason = f'Far from resistance (distance: {dist_to_resistance:.2f}), risky entry'
            
            return {
                'quality': quality,
                'distance_to_support': 0,
                'distance_to_resistance': round(dist_to_resistance, 2),
                'is_at_threshold': dist_to_resistance <= threshold,
                'reason': reason
            }
    
    def is_quality_acceptable(self, entry_quality: dict) -> bool:
        """
        Determine if entry quality passes filter.
        Requires at least FAIR quality.
        """
        quality = entry_quality.get('quality', 'POOR')
        return quality in ['GOOD', 'FAIR']
