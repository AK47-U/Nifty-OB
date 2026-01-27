"""
Data fetching module for Indian indices
Supports multiple data sources with fallback mechanisms
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import requests
from loguru import logger
import time

from config.settings import SYMBOL_MAPPING, TradingConfig

class DataFetcher:
    """Main class for fetching financial data from various sources"""
    
    def __init__(self, data_source: str = 'yahoo'):
        self.data_source = data_source
        self.config = TradingConfig()
        
    def fetch_historical_data(
        self, 
        symbol: str, 
        period: str = '1y',
        interval: str = '1d'
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a given symbol
        
        Args:
            symbol: Index symbol (SENSEX/NIFTY)
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            if self.data_source == 'yahoo':
                # For intraday data, get more recent data for better technical indicators
                if interval in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h']:
                    # For intraday, use last 5-7 days to get enough data points
                    if period in ['1d', '5d']:
                        period = '7d'  # Ensure we have enough data for calculations
                
                return self._fetch_yahoo_data(symbol, period, interval)
            else:
                logger.warning(f"Data source {self.data_source} not implemented, falling back to Yahoo")
                return self._fetch_yahoo_data(symbol, period, interval)
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def _fetch_yahoo_data(
        self, 
        symbol: str, 
        period: str = '1y',
        interval: str = '1d'
    ) -> Optional[pd.DataFrame]:
        """Fetch data from Yahoo Finance"""
        try:
            yahoo_symbol = SYMBOL_MAPPING['yahoo'].get(symbol, symbol)
            ticker = yf.Ticker(yahoo_symbol)
            
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"No data received for {symbol}")
                return None
            
            # Standardize column names - handle different column structures
            original_columns = list(data.columns)
            logger.debug(f"Original columns for {symbol}: {original_columns}")
            
            # Keep only OHLCV columns and rename them properly
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            standardized_data = pd.DataFrame()
            
            for col in required_columns:
                if col in data.columns:
                    standardized_data[col] = data[col]
                else:
                    logger.warning(f"Column {col} not found in data for {symbol}")
            
            # If we don't have all required columns, return None
            if len(standardized_data.columns) < 4:  # At least OHLC
                logger.error(f"Insufficient columns for {symbol}: {list(standardized_data.columns)}")
                return None
            
            standardized_data.index.name = 'Date'
            
            logger.info(f"Fetched {len(standardized_data)} records for {symbol}")
            return standardized_data
            
        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
            return None
    
    def fetch_live_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch live/current market data
        
        Args:
            symbol: Index symbol (SENSEX/NIFTY)
        
        Returns:
            Dictionary with current price data
        """
        try:
            yahoo_symbol = SYMBOL_MAPPING['yahoo'].get(symbol, symbol)
            ticker = yf.Ticker(yahoo_symbol)
            
            # Get current price and basic info
            try:
                info = ticker.info
            except:
                info = {}
            
            # Try to get recent data for current price
            try:
                history = ticker.history(period='1d', interval='1m')
                if history.empty:
                    # Fallback to daily data
                    history = ticker.history(period='2d', interval='1d')
            except:
                # Final fallback
                history = ticker.history(period='5d', interval='1d')
            
            if history.empty:
                logger.warning(f"No recent data available for {symbol}")
                return None
            
            current_price = history['Close'].iloc[-1] if not history.empty else 0
            previous_close = info.get('previousClose', current_price)
            
            # If previous close is not available, use previous day's close
            if previous_close is None or previous_close == 0:
                if len(history) > 1:
                    previous_close = history['Close'].iloc[-2]
                else:
                    previous_close = current_price
            
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close != 0 else 0
            
            volume = history['Volume'].iloc[-1] if 'Volume' in history.columns else 0
            
            return {
                'symbol': symbol,
                'current_price': float(current_price),
                'previous_close': float(previous_close),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': float(volume),
                'timestamp': datetime.now(),
                'high_52w': info.get('fiftyTwoWeekHigh'),
                'low_52w': info.get('fiftyTwoWeekLow'),
                'market_cap': info.get('marketCap')
            }
            
        except Exception as e:
            logger.error(f"Error fetching live data for {symbol}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching live data for {symbol}: {e}")
            return None
    
    def fetch_intraday_data(
        self, 
        symbol: str, 
        interval: str = '5m',
        days: int = 5
    ) -> Optional[pd.DataFrame]:
        """
        Fetch intraday data for technical analysis
        
        Args:
            symbol: Index symbol
            interval: Time interval (1m, 5m, 15m, 30m, 1h)
            days: Number of days to fetch
        
        Returns:
            DataFrame with intraday OHLCV data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            yahoo_symbol = SYMBOL_MAPPING['yahoo'].get(symbol, symbol)
            ticker = yf.Ticker(yahoo_symbol)
            
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval
            )
            
            if data.empty:
                logger.warning(f"No intraday data for {symbol}")
                return None

            # Standardize to OHLCV columns robustly
            cols = list(data.columns)
            logger.debug(f"Intraday original columns for {symbol}: {cols}")

            standardized = pd.DataFrame(index=data.index)
            # Open/High/Low
            for c in ["Open", "High", "Low"]:
                if c in data.columns:
                    standardized[c] = data[c]
            # Close: prefer Close, fallback to Adj Close
            if "Close" in data.columns:
                standardized["Close"] = data["Close"]
            elif "Adj Close" in data.columns:
                standardized["Close"] = data["Adj Close"]
            # Volume
            if "Volume" in data.columns:
                standardized["Volume"] = data["Volume"]

            # Validate minimal required columns
            required_min = ["Open", "High", "Low", "Close"]
            missing = [c for c in required_min if c not in standardized.columns]
            if missing:
                logger.error(f"Insufficient intraday columns for {symbol}; missing: {missing}; have: {list(standardized.columns)}")
                return None

            standardized.index.name = "Date"
            standardized = standardized.dropna()

            logger.info(f"Fetched {len(standardized)} intraday records for {symbol}")
            return standardized
            
        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return None
    
    def is_market_open(self) -> bool:
        """Check if Indian market is currently open"""
        try:
            now = datetime.now()
            current_time = now.time()
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Market hours: 09:15 to 15:30 IST
            market_open = datetime.strptime('09:15', '%H:%M').time()
            market_close = datetime.strptime('15:30', '%H:%M').time()
            
            return market_open <= current_time <= market_close
            
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    def get_market_status(self) -> Dict[str, Any]:
        """Get comprehensive market status information"""
        return {
            'is_open': self.is_market_open(),
            'current_time': datetime.now(),
            'next_market_open': self._get_next_market_open(),
            'trading_session': self._get_current_session()
        }
    
    def _get_next_market_open(self) -> datetime:
        """Calculate next market opening time"""
        now = datetime.now()
        
        # If it's before 9:15 AM on a weekday
        if now.weekday() < 5 and now.time() < datetime.strptime('09:15', '%H:%M').time():
            return now.replace(hour=9, minute=15, second=0, microsecond=0)
        
        # Calculate next weekday
        days_ahead = 1
        if now.weekday() >= 4:  # Friday or later
            days_ahead = 7 - now.weekday()  # Days until Monday
        
        next_day = now + timedelta(days=days_ahead)
        return next_day.replace(hour=9, minute=15, second=0, microsecond=0)
    
    def _get_current_session(self) -> str:
        """Determine current trading session"""
        if not self.is_market_open():
            return 'closed'
        
        now_time = datetime.now().time()
        morning_session_end = datetime.strptime('11:30', '%H:%M').time()
        
        if now_time <= morning_session_end:
            return 'morning_session'
        else:
            return 'afternoon_session'