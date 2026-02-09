"""
LIVE PREDICTOR: Real-Time 30-Min Direction Prediction
- Loads trained XGBoost model
- Generates features from live candle data
- Returns UP/DOWN probability with confidence
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime
from loguru import logger
from typing import Dict, Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))

from ml_models.feature_engineer import FeatureEngineer


class LivePredictor:
    """Real-time direction prediction using trained XGBoost model"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize predictor with trained model
        
        Args:
            model_path: Path to saved model (default: latest in models/)
        """
        self.fe = FeatureEngineer()
        self.model = None
        self.feature_cols = self.fe.get_feature_columns()
        
        # Load model
        if model_path is None:
            model_path = Path(__file__).parent.parent / "models" / "xgboost_direction_model.pkl"
        
        self.load_model(model_path)
    
    def load_model(self, model_path: Path):
        """Load trained model from disk"""
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}\nRun model_trainer.py first!")
        
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        logger.info(f"✓ Model loaded: {model_path}")
    
    def prepare_live_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare live candle data for prediction
        
        Args:
            df: DataFrame with OHLCV data (recent 50+ candles for indicators)
        
        Returns:
            DataFrame with features for latest candle
        """
        # Generate features
        df_features = self.fe.generate_all_features(df)
        
        # Return only the latest row (current candle)
        return df_features.iloc[[-1]]
    
    def predict_direction(self, df: pd.DataFrame) -> Dict:
        """
        Predict 30-min direction from live data
        
        Args:
            df: DataFrame with recent OHLCV candles (minimum 50)
        
        Returns:
            Dictionary with prediction results:
            {
                'direction': 'BUY' or 'SELL',
                'confidence': float (0-100),
                'up_probability': float (0-100),
                'down_probability': float (0-100),
                'timestamp': str,
                'action': 'BUY' | 'SELL' | 'WAIT'
            }
        """
        try:
            # Prepare features
            df_prepared = self.prepare_live_data(df)
            
            # Extract features
            X = df_prepared[self.feature_cols]
            
            # Predict (preserve column order, bypass feature name validation issues)
            prediction = self.model.predict(X, validate_features=False)[0]  # 0 or 1
            probabilities = self.model.predict_proba(X, validate_features=False)[0]  # [prob_down, prob_up]
            
            # Interpret results
            down_prob = probabilities[0] * 100
            up_prob = probabilities[1] * 100
            
            direction = "BUY" if prediction == 1 else "SELL"
            confidence = max(down_prob, up_prob)
            
            # Decision logic: Only trade if confidence > 60%
            if confidence >= 60:
                action = direction
            else:
                action = "WAIT"
            
            result = {
                'direction': direction,
                'confidence': round(confidence, 2),
                'up_probability': round(up_prob, 2),
                'down_probability': round(down_prob, 2),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'action': action
            }
            
            logger.info(f"Prediction: {direction} | Confidence: {confidence:.1f}% | Action: {action}")
            
            return result
        
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    def predict_from_current_candle(self, current_candle: Dict) -> Dict:
        """
        Predict from single candle dict (for integration with analyzer.py)
        
        Args:
            current_candle: Dict with keys: open, high, low, close, volume, timestamp
        
        Returns:
            Prediction dictionary
        """
        # Convert to DataFrame
        df = pd.DataFrame([current_candle])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        return self.predict_direction(df)


def main():
    """Test live prediction with recent data"""
    from ml_models.data_extractor import DataExtractor
    
    logger.info("="*70)
    logger.info("TESTING LIVE PREDICTION")
    logger.info("="*70)
    
    # Fetch recent data (last 5 days)
    extractor = DataExtractor()
    df = extractor.fetch_historical_data(days=5, interval=5)
    
    logger.info(f"Fetched {len(df)} recent candles")
    
    # Initialize predictor
    predictor = LivePredictor()
    
    # Test prediction on last 10 candles
    logger.info("\nPredicting direction for last 10 candles:")
    logger.info("="*70)
    
    for i in range(-10, 0):
        # Get candles up to this point
        df_subset = df.iloc[:i+len(df)]
        
        # Predict
        result = predictor.predict_direction(df_subset)
        
        # Show result
        timestamp = df.index[i].strftime("%Y-%m-%d %H:%M")
        actual_price = df.iloc[i]['close']
        
        print(f"{timestamp} | {result['direction']:4s} | Conf: {result['confidence']:5.1f}% | "
              f"UP: {result['up_probability']:5.1f}% | DOWN: {result['down_probability']:5.1f}% | "
              f"Action: {result['action']:4s} | Price: {actual_price:.2f}")
    
    logger.info("="*70)
    logger.info("✓ PREDICTION TEST COMPLETE")
    logger.info("="*70)


if __name__ == "__main__":
    main()
