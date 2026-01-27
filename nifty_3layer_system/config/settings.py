"""
Configuration settings for the Trading Signal Generator
"""

import os
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class TradingConfig:
    """Main trading configuration"""
    
    # Supported indices
    INDICES = ['SENSEX', 'NIFTY']
    
    # EMA periods
    EMA_PERIODS = [5, 12, 20, 50, 200]
    
    # RSI settings
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    
    # ATR settings (for trade setup - entry/exit/SL calculations)
    ATR_PERIOD = 14
    
    # INTRADAY SCALPING (5-15 min trades) - TIGHT stops for quick scalps
    # With ATR ~200-250 points for NIFTY, these give realistic targets:
    ATR_MULTIPLIER_SL_SCALP = 0.10      # SL = 20-25 points (tight risk)
    ATR_MULTIPLIER_T1_SCALP = 0.25      # T1 = 50-65 points (quick profit)
    ATR_MULTIPLIER_T2_SCALP = 0.50      # T2 = 100-125 points (scalper exit)
    
    # INTRADAY (Day trades, 2-4 hour holds) - Medium stops
    ATR_MULTIPLIER_SL_INTRADAY = 0.5    # SL = 100-125 points
    ATR_MULTIPLIER_T1_INTRADAY = 0.75   # T1 = 150-190 points
    ATR_MULTIPLIER_T2_INTRADAY = 1.25   # T2 = 250-310 points
    
    # DAILY TRADING (1 day holds) - Wider stops for daily moves
    ATR_MULTIPLIER_SL_DAILY = 1.5       # SL = 300-375 points
    ATR_MULTIPLIER_T1_DAILY = 2.5       # T1 = 500-625 points
    ATR_MULTIPLIER_T2_DAILY = 4.0       # T2 = 800-1000 points
    
    # MACD settings
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    
    # VWAP settings
    VWAP_PERIOD = 20
    VWAP_SESSION = True  # If True and using intraday data, use session cumulative VWAP

    # Intraday data settings
    INTRADAY_INTERVAL = '5m'  # Default intraday candle interval
    INTRADAY_DAYS = 5         # Number of past trading days to fetch for intraday analysis
    
    # CPR calculation
    CPR_LOOKBACK = 1  # Previous day's data
    
    # Signal generation
    MIN_SIGNAL_STRENGTH = 0.6  # Minimum signal strength (0-1)
    CONFIRMATION_REQUIRED = True  # Require multiple indicator confirmation
    
    # Risk management
    MAX_RISK_PER_TRADE = 0.02  # 2% of capital
    POSITION_SIZE_METHOD = 'fixed_percentage'  # 'fixed_percentage', 'volatility_based'
    
    # Data source settings
    DATA_SOURCE = 'yahoo'  # 'yahoo', 'nse', 'custom'
    UPDATE_INTERVAL = 60  # seconds
    
    # Backtesting
    BACKTEST_START_DATE = '2023-01-01'
    BACKTEST_END_DATE = '2024-01-01'
    INITIAL_CAPITAL = 100000
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'trading_signals.log'

# Environment variables (for sensitive data)
API_KEYS = {
    'ALPHA_VANTAGE': os.getenv('ALPHA_VANTAGE_API_KEY'),
    'NSE_API': os.getenv('NSE_API_KEY'),
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
}

# Symbol mappings for different data sources
SYMBOL_MAPPING = {
    'yahoo': {
        'SENSEX': '^BSESN',
        'NIFTY': '^NSEI'
    },
    'nse': {
        'SENSEX': 'SENSEX',
        'NIFTY': 'NIFTY 50'
    }
}

# Default trading session times (IST)
TRADING_HOURS = {
    'market_open': '09:15',
    'market_close': '15:30',
    'pre_market_open': '09:00',
    'pre_market_close': '09:15'
}