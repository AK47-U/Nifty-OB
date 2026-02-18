"""
FEATURE ENGINEER: Create ML Features from OHLCV Data
- Technical indicators (RSI, MACD, Bollinger Bands, ATR)
- Price momentum and volume features
- Time-based features (hour, day of week)
- ~25-30 features optimized for XGBoost
"""

import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
import sys
sys.path.append(str(Path(__file__).parent.parent))

from indicators.technical import TechnicalIndicators


class FeatureEngineer:
    """Generate ML features from raw OHLCV data"""
    
    def __init__(self):
        self.ti = TechnicalIndicators()
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate core technical indicators"""
        # logger.info("Calculating technical indicators...")
        
        # RSI indicators
        df['rsi'] = self.ti.calculate_rsi(df['close'], period=14)
        df['rsi_5'] = self.ti.calculate_rsi(df['close'], period=5)
        df['rsi_21'] = self.ti.calculate_rsi(df['close'], period=21)
        
        # Moving averages
        df['ema_5'] = self.ti.calculate_ema(df['close'], period=5)
        df['ema_20'] = self.ti.calculate_ema(df['close'], period=20)
        df['ema_50'] = self.ti.calculate_ema(df['close'], period=50)
        df['ema_200'] = self.ti.calculate_ema(df['close'], period=200)
        
        # VWAP (Volume Weighted Average Price)
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['dist_vwap'] = ((df['close'] - df['vwap']) / df['close']) * 100
        
        # MACD
        macd_data = self.ti.calculate_macd(df['close'])
        df['macd'] = macd_data['MACD']
        df['macd_signal'] = macd_data['Signal']
        df['macd_histogram'] = macd_data['Histogram']
        
        # Bollinger Bands (manual calculation)
        bb_period = 20
        bb_std = 2
        df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
        bb_std_dev = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * bb_std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * bb_std_dev)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_middle'] + 1e-10)
        
        # ATR (volatility) - need to match column names
        df_temp = df.rename(columns={'high': 'High', 'low': 'Low', 'close': 'Close'})
        df['atr'] = self.ti.calculate_atr(df_temp, period=14)
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        # logger.info("✓ Technical indicators calculated")
        return df
    
    def calculate_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price-based features"""
        # logger.info("Calculating price features...")
        
        # Price position relative to range
        df['high_low_range'] = df['high'] - df['low']
        df['close_position'] = (df['close'] - df['low']) / (df['high_low_range'] + 1e-10)
        
        # Price momentum
        df['price_change'] = df['close'].pct_change()
        df['price_change_5'] = df['close'].pct_change(periods=5)
        df['price_change_10'] = df['close'].pct_change(periods=10)
        
        # Rate of change
        df['roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
        df['roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100
        
        # Distance from EMAs (percentage)
        df['dist_ema5'] = ((df['close'] - df['ema_5']) / df['close']) * 100
        df['dist_ema20'] = ((df['close'] - df['ema_20']) / df['close']) * 100
        df['dist_ema50'] = ((df['close'] - df['ema_50']) / df['close']) * 100
        df['dist_ema200'] = ((df['close'] - df['ema_200']) / df['close']) * 100
        
        # EMA alignment (is trend aligned?)
        df['ema_alignment'] = np.where(
            (df['ema_5'] > df['ema_20']) & (df['ema_20'] > df['ema_50']), 1,
            np.where((df['ema_5'] < df['ema_20']) & (df['ema_20'] < df['ema_50']), -1, 0)
        )

        # Macro baseline trend regime (EMA200)
        df['trend_regime'] = np.where(df['close'] >= df['ema_200'], 1, -1)
        
        # logger.info("✓ Price features calculated")
        return df
    
    def calculate_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volume-based features"""
        # logger.info("Calculating volume features...")
        
        # Volume moving averages
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        
        # Volume ratio (current vs average)
        df['volume_ratio'] = df['volume'] / (df['volume_ma20'] + 1)
        
        # Volume change
        df['volume_change'] = df['volume'].pct_change()

        # Volume Z-score (volume drift)
        vol_mean = df['volume'].rolling(window=20).mean()
        vol_std = df['volume'].rolling(window=20).std()
        df['volume_zscore'] = (df['volume'] - vol_mean) / (vol_std + 1e-10)
        df['volume_zscore_ma5'] = df['volume_zscore'].rolling(window=5).mean()
        df['volume_drift'] = df['volume_zscore'] * df['price_change'].fillna(0)
        
        # Price-volume correlation
        df['pv_correlation'] = df['close'].rolling(window=20).corr(df['volume'])
        
        # logger.info("✓ Volume features calculated")
        return df
    
    def calculate_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Time-based features (market hour, day of week)"""
        # logger.info("Calculating time features...")
        
        # Ensure timestamp is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Hour of day (9-15 for market hours)
        df['hour'] = df.index.hour
        
        # Minute of hour (0, 5, 10, 15, ...)
        df['minute'] = df.index.minute
        
        # Day of week (0=Monday, 4=Friday)
        df['day_of_week'] = df.index.dayofweek
        
        # Market phase (0=opening, 1=mid, 2=closing)
        df['market_phase'] = np.where(df['hour'] < 11, 0,
                                       np.where(df['hour'] < 14, 1, 2))
        
        # logger.info("✓ Time features calculated")
        return df
    
    def calculate_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volatility regime features"""
        # logger.info("Calculating volatility features...")
        
        # Rolling standard deviation
        df['volatility_5'] = df['close'].pct_change().rolling(window=5).std() * 100
        df['volatility_20'] = df['close'].pct_change().rolling(window=20).std() * 100
        
        # Volatility ratio (recent vs historical)
        df['volatility_ratio'] = df['volatility_5'] / (df['volatility_20'] + 1e-10)
        
        # Garman-Klass Volatility (intraday volatility measure)
        # More efficient than close-to-close, uses OHLC data
        df['gk_log_hl'] = np.log(df['high'] / df['low'])
        df['gk_log_co'] = np.log(df['close'] / df['open'])
        df['gk_vol'] = (0.5 * (df['gk_log_hl'] ** 2) - (2 * np.log(2) - 1) * (df['gk_log_co'] ** 2)).rolling(20).mean()
        df['gk_vol'] = np.sqrt(df['gk_vol']) * 100
        
        # Parkinson Volatility (uses high-low range)
        df['parkinson_vol'] = (np.log(df['high'] / df['low']) ** 2) / (4 * np.log(2))
        df['parkinson_vol'] = np.sqrt(df['parkinson_vol'].rolling(20).mean()) * 100
        
        # VIX-like indicator (volatility of volatility)
        df['vol_of_vol'] = df['volatility_5'].rolling(20).std()
        
        # logger.info("✓ Volatility features calculated")
        return df
    
    def calculate_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Market microstructure features (order flow, tick direction)"""
        # logger.info("Calculating market microstructure features...")
        
        # Tick direction (up tick = 1, down tick = -1)
        df['tick_direction'] = np.where(df['close'] > df['close'].shift(1), 1,
                                        np.where(df['close'] < df['close'].shift(1), -1, 0))
        
        # Up tick count in last 20 candles
        df['up_ticks_20'] = df['tick_direction'].rolling(20).apply(lambda x: (x == 1).sum(), raw=True)
        
        # Order flow imbalance (buy pressure vs sell pressure)
        # Buy pressure: volume on up moves, Sell pressure: volume on down moves
        df['buy_volume'] = np.where(df['tick_direction'] > 0, df['volume'], 0)
        df['sell_volume'] = np.where(df['tick_direction'] < 0, df['volume'], 0)
        
        df['buy_volume_ma'] = df['buy_volume'].rolling(20).mean()
        df['sell_volume_ma'] = df['sell_volume'].rolling(20).mean()
        
        # Order flow imbalance ratio
        df['order_flow_imbalance'] = (df['buy_volume_ma'] - df['sell_volume_ma']) / (df['buy_volume_ma'] + df['sell_volume_ma'] + 1)
        
        # Volume weighted tick direction
        df['vwtd'] = (df['volume'] * df['tick_direction']).rolling(20).mean() / (df['volume'].rolling(20).mean() + 1)
        
        # Bid-ask spread proxy (using high-low range as proxy)
        df['spread_proxy'] = ((df['high'] - df['low']) / df['close'] * 10000).rolling(5).mean()
        
        # logger.info("✓ Market microstructure features calculated")
        return df
    
    def calculate_support_resistance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Support/Resistance level features"""
        # logger.info("Calculating support/resistance features...")
        
        # Calculate support and resistance from last 20 candles
        window = 20
        df['resistance_20'] = df['high'].rolling(window).max()
        df['support_20'] = df['low'].rolling(window).min()
        df['midpoint_20'] = (df['resistance_20'] + df['support_20']) / 2
        
        # Distance to support/resistance (percentage)
        df['dist_to_resistance'] = ((df['resistance_20'] - df['close']) / df['close']) * 100
        df['dist_to_support'] = ((df['close'] - df['support_20']) / df['close']) * 100
        
        # How many times has price touched support/resistance in last 20 candles
        df['resistance_touches'] = ((df['high'] >= df['resistance_20'] * 0.99).rolling(20).sum())
        df['support_touches'] = ((df['low'] <= df['support_20'] * 1.01).rolling(20).sum())
        
        # Price position within support-resistance range (0-1)
        df['price_position_in_range'] = (df['close'] - df['support_20']) / (df['resistance_20'] - df['support_20'] + 1e-10)
        
        # Is price near support or resistance? (within 0.5%)
        df['near_resistance'] = (df['resistance_20'] - df['close']) / df['close'] < 0.005
        df['near_support'] = (df['close'] - df['support_20']) / df['close'] < 0.005
        
        # CPR (Central Pivot Range) - POWERFUL FOR INTRADAY SCALPING
        # Uses previous day's high, low, close
        df['pivot'] = (df['high'] + df['low'] + df['close']) / 3
        df['cpr_tc'] = ((df['high'] + df['low']) / 2) + (df['pivot'] - (df['high'] + df['low']) / 2)
        df['cpr_bc'] = ((df['high'] + df['low']) / 2) - (df['pivot'] - (df['high'] + df['low']) / 2)
        df['cpr_width'] = df['cpr_tc'] - df['cpr_bc']
        
        # Distance from CPR levels
        df['dist_to_cpr_tc'] = ((df['cpr_tc'] - df['close']) / df['close']) * 100
        df['dist_to_cpr_bc'] = ((df['close'] - df['cpr_bc']) / df['close']) * 100
        df['cpr_midpoint'] = (df['cpr_tc'] + df['cpr_bc']) / 2
        df['dist_to_cpr_pivot'] = ((df['cpr_midpoint'] - df['close']) / df['close']) * 100
        
        # Is price above, below, or inside CPR?
        df['above_cpr'] = (df['close'] > df['cpr_tc']).astype(int)
        df['below_cpr'] = (df['close'] < df['cpr_bc']).astype(int)
        df['inside_cpr'] = ((df['close'] >= df['cpr_bc']) & (df['close'] <= df['cpr_tc'])).astype(int)
        
        # Proximity to CPR (0-1, where 1 is exactly at CPR)
        df['cpr_proximity'] = 1 - (np.abs(df['close'] - df['cpr_midpoint']) / (df['cpr_width'] / 2 + 1e-10))
        df['cpr_proximity'] = np.clip(df['cpr_proximity'], 0, 1)
        
        # logger.info("✓ Support/resistance features calculated")
        return df
    
    def calculate_gap_open_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gap and open price features"""
        # logger.info("Calculating gap and open price features...")
        
        # Gap from previous close (open of current - close of previous)
        df['gap'] = ((df['open'] - df['close'].shift(1)) / df['close'].shift(1)) * 100
        
        # Filled gap or not (current close vs gap level)
        df['gap_filled'] = np.where(
            ((df['open'] > df['close'].shift(1)) & (df['close'] < df['close'].shift(1))) |
            ((df['open'] < df['close'].shift(1)) & (df['close'] > df['close'].shift(1))),
            1, 0
        )
        
        # Current candle: distance from open
        df['price_from_open'] = ((df['close'] - df['open']) / df['open']) * 100
        
        # Is close above or below open? (bullish or bearish candle)
        df['bullish_candle'] = np.where(df['close'] > df['open'], 1, -1)
        
        # Open price relative to range
        df['open_price_position'] = (df['open'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        
        # Running distance from day's open (need to track day boundaries)
        df['time_index'] = range(len(df))
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        df['day'] = df.index.date
        # Find first open of each day
        day_opens = df.groupby('day')['open'].first()
        df['day_open'] = df['day'].map(day_opens)
        df['dist_from_day_open'] = ((df['close'] - df['day_open']) / df['day_open']) * 100
        
        # logger.info("✓ Gap and open features calculated")
        return df
    
    def calculate_options_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Synthetic options-based features (derived from price action & volatility)"""
        # logger.info("Calculating options-derived features...")
        
        # Make sure volatility features exist
        if 'volatility_20' not in df.columns:
            df['volatility_20'] = df['close'].pct_change().rolling(window=20).std() * 100
        
        # Simulated PCR (Put-Call Ratio) from price volatility
        # High volatility = more put buying = higher PCR
        df['simulated_pcr'] = (1 + (df['volatility_20'].fillna(0) / 100)).fillna(1)
        
        # Simulated OI skew (based on momentum)
        # Bullish momentum = Call heavy, Bearish = Put heavy
        df['momentum_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100
        df['oi_skew'] = np.where(df['momentum_10'].fillna(0) > 0, 0.7, 1.3)
        
        # IV Skew (approximated from RSI)
        # Extreme RSI values suggest elevated IV
        df['iv_skew'] = np.where(
            (df['rsi'].fillna(50) > 70) | (df['rsi'].fillna(50) < 30),
            1.5,  # High IV
            1.0   # Normal IV
        )
        
        # Options sentiment indicator
        df['options_sentiment'] = (
            (1 - (df['simulated_pcr'] - 1) * 50) +
            ((df['rsi'].fillna(50) - 50) / 100) +
            np.clip(df['momentum_10'].fillna(0) / 100, -1, 1)
        ) / 3
        
        # Institutional activity proxy (volume spikes with price moves)
        df['inst_activity'] = ((df['volume'].rolling(5).std() / (df['volume_ma20'].fillna(df['volume'].mean()) + 1)) * 100).fillna(0)
        
        # logger.info("✓ Options-derived features calculated")
        return df
    
    def generate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate complete feature set"""
        # logger.info("="*70)
        # logger.info("GENERATING FEATURES (15MIN HORIZON + OPTIONS DATA)")
        # logger.info("="*70)
        
        # Make copy to avoid modifying original
        df = df.copy()
        
        # Calculate all feature groups
        df = self.calculate_technical_indicators(df)
        df = self.calculate_price_features(df)
        df = self.calculate_volume_features(df)
        df = self.calculate_time_features(df)
        df = self.calculate_volatility_features(df)
        df = self.calculate_microstructure_features(df)  # NEW
        df = self.calculate_support_resistance_features(df)  # NEW
        df = self.calculate_gap_open_features(df)  # NEW
        df = self.calculate_options_features(df)  # NEW: Options features
        
        # Drop NaN values from indicator calculations
        initial_rows = len(df)
        df = df.dropna()
        dropped_rows = initial_rows - len(df)
        
        # logger.info(f"✓ Dropped {dropped_rows} rows with NaN values")
        # logger.info(f"✓ Final dataset: {len(df)} rows")
        # logger.info("="*70)
        
        return df
    
    def get_feature_columns(self) -> list:
        """Return list of feature column names (excluding target)"""
        return [
            # Technical indicators
            'rsi', 'rsi_5', 'rsi_21',
            'macd', 'macd_signal', 'macd_histogram',
            'bb_width', 'atr_pct',
            
            # Price features
            'close_position', 'price_change', 'price_change_5', 'price_change_10',
            'roc_5', 'roc_10',
            'dist_ema5', 'dist_ema20', 'dist_ema50',
            'dist_ema200',
            'dist_vwap',
            'ema_alignment',
            'trend_regime',
            
            # Volume features
            'volume_ratio', 'volume_change', 'pv_correlation',
            'volume_zscore', 'volume_zscore_ma5', 'volume_drift',
            
            # Time features
            'hour', 'minute', 'day_of_week', 'market_phase',
            
            # Volatility features (ENHANCED)
            'volatility_5', 'volatility_20', 'volatility_ratio',
            'gk_vol', 'parkinson_vol', 'vol_of_vol',
            
            # Market Microstructure features (NEW)
            'up_ticks_20', 'order_flow_imbalance', 'vwtd', 'spread_proxy',
            
            # Support/Resistance features (ENHANCED WITH CPR)
            'dist_to_resistance', 'dist_to_support', 'resistance_touches', 
            'support_touches', 'price_position_in_range', 'near_resistance', 'near_support',
            'cpr_width', 'dist_to_cpr_tc', 'dist_to_cpr_bc', 'dist_to_cpr_pivot',
            'above_cpr', 'below_cpr', 'inside_cpr', 'cpr_proximity',
            
            # Gap & Open features (NEW)
            'gap', 'gap_filled', 'price_from_open', 'bullish_candle',
            'open_price_position', 'dist_from_day_open',
            
            # Options-derived features
            'simulated_pcr', 'oi_skew', 'iv_skew', 'options_sentiment', 'inst_activity'
        ]


def main():
    """Test feature generation"""
    from ml_models.data_extractor import DataExtractor
    
    logger.info("Testing feature generation...")
    
    # Load training data
    data_path = Path(__file__).parent.parent / "models" / "training_data.csv"
    
    if not data_path.exists():
        logger.info("Training data not found. Running extraction first...")
        extractor = DataExtractor()
        extractor.extract_and_save(days=90)
    
    # Load data
    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    logger.info(f"Loaded {len(df)} rows from {data_path}")
    
    # Generate features
    fe = FeatureEngineer()
    df_features = fe.generate_all_features(df)
    
    # Show feature summary
    feature_cols = fe.get_feature_columns()
    logger.info(f"\n✓ Generated {len(feature_cols)} features:")
    for feat in feature_cols:
        print(f"  - {feat}")
    
    # Save featured data
    output_path = Path(__file__).parent.parent / "models" / "featured_data.csv"
    df_features.to_csv(output_path)
    logger.info(f"\n✓ Saved featured data: {output_path}")
    
    # Show sample
    print(f"\nSample features (first 3 rows):")
    print(df_features[feature_cols[:5]].head(3))


if __name__ == "__main__":
    main()
