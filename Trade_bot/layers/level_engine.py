"""
LAYER 1: Level & Context Engine
WHERE TO TRADE - Proximity Monitor for Technical & Historical Levels

Responsibilities:
1. Load historical levels from CSV
2. Calculate daily CPR (Pivot, TC, BC) and R1-R4, S1-S4
3. Monitor LTP proximity to all levels
4. Flag when price enters tradeable zones
5. Provide level context for Layer 2 (signal engine)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

@dataclass
class Level:
    """Represents a trading level"""
    name: str
    price: float
    level_type: str  # 'historical', 'cpr', 'pivot', 'resistance', 'support'
    strength: float = 0.0  # 0-1 strength score
    touches: int = 0
    

class LevelType(Enum):
    """Level classification"""
    HISTORICAL = "historical"
    CPR_TC = "cpr_tc"
    CPR_PIVOT = "cpr_pivot"
    CPR_BC = "cpr_bc"
    RESISTANCE = "resistance"
    SUPPORT = "support"


class LevelContextEngine:
    """
    Layer 1: Proximity Monitor
    Detects when price is near technical or historical levels
    """
    
    def __init__(self, symbol: str = 'NIFTY', proximity_distance: float = 20.0):
        """
        Args:
            symbol: Trading symbol (NIFTY, SENSEX)
            proximity_distance: Distance in points to flag proximity (default 20pts)
        """
        self.symbol = symbol
        self.proximity_distance = proximity_distance
        
        self.historical_levels = []
        self.cpr_levels = {}
        self.pivot_levels = {}
        
        self.current_ltp = 0.0
        self.timestamp = None
        
        logger.info(f"Layer 1 initialized: {symbol} | Proximity: {proximity_distance}pts")
    
    def load_historical_levels(self, csv_path: str) -> bool:
        """
        Load historical levels from CSV file
        
        Args:
            csv_path: Path to historical_levels.csv
        
        Returns:
            True if successful
        """
        try:
            df = pd.read_csv(csv_path)
            
            self.historical_levels = []
            for _, row in df.iterrows():
                level = Level(
                    name=row.get('Zone_Name', 'UNKNOWN'),
                    price=float(row['Price']),
                    level_type=row.get('Type', 'historical'),
                    strength=float(row.get('Strength', 0)),
                    touches=int(row.get('Touches', 0))
                )
                self.historical_levels.append(level)
            
            logger.info(f"✓ Loaded {len(self.historical_levels)} historical levels from {csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error loading historical levels: {e}")
            return False
    
    def calculate_cpr(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        Calculate CPR (Central Pivot Range) for the day
        
        CPR Formula:
        - Pivot (P) = (High + Low + Close) / 3
        - Top Central (TC) = (High + Close) / 2
        - Bottom Central (BC) = (Low + Close) / 2
        - R1 = (2 * P) - Low
        - S1 = (2 * P) - High
        - R2/R3/R4 and S2/S3/S4 calculated accordingly
        
        Args:
            high: Previous day high
            low: Previous day low
            close: Previous day close
        
        Returns:
            Dictionary with CPR levels
        """
        pivot = (high + low + close) / 3
        tc = (high + close) / 2
        bc = (low + close) / 2
        
        r1 = (2 * pivot) - low
        s1 = (2 * pivot) - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)
        r4 = high + 3 * (pivot - low)
        s4 = low - 3 * (high - pivot)
        
        self.cpr_levels = {
            'pivot': pivot,
            'tc': tc,
            'bc': bc,
            'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4,
            's1': s1, 's2': s2, 's3': s3, 's4': s4
        }
        
        logger.debug(f"CPR Calculated - P:{pivot:.2f} TC:{tc:.2f} BC:{bc:.2f}")
        return self.cpr_levels
    
    def check_proximity(self, ltp: float) -> Dict:
        """
        Check if LTP is near any technical or historical level
        
        Args:
            ltp: Current Last Traded Price
        
        Returns:
            Dictionary with proximity analysis
        """
        self.current_ltp = ltp
        self.timestamp = datetime.now()
        
        proximity_events = {
            'in_proximity': False,
            'nearest_level': None,
            'distance_to_nearest': float('inf'),
            'all_near_levels': [],
            'level_type': None,
            'direction': None,  # 'above', 'below'
            'zone_type': None   # 'resistance', 'support'
        }
        
        # Check CPR proximity
        for level_name, level_price in self.cpr_levels.items():
            distance = abs(ltp - level_price)
            
            if distance <= self.proximity_distance:
                proximity_events['all_near_levels'].append({
                    'name': f'CPR_{level_name.upper()}',
                    'price': level_price,
                    'distance': distance,
                    'type': 'cpr'
                })
                proximity_events['in_proximity'] = True
        
        # Check historical levels proximity
        for level in self.historical_levels:
            distance = abs(ltp - level.price)
            
            if distance <= self.proximity_distance:
                proximity_events['all_near_levels'].append({
                    'name': level.name,
                    'price': level.price,
                    'distance': distance,
                    'type': 'historical',
                    'strength': level.strength,
                    'touches': level.touches
                })
                proximity_events['in_proximity'] = True
        
        # Find nearest level
        if proximity_events['all_near_levels']:
            nearest = min(proximity_events['all_near_levels'], 
                         key=lambda x: x['distance'])
            proximity_events['nearest_level'] = nearest['name']
            proximity_events['distance_to_nearest'] = nearest['distance']
            proximity_events['level_type'] = nearest['type']
            
            # Determine if price is above or below, and zone type
            if 'resistance' in nearest['name'].lower() or nearest['price'] > ltp:
                proximity_events['zone_type'] = 'resistance'
                proximity_events['direction'] = 'above'
            else:
                proximity_events['zone_type'] = 'support'
                proximity_events['direction'] = 'below'
        
        return proximity_events
    
    def get_level_context(self, ltp: float) -> Dict:
        """
        Get complete level context for trading decision
        
        Args:
            ltp: Current price
        
        Returns:
            Comprehensive level analysis
        """
        proximity = self.check_proximity(ltp)
        
        context = {
            'timestamp': self.timestamp,
            'ltp': ltp,
            'proximity': proximity,
            'cpr_zone': self._get_cpr_zone(ltp),
            'nearest_support': self._get_nearest_support(ltp),
            'nearest_resistance': self._get_nearest_resistance(ltp),
            'levels_summary': {
                'total_historical': len(self.historical_levels),
                'near_levels_count': len(proximity['all_near_levels'])
            }
        }
        
        return context
    
    def _get_cpr_zone(self, ltp: float) -> str:
        """Determine price position relative to CPR"""
        if not self.cpr_levels:
            return "no_cpr_data"
        
        if ltp > self.cpr_levels['tc']:
            return "above_cpr"
        elif ltp < self.cpr_levels['bc']:
            return "below_cpr"
        else:
            return "inside_cpr"
    
    def _get_nearest_support(self, ltp: float) -> Optional[Tuple[str, float, float]]:
        """Get nearest support level below LTP"""
        supports = [
            ('CPR_BC', self.cpr_levels.get('bc', 0)),
            ('S1', self.cpr_levels.get('s1', 0)),
            ('S2', self.cpr_levels.get('s2', 0)),
            ('S3', self.cpr_levels.get('s3', 0)),
            ('S4', self.cpr_levels.get('s4', 0))
        ]
        
        # Add historical supports
        for level in self.historical_levels:
            if level.price < ltp:
                supports.append((level.name, level.price))
        
        supports = [(name, price) for name, price in supports if price > 0 and price < ltp]
        
        if supports:
            nearest = max(supports, key=lambda x: x[1])
            distance = ltp - nearest[1]
            return (nearest[0], nearest[1], distance)
        
        return None
    
    def _get_nearest_resistance(self, ltp: float) -> Optional[Tuple[str, float, float]]:
        """Get nearest resistance level above LTP"""
        resistances = [
            ('CPR_TC', self.cpr_levels.get('tc', 0)),
            ('R1', self.cpr_levels.get('r1', 0)),
            ('R2', self.cpr_levels.get('r2', 0)),
            ('R3', self.cpr_levels.get('r3', 0)),
            ('R4', self.cpr_levels.get('r4', 0))
        ]
        
        # Add historical resistances
        for level in self.historical_levels:
            if level.price > ltp:
                resistances.append((level.name, level.price))
        
        resistances = [(name, price) for name, price in resistances if price > 0 and price > ltp]
        
        if resistances:
            nearest = min(resistances, key=lambda x: x[1])
            distance = nearest[1] - ltp
            return (nearest[0], nearest[1], distance)
        
        return None


