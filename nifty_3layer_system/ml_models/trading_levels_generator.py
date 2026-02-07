"""
TRADING LEVELS GENERATOR: Convert ML Predictions to Actual Trading Setup
- Uses ML probability to calculate Level, Entry, Exit, SL
- IST timezone
- 15-30min forecast
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from loguru import logger
from typing import Dict, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from ml_models.live_predictor import LivePredictor


class TradingLevelsGenerator:
    """Convert ML predictions into actual trading levels"""
    
    def __init__(self, atr_multiplier: float = 1.5, buffer_pct: float = 0.05):
        """
        Initialize levels generator
        
        Args:
            atr_multiplier: How many ATRs for SL (1.5 ATR = conservative)
            buffer_pct: Buffer % for entry (0.05 = 0.05% above/below current)
        """
        self.predictor = LivePredictor()
        self.atr_multiplier = atr_multiplier
        self.buffer_pct = buffer_pct
        self.ist = pytz.timezone('Asia/Kolkata')
    
    def get_ist_time(self) -> str:
        """Get current time in IST"""
        ist_now = datetime.now(self.ist)
        return ist_now.strftime("%Y-%m-%d %H:%M:%S IST")
    
    def calculate_levels(self, df: pd.DataFrame) -> Dict:
        """
        Convert ML prediction to trading levels
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            Dictionary with Level, Entry, Exit, SL, and metadata
        """
        # Get ML prediction
        ml_result = self.predictor.predict_direction(df)
        
        # Current market data
        current_price = df['close'].iloc[-1]
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else (df['high'].iloc[-20:].mean() - df['low'].iloc[-20:].mean())
        
        # Get recent high/low for zone
        recent_high = df['high'].iloc[-20:].max()
        recent_low = df['low'].iloc[-20:].min()
        
        # Confidence-based risk/reward - convert from 0-100 to 0-1 scale
        confidence = ml_result['confidence'] / 100  # Convert to decimal
        
        if ml_result['direction'] == 'BUY':
            return self._calculate_buy_levels(
                current_price, atr, recent_high, recent_low, confidence, ml_result
            )
        else:
            return self._calculate_sell_levels(
                current_price, atr, recent_high, recent_low, confidence, ml_result
            )
    
    def _calculate_buy_levels(self, price, atr, high, low, confidence, ml_result) -> Dict:
        """Calculate BUY setup levels"""
        
        # LEVEL (Zone): Support zone for potential bounce
        level_zone = low  # Recent 20-candle low = support zone
        
        # ENTRY: Current price + small buffer (or dip to support)
        entry = price * (1 + self.buffer_pct / 100)
        
        # EXIT TARGET: Based on confidence
        # Higher confidence = higher target
        if confidence >= 0.75:
            target_atr = atr * 2.5  # Very confident: risk 2.5 ATR
        elif confidence >= 0.65:
            target_atr = atr * 2.0  # Confident: risk 2 ATR
        else:
            target_atr = atr * 1.5  # Less confident: risk 1.5 ATR
        
        exit_price = entry + target_atr
        
        # STOPLOSS: Below entry by ATR * multiplier (CAPPED at 13 points max)
        calculated_sl_distance = atr * self.atr_multiplier
        max_sl_points = 13.0  # Rs.900 / 65 lot size = 13.8, using 13 for safety
        sl_distance = min(calculated_sl_distance, max_sl_points)
        sl_price = entry - sl_distance
        
        # Risk/Reward Ratio
        risk = entry - sl_price
        reward = exit_price - entry
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            'direction': 'BUY',
            'confidence': ml_result['confidence'],
            'up_probability': ml_result['up_probability'],
            'down_probability': ml_result['down_probability'],
            'action': ml_result['action'],
            'timestamp_ist': self.get_ist_time(),
            'forecast_horizon': '15-30 minutes',
            
            # TRADING LEVELS
            'level_zone': round(level_zone, 2),
            'entry': round(entry, 2),
            'exit_target': round(exit_price, 2),
            'stoploss': round(sl_price, 2),
            
            # METRICS
            'current_price': round(price, 2),
            'atr': round(atr, 2),
            'risk_per_trade': round(risk, 2),
            'reward_per_trade': round(reward, 2),
            'risk_reward_ratio': round(rr_ratio, 2),
            'recent_20c_high': round(high, 2),
            'recent_20c_low': round(low, 2),
            
            # SIGNALS
            'zone_description': f"Support zone between {round(low, 2)} - {round(level_zone + (atr*0.5), 2)}",
            'entry_description': f"Buy on touch of {round(level_zone, 2)} or break above {round(entry, 2)}",
            'exit_description': f"Take profit at {round(exit_price, 2)} (target {round(target_atr, 2)} points)",
            'sl_description': f"Stop loss at {round(sl_price, 2)} (risk {round(risk, 2)} points)"
        }
    
    def _calculate_sell_levels(self, price, atr, high, low, confidence, ml_result) -> Dict:
        """Calculate SELL setup levels"""
        
        # LEVEL (Zone): Resistance zone for potential pullback
        level_zone = high  # Recent 20-candle high = resistance zone
        
        # ENTRY: Current price - small buffer (or rally to resistance)
        entry = price * (1 - self.buffer_pct / 100)
        
        # EXIT TARGET: Based on confidence
        if confidence >= 0.75:
            target_atr = atr * 2.5
        elif confidence >= 0.65:
            target_atr = atr * 2.0
        else:
            target_atr = atr * 1.5
        
        exit_price = entry - target_atr
        
        # STOPLOSS: Above entry by ATR * multiplier (CAPPED at 13 points max)
        calculated_sl_distance = atr * self.atr_multiplier
        max_sl_points = 13.0  # Rs.900 / 65 lot size = 13.8, using 13 for safety
        sl_distance = min(calculated_sl_distance, max_sl_points)
        sl_price = entry + sl_distance
        
        # Risk/Reward Ratio
        risk = sl_price - entry
        reward = entry - exit_price
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            'direction': 'SELL',
            'confidence': ml_result['confidence'],
            'up_probability': ml_result['up_probability'],
            'down_probability': ml_result['down_probability'],
            'action': ml_result['action'],
            'timestamp_ist': self.get_ist_time(),
            'forecast_horizon': '15-30 minutes',
            
            # TRADING LEVELS
            'level_zone': round(level_zone, 2),
            'entry': round(entry, 2),
            'exit_target': round(exit_price, 2),
            'stoploss': round(sl_price, 2),
            
            # METRICS
            'current_price': round(price, 2),
            'atr': round(atr, 2),
            'risk_per_trade': round(risk, 2),
            'reward_per_trade': round(reward, 2),
            'risk_reward_ratio': round(rr_ratio, 2),
            'recent_20c_high': round(high, 2),
            'recent_20c_low': round(low, 2),
            
            # SIGNALS
            'zone_description': f"Resistance zone between {round(high - (atr*0.5), 2)} - {round(level_zone, 2)}",
            'entry_description': f"Sell on touch of {round(level_zone, 2)} or break below {round(entry, 2)}",
            'exit_description': f"Take profit at {round(exit_price, 2)} (target {round(target_atr, 2)} points)",
            'sl_description': f"Stop loss at {round(sl_price, 2)} (risk {round(risk, 2)} points)"
        }
    
    def format_for_display(self, levels: Dict) -> str:
        """Format levels for beautiful display"""
        
        output = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                     TRADING LEVELS - 15-30 MIN FORECAST                 ║
╚══════════════════════════════════════════════════════════════════════════╝

⏰ TIME (IST):             {levels['timestamp_ist']}
📊 FORECAST HORIZON:      {levels['forecast_horizon']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 ML PREDICTION:
   Direction:            {levels['direction']}
   Confidence:           {levels['confidence']:.1f}%
   UP Probability:       {levels['up_probability']:.1f}%
   DOWN Probability:     {levels['down_probability']:.1f}%
   Action:               {levels['action']} {'✓ TRADE THIS!' if levels['action'] != 'WAIT' else '✗ SKIP (low confidence)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 CURRENT MARKET:
   Price Now:            {levels['current_price']}
   ATR (Volatility):     {levels['atr']}
   20-Candle High:       {levels['recent_20c_high']}
   20-Candle Low:        {levels['recent_20c_low']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 TRADING SETUP:

   📍 LEVEL/ZONE:       {levels['level_zone']}
      └─ {levels['zone_description']}
   
   📥 ENTRY:            {levels['entry']}
      └─ {levels['entry_description']}
   
   ✅ EXIT TARGET:      {levels['exit_target']}
      └─ {levels['exit_description']}
   
   🛑 STOP LOSS:        {levels['stoploss']}
      └─ {levels['sl_description']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 RISK/REWARD:
   Risk per Trade:       {levels['risk_per_trade']} points
   Reward per Trade:     {levels['reward_per_trade']} points
   Risk:Reward Ratio:    1:{levels['risk_reward_ratio']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return output


def main():
    """Test trading levels generation"""
    from ml_models.data_extractor import DataExtractor
    
    logger.info("=" * 70)
    logger.info("TRADING LEVELS GENERATOR TEST")
    logger.info("=" * 70)
    
    # Fetch recent data
    extractor = DataExtractor()
    df = extractor.fetch_historical_data(days=5, interval=5)
    
    logger.info(f"Fetched {len(df)} candles")
    
    # Generate levels
    generator = TradingLevelsGenerator()
    levels = generator.calculate_levels(df)
    
    # Display
    print(generator.format_for_display(levels))
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ LEVELS GENERATED SUCCESSFULLY")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
