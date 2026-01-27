"""
Technical indicators module for trading signal generation
Implements EMA, CPR, VWAP, RSI, MACD, and support/resistance levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger

class TechnicalIndicators:
    """Class containing all technical indicator calculations"""
    
    @staticmethod
    def calculate_ema(data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average
        
        Args:
            data: Price series (typically Close prices)
            period: EMA period
        
        Returns:
            EMA series
        """
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_multiple_ema(data: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """
        Calculate multiple EMAs at once
        
        Args:
            data: DataFrame with OHLCV data
            periods: List of EMA periods
        
        Returns:
            DataFrame with EMA columns
        """
        result = data.copy()
        
        for period in periods:
            result[f'EMA_{period}'] = TechnicalIndicators.calculate_ema(data['Close'], period)
        
        return result
    
    @staticmethod
    def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index using Wilder's smoothing method
        This matches the calculation used by most trading platforms
        
        Args:
            data: Price series
            period: RSI period (default 14)
        
        Returns:
            RSI series
        """
        delta = data.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate initial SMA for gains and losses
        avg_gain = gains.rolling(window=period, min_periods=period).mean()
        avg_loss = losses.rolling(window=period, min_periods=period).mean()
        
        # Apply Wilder's smoothing (EMA with alpha = 1/period)
        # This is the correct method used by trading platforms
        avg_gain = avg_gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = avg_loss.ewm(alpha=1/period, adjust=False).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        data: pd.Series, 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Dict[str, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            data: Price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
        
        Returns:
            Dictionary with MACD, Signal, and Histogram series
        """
        ema_fast = TechnicalIndicators.calculate_ema(data, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow_period)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return {
            'MACD': macd_line,
            'Signal': signal_line,
            'Histogram': histogram
        }
    
    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR)
        Measures market volatility
        
        Args:
            data: DataFrame with OHLCV data
            period: ATR period (default 14)
        
        Returns:
            ATR series
        """
        if 'High' not in data.columns or 'Low' not in data.columns or 'Close' not in data.columns:
            logger.warning("Missing OHLC columns for ATR calculation")
            return pd.Series(0, index=data.index)
        
        # Calculate True Range
        tr1 = data['High'] - data['Low']
        tr2 = abs(data['High'] - data['Close'].shift(1))
        tr3 = abs(data['Low'] - data['Close'].shift(1))
        
        # True Range = max(tr1, tr2, tr3)
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = Simple Moving Average of True Range (Wilder's smoothing)
        atr = true_range.rolling(window=period).mean()
        
        # Wilder's smoothing (alternative, more commonly used for ATR)
        # First ATR is simple average, then exponential smoothing
        atr_wilder = true_range.ewm(span=period, adjust=False).mean()
        
        return atr_wilder
    
    @staticmethod
    def calculate_vwap(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calculate Volume Weighted Average Price.
        If intraday data (frequency < 1D) is detected, compute cumulative session VWAP
        for each trading day (reset at day boundaries). Otherwise use rolling VWAP.

        Args:
            data: DataFrame with OHLCV data
            period: Rolling period used only for non-intraday (daily) data or fallback

        Returns:
            VWAP series aligned with input index
        """
        if 'Volume' not in data.columns:
            logger.warning("Volume column missing; returning Close as VWAP fallback")
            return data['Close']
        
        # Check if volume has valid data
        valid_volume_count = int((data['Volume'] > 0).sum())
        if valid_volume_count <= 0:
            logger.warning("No valid Volume data; returning Close as VWAP fallback")
            return data['Close']

        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        volume = data['Volume']

        # Detect intraday by checking time component variability (multiple entries per day)
        is_intraday = False
        if isinstance(data.index, pd.DatetimeIndex):
            # If more than one row shares the same date, treat as intraday
            date_counts = data.index.date
            is_intraday = len(pd.Series(date_counts).value_counts().index) > 0 and \
                          any(c > 1 for c in pd.Series(date_counts).value_counts().values)

        if is_intraday:
            # Calculate cumulative session VWAP per day
            vwap_values = []
            cumulative_price_volume = 0.0
            cumulative_volume = 0.0
            last_date = None
            for ts, tp, vol in zip(data.index, typical_price, volume):
                current_date = ts.date()
                if last_date is None or current_date != last_date:
                    # Reset at new session
                    cumulative_price_volume = 0.0
                    cumulative_volume = 0.0
                    last_date = current_date
                # Update cumulative sums
                cumulative_price_volume += tp * (vol if vol > 0 else 0)
                cumulative_volume += (vol if vol > 0 else 0)
                if cumulative_volume == 0:
                    vwap_values.append(tp)  # Fallback to typical price
                else:
                    vwap_values.append(cumulative_price_volume / cumulative_volume)
            return pd.Series(vwap_values, index=data.index, name='VWAP')
        else:
            # Daily data: use rolling VWAP as approximation
            volume_nonzero = volume.replace(0, np.nan)
            volume_price = typical_price * volume_nonzero
            cumulative_volume_price = volume_price.rolling(window=period, min_periods=1).sum()
            cumulative_volume = volume_nonzero.rolling(window=period, min_periods=1).sum()
            vwap = cumulative_volume_price / cumulative_volume
            return vwap.fillna(typical_price)
    
    @staticmethod
    def calculate_cpr(data: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate Central Pivot Range (CPR)
        Uses previous day's OHLC to calculate pivot levels
        
        Args:
            data: DataFrame with OHLCV data (must have at least 2 rows)
        
        Returns:
            Dictionary with pivot levels
        """
        if len(data) < 2:
            return {}
        
        # Use previous day's data
        prev_high = data['High'].iloc[-2]
        prev_low = data['Low'].iloc[-2]
        prev_close = data['Close'].iloc[-2]
        
        # Central Pivot Point
        pivot = (prev_high + prev_low + prev_close) / 3
        
        # Top and Bottom Central Pivot
        top_central = (prev_high + prev_low) / 2
        bottom_central = (2 * pivot) - top_central
        
        # Traditional support and resistance levels
        r1 = (2 * pivot) - prev_low  # Resistance 1
        s1 = (2 * pivot) - prev_high  # Support 1
        r2 = pivot + (prev_high - prev_low)  # Resistance 2
        s2 = pivot - (prev_high - prev_low)  # Support 2
        r3 = prev_high + 2 * (pivot - prev_low)  # Resistance 3
        s3 = prev_low - 2 * (prev_high - pivot)  # Support 3
        
        return {
            'pivot': pivot,
            'top_central': top_central,
            'bottom_central': bottom_central,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    
    @staticmethod
    def calculate_support_resistance(
        data: pd.DataFrame, 
        window: int = 20, 
        min_touches: int = 2
    ) -> Dict[str, List[float]]:
        """
        Calculate dynamic support and resistance levels
        
        Args:
            data: DataFrame with OHLCV data
            window: Lookback window for level detection
            min_touches: Minimum touches required for valid level
        
        Returns:
            Dictionary with support and resistance levels
        """
        highs = data['High'].rolling(window=window).max()
        lows = data['Low'].rolling(window=window).min()
        
        # Find significant highs and lows (local peaks and valleys)
        resistance_levels = []
        support_levels = []
        
        for i in range(window, len(data) - window):
            # Check for resistance (local maximum)
            if data['High'].iloc[i] == highs.iloc[i]:
                level = data['High'].iloc[i]
                # Count how many times price touched this level
                touches = sum(abs(data['High'][i-window:i+window] - level) < (level * 0.001))
                if touches >= min_touches:
                    resistance_levels.append(level)
            
            # Check for support (local minimum)
            if data['Low'].iloc[i] == lows.iloc[i]:
                level = data['Low'].iloc[i]
                touches = sum(abs(data['Low'][i-window:i+window] - level) < (level * 0.001))
                if touches >= min_touches:
                    support_levels.append(level)
        
        return {
            'resistance': sorted(set(resistance_levels), reverse=True)[:5],  # Top 5
            'support': sorted(set(support_levels))[:5]  # Bottom 5
        }
    
    @staticmethod
    def calculate_previous_high_low(data: pd.DataFrame, periods: List[int] = [1, 5, 10]) -> Dict[str, Dict[int, float]]:
        """
        Calculate previous highs and lows for different periods
        
        Args:
            data: DataFrame with OHLCV data
            periods: List of lookback periods
        
        Returns:
            Dictionary with previous highs and lows for each period
        """
        result = {'previous_highs': {}, 'previous_lows': {}}
        
        for period in periods:
            if len(data) > period:
                result['previous_highs'][period] = data['High'].iloc[-(period+1):-1].max()
                result['previous_lows'][period] = data['Low'].iloc[-(period+1):-1].min()
        
        return result
    
    @staticmethod
    def calculate_all_indicators(data: pd.DataFrame, config: Optional[object] = None) -> pd.DataFrame:
        """
        Calculate all technical indicators at once
        
        Args:
            data: DataFrame with OHLCV data
            config: Configuration object with indicator parameters
        
        Returns:
            DataFrame with all indicators
        """
        from config.settings import TradingConfig
        
        if config is None:
            config = TradingConfig()
        
        result = data.copy()
        
        try:
            # EMAs
            for period in config.EMA_PERIODS:
                result[f'EMA_{period}'] = TechnicalIndicators.calculate_ema(data['Close'], period)
            
            # RSI
            result['RSI'] = TechnicalIndicators.calculate_rsi(data['Close'], config.RSI_PERIOD)
            
            # ATR (for trade setup calculations)
            result['ATR'] = TechnicalIndicators.calculate_atr(data, config.ATR_PERIOD)
            
            # MACD
            macd_data = TechnicalIndicators.calculate_macd(
                data['Close'], 
                config.MACD_FAST, 
                config.MACD_SLOW, 
                config.MACD_SIGNAL
            )
            result['MACD'] = macd_data['MACD']
            result['MACD_Signal'] = macd_data['Signal']
            result['MACD_Histogram'] = macd_data['Histogram']
            
            # VWAP (session cumulative if intraday and config.VWAP_SESSION True)
            result['VWAP'] = TechnicalIndicators.calculate_vwap(data, config.VWAP_PERIOD)
            
            logger.info("All technical indicators calculated successfully")
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
        
        return result