# Test
if __name__ == "__main__":
    engine = LevelContextEngine('NIFTY', proximity_distance=25.0)
    
    # Load historical levels
    engine.load_historical_levels('data/levels_NIFTY.csv')
    
    # Simulate PDH, PDL, PDC (previous day data)
    pdt_high = 26104.20
    pdt_low = 25300.00
    pdt_close = 25650.00
    
    # Calculate CPR
    engine.calculate_cpr(pdt_high, pdt_low, pdt_close)
    
    # Test with current LTP
    test_ltp = 25690.00
    context = engine.get_level_context(test_ltp)
    
    print("\n" + "="*80)
    print("LAYER 1: LEVEL & CONTEXT ENGINE")
    print("="*80)
    print(f"\nCurrent LTP: {test_ltp:.2f}")
    print(f"Proximity: {context['proximity']['in_proximity']}")
    print(f"CPR Zone: {context['cpr_zone']}")
    print(f"Nearest Support: {context['nearest_support']}")
    print(f"Nearest Resistance: {context['nearest_resistance']}")
    
    if context['proximity']['all_near_levels']:
        print(f"\nNear Levels (within 25pts):")
        for level in context['proximity']['all_near_levels']:
            print(f"  {level['name']}: {level['price']:.2f} ({level['distance']:.1f}pts away)")
    
    print("\n" + "="*80)
