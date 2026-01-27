"""
Historical Level Detection & Analysis Script
==============================================
Detects support/resistance levels from 1-year daily data.
Identifies swings, clusters zones, calculates strength scores.
Outputs: data/levels_NIFTY.csv, data/levels_SENSEX.csv

Standalone execution: No dependencies on core signal generation.
Can be run monthly to refresh levels independently.

Usage:
  python scripts/compute_levels.py --symbol NIFTY --period 1y
  python scripts/compute_levels.py --symbol SENSEX --period 1y
"""

import pandas as pd
import numpy as np
import yfinance as yf
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from loguru import logger

# Setup logging
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<level>{time:YYYY-MM-DD HH:mm:ss}</level> | <level>{level: <8}</level> | {message}"
)


class HistoricalLevelDetector:
    """
    Detects historical support/resistance levels from daily OHLCV data.
    
    Algorithm:
    1. Fetch 1-year daily data
    2. Detect swing highs (local resistance) and swing lows (local support)
    3. Cluster nearby levels into zones
    4. Calculate touch counts and strength scores
    5. Identify special zones (MAJOR, ROUND, etc.)
    6. Export to CSV + metadata JSON
    """
    
    # Configuration constants
    SWING_LOOKBACK = 10  # Bars to left/right for swing detection
    CLUSTER_RADIUS = 100  # Points to merge nearby levels (NIFTY scale)
    MIN_TOUCHES = 2  # Minimum touches to count as valid level
    ROUND_INTERVAL = 500  # Psychological level intervals
    
    # Symbols and tickers
    SYMBOLS = {
        'NIFTY': '^NSEI',
        'SENSEX': '^BSESN'
    }
    
    def __init__(self, symbol='NIFTY', period='1y'):
        """
        Initialize detector.
        
        Args:
            symbol: 'NIFTY' or 'SENSEX'
            period: '1y' (1 year), '2y' (2 years), etc.
        """
        self.symbol = symbol
        self.period = period
        self.ticker = self.SYMBOLS.get(symbol, '^NSEI')
        self.data = None
        self.levels = []
        self.output_dir = Path('data')
        self.output_dir.mkdir(exist_ok=True)
    
    def fetch_data(self) -> pd.DataFrame:
        """Fetch 1-year daily OHLCV data from Yahoo Finance."""
        logger.info(f"Fetching {self.period} daily data for {self.symbol}...")
        try:
            df = yf.download(
                self.ticker,
                period=self.period,
                interval='1d',
                progress=False
            )
            df = df.dropna()
            logger.info(f"✓ Fetched {len(df)} candles ({df.index[0].date()} to {df.index[-1].date()})")
            return df
        except Exception as e:
            logger.error(f"✗ Failed to fetch data: {e}")
            raise
    
    def detect_swings(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """
        Detect swing highs (resistance) and swing lows (support).
        
        Criteria:
        - SWING HIGH: Current High > Previous N and Next N highs
        - SWING LOW: Current Low < Previous N and Next N lows
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            (swing_highs, swing_lows) as lists of prices
        """
        swing_highs = []
        swing_lows = []
        
        highs = df['High'].values
        lows = df['Low'].values
        
        lookback = self.SWING_LOOKBACK
        
        for i in range(lookback, len(df) - lookback):
            # Check for swing high (resistance)
            if highs[i] == max(highs[i - lookback:i + lookback + 1]):
                swing_highs.append((i, highs[i]))
            
            # Check for swing low (support)
            if lows[i] == min(lows[i - lookback:i + lookback + 1]):
                swing_lows.append((i, lows[i]))
        
        logger.info(f"  Detected {len(swing_highs)} swing highs, {len(swing_lows)} swing lows")
        return swing_highs, swing_lows
    
    def cluster_levels(self, levels: List[Tuple[int, float]]) -> List[float]:
        """
        Cluster nearby levels into zones.
        Merge levels within CLUSTER_RADIUS points.
        
        Args:
            levels: List of (bar_index, price) tuples
        
        Returns:
            List of clustered price levels (zone centers)
        """
        if not levels:
            return []
        
        # Sort by price
        sorted_levels = sorted(levels, key=lambda x: x[1])
        clusters = []
        current_cluster = [sorted_levels[0][1]]
        
        for _, price in sorted_levels[1:]:
            if abs(price - current_cluster[-1]) <= self.CLUSTER_RADIUS:
                current_cluster.append(price)
            else:
                # Save cluster center (mean)
                clusters.append(np.mean(current_cluster))
                current_cluster = [price]
        
        if current_cluster:
            clusters.append(np.mean(current_cluster))
        
        logger.info(f"  Clustered into {len(clusters)} zones (radius={self.CLUSTER_RADIUS})")
        return clusters
    
    def count_touches(self, df: pd.DataFrame, level: float, tolerance: float = 50) -> int:
        """
        Count how many bars touched but didn't break a level.
        
        Args:
            df: OHLCV DataFrame
            level: Price level to check
            tolerance: Proximity threshold
        
        Returns:
            Touch count
        """
        highs = df['High'].values
        lows = df['Low'].values
        
        touches = 0
        for i in range(len(df)):
            # Check if price touched level (within tolerance)
            if lows[i] <= level <= highs[i]:
                touches += 1
        
        return touches
    
    def calculate_strength(self, touches: int, max_touches: int, 
                          volume_factor: float = 1.0, 
                          recency_days: int = 10) -> float:
        """
        Calculate zone strength (0-1 scale).
        
        Formula:
        Strength = (touches / max_touches) * volume_factor * recency_factor
        
        Args:
            touches: Number of times price touched level
            max_touches: Maximum touches in dataset (for normalization)
            volume_factor: Volume-based multiplier (1.0 = normal)
            recency_days: Days since last touch
        
        Returns:
            Strength score (0-1)
        """
        # Ensure volume_factor is a scalar
        if hasattr(volume_factor, '__len__'):
            volume_factor = float(volume_factor) if len(volume_factor) > 0 else 1.0
        else:
            volume_factor = float(volume_factor)
        
        # Normalize by max touches
        touch_score = min(touches / max(max_touches, 5), 1.0)
        
        # Recency factor (recent touches = stronger)
        recency_factor = 1.0 / (1.0 + (recency_days / 30.0))
        
        strength = float(touch_score) * float(volume_factor) * float(recency_factor)
        return min(strength, 1.0)
    
    def get_last_touch_date(self, df: pd.DataFrame, level: float, 
                           tolerance: float = 50) -> str:
        """Get date of last time price touched a level."""
        highs = df['High'].values
        lows = df['Low'].values
        dates = df.index
        
        for i in range(len(df) - 1, -1, -1):
            if lows[i] <= level <= highs[i]:
                return dates[i].strftime('%Y-%m-%d')
        
        return df.index[-1].strftime('%Y-%m-%d')
    
    def get_avg_volume(self, df: pd.DataFrame, level: float, 
                       tolerance: float = 50) -> float:
        """Get average volume at a price level."""
        highs = df['High'].values
        lows = df['Low'].values
        volumes = df['Volume'].values
        
        level_volumes = []
        for i in range(len(df)):
            if lows[i] <= level <= highs[i]:
                level_volumes.append(volumes[i])
        
        return np.mean(level_volumes) if level_volumes else np.mean(volumes)
    
    def identify_zone_types(self, df: pd.DataFrame, 
                           swing_highs: List[float], 
                           swing_lows: List[float]) -> Dict[str, Dict]:
        """
        Identify special zone types (MAJOR, SWING, ROUND, etc.).
        
        Returns:
            Dict mapping price level to zone metadata
        """
        zones = {}
        
        # MAJOR_R and MAJOR_S (1-year high/low)
        major_high = float(df['High'].max())
        major_low = float(df['Low'].min())
        
        zones[major_high] = {'zone_name': 'MAJOR_R', 'type': 'Resistance', 'priority': 1}
        zones[major_low] = {'zone_name': 'MAJOR_S', 'type': 'Support', 'priority': 1}
        
        # Swing highs and lows
        for idx, price in enumerate(swing_highs[:5]):  # Top 5 swing highs
            price = float(price)
            zones[price] = {
                'zone_name': f'SWING_H_{idx+1}',
                'type': 'Swing_High',
                'priority': 2
            }
        
        for idx, price in enumerate(swing_lows[:5]):  # Top 5 swing lows
            price = float(price)
            zones[price] = {
                'zone_name': f'SWING_L_{idx+1}',
                'type': 'Swing_Low',
                'priority': 2
            }
        
        # Round numbers (psychological levels)
        round_base = int(float(df['Close'].iloc[0]) / self.ROUND_INTERVAL) * self.ROUND_INTERVAL
        for mult in range(-2, 3):
            round_level = round_base + (mult * self.ROUND_INTERVAL)
            if major_low <= round_level <= major_high:
                if round_level not in zones:
                    zones[round_level] = {
                        'zone_name': f'ROUND_{int(round_level)}',
                        'type': 'Psychological',
                        'priority': 3
                    }
        
        return zones
    
    def compute_levels(self) -> pd.DataFrame:
        """Main computation orchestrator."""
        logger.info(f"\n{'='*70}")
        logger.info(f"HISTORICAL LEVEL DETECTION: {self.symbol}")
        logger.info(f"{'='*70}\n")
        
        # Step 1: Fetch data
        df = self.fetch_data()
        self.data = df
        
        # Step 2: Detect swings
        logger.info("\n[1/6] Detecting swings...")
        swing_highs_raw, swing_lows_raw = self.detect_swings(df)
        
        # Step 3: Cluster
        logger.info("\n[2/6] Clustering levels...")
        swing_highs = self.cluster_levels(swing_highs_raw)
        swing_lows = self.cluster_levels(swing_lows_raw)
        
        all_levels = swing_highs + swing_lows
        
        # Step 4: Identify zone types
        logger.info("\n[3/6] Identifying zone types...")
        zone_types = self.identify_zone_types(df, swing_highs, swing_lows)
        
        # Step 5: Calculate touches and strength
        logger.info("\n[4/6] Calculating touches and strength...")
        max_touches = max(
            self.count_touches(df, level) for level in all_levels
        ) if all_levels else 1
        
        levels_data = []
        
        for level in all_levels:
            touches = self.count_touches(df, level)
            
            # Skip if too few touches
            if touches < self.MIN_TOUCHES:
                continue
            
            last_touch = self.get_last_touch_date(df, level)
            last_touch_date = datetime.strptime(last_touch, '%Y-%m-%d')
            recency_days = (datetime.now() - last_touch_date).days
            
            avg_volume = self.get_avg_volume(df, level)
            volume_factor = avg_volume / df['Volume'].mean()
            
            strength = self.calculate_strength(
                touches, max_touches, 
                volume_factor=volume_factor,
                recency_days=recency_days
            )
            
            # Get zone metadata
            zone_info = zone_types.get(level, {
                'zone_name': f'ZONE_{int(level)}',
                'type': 'Support_Resistance',
                'priority': 4
            })
            
            levels_data.append({
                'Symbol': self.symbol,
                'Zone_Name': zone_info.get('zone_name', f'ZONE_{int(level)}'),
                'Price': round(level, 2),
                'Strength': round(strength, 2),
                'Touches': int(touches),
                'LastTouch': last_touch,
                'AvgVolume': int(avg_volume),
                'Type': zone_info.get('type', 'Unknown'),
                'Date_Created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Sort by strength (descending)
        levels_df = pd.DataFrame(levels_data)
        levels_df = levels_df.sort_values('Strength', ascending=False).reset_index(drop=True)
        
        logger.info(f"  Detected {len(levels_df)} valid levels (min {self.MIN_TOUCHES} touches)")
        
        return levels_df
    
    def save_levels(self, levels_df: pd.DataFrame):
        """Save levels to CSV and metadata to JSON."""
        logger.info("\n[5/6] Saving levels...")
        
        # CSV output
        csv_path = self.output_dir / f'levels_{self.symbol}.csv'
        levels_df.to_csv(csv_path, index=False)
        logger.info(f"  ✓ CSV saved: {csv_path}")
        
        # Metadata JSON
        metadata = {
            'symbol': self.symbol,
            'data_start': self.data.index[0].strftime('%Y-%m-%d'),
            'data_end': self.data.index[-1].strftime('%Y-%m-%d'),
            'total_candles': len(self.data),
            'levels_count': len(levels_df),
            'computed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'config': {
                'swing_lookback': self.SWING_LOOKBACK,
                'cluster_radius': self.CLUSTER_RADIUS,
                'min_touches': self.MIN_TOUCHES,
                'round_interval': self.ROUND_INTERVAL
            }
        }
        
        meta_path = self.output_dir / f'levels_{self.symbol}_meta.json'
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"  ✓ Metadata saved: {meta_path}")
    
    def print_summary(self, levels_df: pd.DataFrame):
        """Print summary report."""
        logger.info("\n[6/6] Summary Report")
        logger.info("="*70)
        logger.info(f"\nTop 10 Levels by Strength:\n")
        
        summary_df = levels_df[['Zone_Name', 'Price', 'Strength', 'Touches', 'Type']].head(10)
        print(summary_df.to_string(index=False))
        
        logger.info(f"\n\nLevel Distribution by Type:")
        type_counts = levels_df['Type'].value_counts()
        for level_type, count in type_counts.items():
            logger.info(f"  {level_type}: {count}")
        
        logger.info(f"\nStrength Statistics:")
        logger.info(f"  Mean: {levels_df['Strength'].mean():.2f}")
        logger.info(f"  Min: {levels_df['Strength'].min():.2f}")
        logger.info(f"  Max: {levels_df['Strength'].max():.2f}")
        logger.info(f"  Median: {levels_df['Strength'].median():.2f}")
        
        logger.info("\n" + "="*70)
        logger.info(f"✓ Complete! {len(levels_df)} levels saved.\n")
    
    def run(self):
        """Execute full pipeline."""
        try:
            levels_df = self.compute_levels()
            self.save_levels(levels_df)
            self.print_summary(levels_df)
            return levels_df
        except Exception as e:
            logger.error(f"✗ Execution failed: {e}")
            raise


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Historical Level Detection for NIFTY/SENSEX'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='NIFTY',
        choices=['NIFTY', 'SENSEX'],
        help='Index symbol (default: NIFTY)'
    )
    parser.add_argument(
        '--period',
        type=str,
        default='1y',
        help='Data period (default: 1y). Examples: 1y, 2y, 6mo'
    )
    
    args = parser.parse_args()
    
    detector = HistoricalLevelDetector(symbol=args.symbol, period=args.period)
    detector.run()


if __name__ == '__main__':
    main()
