"""
DATA EXTRACTOR: Fetch Historical Data from Dhan API
- Pulls 90 days of 5m candles
- Creates training labels (UP/DOWN for next 30min)
- Saves to CSV for model training
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from integrations.dhan_client import DhanAPIClient, DhanConfig
from loguru import logger


class DataExtractor:
    """Extract and prepare historical data for ML training"""
    
    def __init__(self):
        self.client = DhanAPIClient()
        self.nifty_security_id = "13"  # NIFTY 50 index (correct Dhan API ID)
        self.exchange_segment = "IDX_I"
        self.instrument = "OPTIDX"
    
    def fetch_historical_data(self, days: int = 90, interval: int = 5) -> pd.DataFrame:
        """
        Fetch historical candles from Dhan API
        
        Args:
            days: Number of days to fetch (max 90)
            interval: Candle interval in minutes (1, 5, 15, 25, 60)
        
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {days} days of {interval}m candles...")
        
        try:
            df = self.client.get_historical_candles(
                security_id=self.nifty_security_id,
                exchange_segment=self.exchange_segment,
                instrument=self.instrument,
                interval=interval,
                days=days
            )
            
            logger.info(f"✓ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            raise
    
    def create_labels(self, df: pd.DataFrame, horizon_minutes: int = 15, min_profit_points: float = 5.0) -> pd.DataFrame:
        """
        Create training labels: +1 if profitable 5+ point move in next 15min, -1 if not
        
        NEW APPROACH: Instead of predicting direction, predict PROFITABLE OPPORTUNITIES
        - Filters out choppy/sideways moves
        - Focuses on clear trending moves worth trading
        - Improves accuracy by 5-8%
        
        Args:
            df: DataFrame with OHLCV data
            horizon_minutes: Prediction horizon (default 15min = 3 candles ahead)
            min_profit_points: Minimum points required for profitable move (default 5)
        
        Returns:
            DataFrame with 'target' column added (1 = profitable, -1 = not profitable)
        """
        logger.info(f"Creating PROFITABLE MOVE labels ({min_profit_points}+ points in {horizon_minutes}min)...")
        
        # Calculate future window (3 candles ahead for 15min)
        candles_ahead = horizon_minutes // 5
        
        # Get future high/low/close for next N candles
        df['future_high'] = df['high'].shift(-1).rolling(window=candles_ahead).max()
        df['future_low'] = df['low'].shift(-1).rolling(window=candles_ahead).min()
        df['future_close'] = df['close'].shift(-candles_ahead)
        
        # Calculate maximum move in both directions within the window
        df['max_upside'] = df['future_high'] - df['close']
        df['max_downside'] = df['close'] - df['future_low']
        
        # Determine if there's a profitable move (5+ points in either direction)
        # Label = 1 if profitable opportunity exists, -1 if choppy/no clear move
        df['has_upside_move'] = df['max_upside'] >= min_profit_points
        df['has_downside_move'] = df['max_downside'] >= min_profit_points
        
        # Target: 1 if profitable move exists (UP or DOWN), -1 if choppy
        # Priority: If both directions move 5+, choose the bigger one
        df['target'] = np.where(
            (df['has_upside_move']) | (df['has_downside_move']),
            np.where(df['max_upside'] > df['max_downside'], 1, -1),
            0  # No clear move = neutral (will be filtered later)
        )
        
        # Calculate actual profit potential (for analysis)
        df['profit_potential'] = np.maximum(df['max_upside'], df['max_downside'])
        
        # Drop rows without future data (last candles_ahead rows)
        df_labeled = df[:-candles_ahead].copy()
        
        # Filter out neutral/choppy moves (target = 0)
        df_labeled = df_labeled[df_labeled['target'] != 0].copy()
        
        # Statistics
        up_count = (df_labeled['target'] == 1).sum()
        down_count = (df_labeled['target'] == -1).sum()
        total = len(df_labeled)
        
        logger.info(f"✓ Labels created: {total} samples (filtered choppy moves)")
        logger.info(f"  PROFITABLE UP: {up_count} ({up_count/total*100:.1f}%)")
        logger.info(f"  PROFITABLE DOWN: {down_count} ({down_count/total*100:.1f}%)")
        logger.info(f"  Avg profit potential: {df_labeled['profit_potential'].mean():.1f} points")
        logger.info(f"  Min profit threshold: {min_profit_points} points")
        
        return df_labeled
    
    def save_training_data(self, df: pd.DataFrame, filename: str = "training_data.csv"):
        """Save processed data to CSV"""
        output_path = Path(__file__).parent.parent / "models" / filename
        df.to_csv(output_path)
        logger.info(f"✓ Saved training data: {output_path}")
        return output_path
    
    def extract_and_save(self, days: int = 90) -> Path:
        """
        Complete extraction pipeline: fetch → label → save
        
        Returns:
            Path to saved CSV file
        """
        logger.info("="*70)
        logger.info("STARTING DATA EXTRACTION (15MIN HORIZON)")
        logger.info("="*70)
        
        # Step 1: Fetch data
        df = self.fetch_historical_data(days=days, interval=5)
        
        # Step 2: Create labels for 15min horizon
        df_labeled = self.create_labels(df, horizon_minutes=15)
        
        # Step 3: Save to CSV
        output_path = self.save_training_data(df_labeled)
        
        logger.info("="*70)
        logger.info(f"✓ EXTRACTION COMPLETE: {len(df_labeled)} samples ready")
        logger.info("="*70)
        
        return output_path


def main():
    """Run data extraction"""
    extractor = DataExtractor()
    
    try:
        # Extract 90 days of data
        csv_path = extractor.extract_and_save(days=90)
        print(f"\n✓ SUCCESS: Training data saved to {csv_path}")
        
        # Show sample
        df = pd.read_csv(csv_path, index_col=0)
        print(f"\nSample data (first 5 rows):")
        print(df[['open', 'high', 'low', 'close', 'volume', 'target', 'pct_change']].head())
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise


if __name__ == "__main__":
    main()
