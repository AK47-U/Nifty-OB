"""
Validate signals against historical support/resistance levels
Makes sure entry/exit/SL are REALISTIC and near actual zones
"""

import pandas as pd
import numpy as np
from pathlib import Path

class LevelValidator:
    """Validate trading signals against historical levels"""
    
    def __init__(self, symbol='NIFTY'):
        self.symbol = symbol
        self.levels_df = None
        self.support_zones = []
        self.resistance_zones = []
        self.load_historical_levels()
    
    def load_historical_levels(self):
        """Load historical levels from CSV"""
        levels_file = Path(f'data/levels_{self.symbol}.csv')
        
        if not levels_file.exists():
            print(f"WARNING: Historical levels file not found: {levels_file}")
            return False
        
        try:
            self.levels_df = pd.read_csv(levels_file)
            
            # Separate support and resistance zones
            self.support_zones = self.levels_df[self.levels_df['Type'] == 'Swing_Low']['Price'].tolist()
            self.resistance_zones = self.levels_df[self.levels_df['Type'] == 'Swing_High']['Price'].tolist()
            
            print(f"Loaded {len(self.levels_df)} historical levels for {self.symbol}")
            print(f"  Support zones: {len(self.support_zones)}")
            print(f"  Resistance zones: {len(self.resistance_zones)}")
            return True
            
        except Exception as e:
            print(f"ERROR loading levels: {e}")
            return False
    
    def find_nearest_level(self, price, zone_type='any', max_distance=200):
        """Find nearest historical level to current price"""
        if zone_type == 'support':
            zones = self.support_zones
        elif zone_type == 'resistance':
            zones = self.resistance_zones
        else:
            zones = self.support_zones + self.resistance_zones
        
        if not zones:
            return None, None
        
        zones = np.array(zones)
        distances = np.abs(zones - price)
        nearest_idx = np.argmin(distances)
        nearest_distance = distances[nearest_idx]
        
        if nearest_distance <= max_distance:
            return zones[nearest_idx], nearest_distance
        return None, nearest_distance
    
    def validate_entry(self, entry_price, tolerance=100):
        """Check if entry is near a real support/resistance zone"""
        nearest_level, distance = self.find_nearest_level(entry_price, 'any', max_distance=tolerance)
        
        if nearest_level is not None:
            return True, nearest_level, distance
        return False, None, distance
    
    def validate_target(self, entry, target, option_type='put'):
        """Check if target aligns with historical levels"""
        # For PUT (down): target should be at/below a support
        # For CALL (up): target should be at/above a resistance
        
        if option_type.lower() == 'put':
            nearest_level, distance = self.find_nearest_level(target, 'support', max_distance=300)
        else:  # call
            nearest_level, distance = self.find_nearest_level(target, 'resistance', max_distance=300)
        
        if nearest_level is not None:
            return True, nearest_level, distance
        return False, None, distance
    
    def validate_signal(self, entry, sl, target1, target2, option_type='put'):
        """Complete signal validation"""
        validation = {
            'entry': {'valid': False, 'level': None, 'distance': None},
            'sl': {'valid': False, 'level': None, 'distance': None},
            'target1': {'valid': False, 'level': None, 'distance': None},
            'target2': {'valid': False, 'level': None, 'distance': None},
            'overall_valid': False,
            'issues': []
        }
        
        # Validate entry (must be near real zone)
        entry_valid, entry_level, entry_dist = self.validate_entry(entry, tolerance=100)
        validation['entry']['valid'] = entry_valid
        validation['entry']['level'] = entry_level
        validation['entry']['distance'] = entry_dist
        
        if not entry_valid:
            validation['issues'].append(f"Entry {entry:.2f} not near any historical level (closest: {entry_dist:.0f}pt away)")
        
        # Validate SL (should be away from current level)
        if option_type.lower() == 'put':
            # For PUT: SL is above entry, should not hit resistance immediately
            nearest_sl, sl_dist = self.find_nearest_level(sl, 'resistance', max_distance=200)
            validation['sl']['valid'] = sl_dist > 50  # Should be away from resistance
        else:
            # For CALL: SL is below entry, should not hit support immediately
            nearest_sl, sl_dist = self.find_nearest_level(sl, 'support', max_distance=200)
            validation['sl']['valid'] = sl_dist > 50
        
        validation['sl']['distance'] = sl_dist
        
        # Validate targets (should align with support/resistance)
        t1_valid, t1_level, t1_dist = self.validate_target(entry, target1, option_type)
        validation['target1']['valid'] = t1_valid
        validation['target1']['level'] = t1_level
        validation['target1']['distance'] = t1_dist
        
        if not t1_valid:
            validation['issues'].append(f"Target 1 ({target1:.2f}) not near historical level")
        
        t2_valid, t2_level, t2_dist = self.validate_target(entry, target2, option_type)
        validation['target2']['valid'] = t2_valid
        validation['target2']['level'] = t2_level
        validation['target2']['distance'] = t2_dist
        
        # Overall validity (entry and at least one target must be valid)
        validation['overall_valid'] = entry_valid and (t1_valid or t2_valid)
        
        return validation


if __name__ == "__main__":
    # Test
    validator = LevelValidator('NIFTY')
    
    # Test validation
    test_signal = {
        'entry': 25687.05,
        'sl': 25862.07,
        'target1': 25424.52,
        'target2': 25249.50,
        'option_type': 'put'
    }
    
    result = validator.validate_signal(
        test_signal['entry'],
        test_signal['sl'],
        test_signal['target1'],
        test_signal['target2'],
        test_signal['option_type']
    )
    
    print("\n" + "="*70)
    print("SIGNAL VALIDATION AGAINST HISTORICAL LEVELS")
    print("="*70)
    print(f"\nEntry: {test_signal['entry']:.2f}")
    level_str = f"{result['entry']['level']:.2f}" if result['entry']['level'] else 'NO'
    print(f"  Near level: {level_str}")
    print(f"  Distance: {result['entry']['distance']:.0f} points")
    print(f"  Valid: {result['entry']['valid']}")
    
    print(f"\nTarget 1: {test_signal['target1']:.2f}")
    level_str = f"{result['target1']['level']:.2f}" if result['target1']['level'] else 'NO'
    print(f"  Near level: {level_str}")
    print(f"  Distance: {result['target1']['distance']:.0f} points")
    print(f"  Valid: {result['target1']['valid']}")
    
    print(f"\nTarget 2: {test_signal['target2']:.2f}")
    level_str = f"{result['target2']['level']:.2f}" if result['target2']['level'] else 'NO'
    print(f"  Near level: {level_str}")
    print(f"  Distance: {result['target2']['distance']:.0f} points")
    print(f"  Valid: {result['target2']['valid']}")
    
    print(f"\nOverall Valid: {result['overall_valid']}")
    
    if result['issues']:
        print("\nIssues:")
        for issue in result['issues']:
            print(f"  - {issue}")
    else:
        print("\nNo issues - Signal is REALISTIC!")
