"""
LAYER 2: Signal & Momentum Engine
WHEN TO TRADE - Technical Confluence & Multi-Timeframe Confirmation

Triggered ONLY by Layer 1 proximity events
Validates: EMA alignment + VWAP + RSI + MACD + MTF trend
Output: "Ready-to-Trade" signal with confluence score
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
from indicators.technical import TechnicalIndicators


@dataclass
class SignalConfluence:
    """Signal validation with confluence scoring"""
    ema_aligned: bool = False
    vwap_aligned: bool = False
    rsi_valid: bool = False
    macd_valid: bool = False
    mtf_aligned: bool = False
    confluence_score: float = 0.0  # 0-1
    signal_strength: str = "weak"  # weak, medium, strong
    ready_to_trade: bool = False


class SignalMomentumEngine:
    """
    Layer 2: Signal Generator
    Only triggered when Layer 1 flags a proximity event
    Validates technical confluence and multi-timeframe alignment
    """
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
        self.intraday_data = None  # 5-min data
        self.trend_data = None     # 15-min data
        self.confluence_threshold = 3.5  # Minimum score to trade (out of 5)
        logger.info("Layer 2 initialized: Signal & Momentum Engine")
    
    def validate_signal(
        self,
        intraday_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        direction: str  # 'bullish' or 'bearish'
    ) -> SignalConfluence:
        """
        Validate signal with full technical confluence
        
        Args:
            intraday_df: 5-min OHLCV data (recent 100 candles)
            trend_df: 15-min OHLCV data (recent 50 candles)
            direction: 'bullish' for CALL, 'bearish' for PUT
        
        Returns:
            SignalConfluence object with validation results
        """
        confluence = SignalConfluence()
        
        if intraday_df is None or len(intraday_df) < 20:
            logger.warning("Insufficient intraday data for signal validation")
            return confluence
        
        # Calculate indicators if not present
        intraday_df = self._calculate_indicators(intraday_df)
        trend_df = self._calculate_indicators(trend_df) if trend_df is not None else None
        
        # 1. EMA Stack Alignment (5 > 12 > 20 for bullish, reverse for bearish)
        confluence.ema_aligned = self._check_ema_alignment(intraday_df, direction)
        
        # 2. VWAP Alignment
        confluence.vwap_aligned = self._check_vwap_alignment(intraday_df, direction)
        
        # 3. RSI Momentum
        confluence.rsi_valid = self._check_rsi_condition(intraday_df, direction)
        
        # 4. MACD Histogram
        confluence.macd_valid = self._check_macd_histogram(intraday_df, direction)
        
        # 5. Multi-Timeframe (5-min signal + 15-min trend alignment)
        confluence.mtf_aligned = self._check_mtf_alignment(intraday_df, trend_df, direction)
        
        # Calculate confluence score (each validation worth 1 point, max 5)
        confluence_score = sum([
            confluence.ema_aligned,
            confluence.vwap_aligned,
            confluence.rsi_valid,
            confluence.macd_valid,
            confluence.mtf_aligned
        ])
        
        confluence.confluence_score = confluence_score / 5.0  # Normalize to 0-1
        
        # Determine signal strength
        if confluence_score >= 4.5:
            confluence.signal_strength = "strong"
            confluence.ready_to_trade = True
        elif confluence_score >= 3.5:
            confluence.signal_strength = "medium"
            confluence.ready_to_trade = True
        else:
            confluence.signal_strength = "weak"
            confluence.ready_to_trade = False
        
        logger.info(f"Signal Validation: {direction.upper()} | "
                   f"Score: {confluence_score}/5 | "
                   f"Strength: {confluence.signal_strength} | "
                   f"Ready: {confluence.ready_to_trade}")
        
        return confluence
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        if 'EMA5' not in df.columns:
            df['EMA5'] = self.indicators.calculate_ema(df['Close'], 5)
            df['EMA12'] = self.indicators.calculate_ema(df['Close'], 12)
            df['EMA20'] = self.indicators.calculate_ema(df['Close'], 20)
        
        if 'RSI' not in df.columns:
            df['RSI'] = self.indicators.calculate_rsi(df['Close'], 14)
        
        if 'MACD' not in df.columns:
            macd_dict = self.indicators.calculate_macd(df['Close'])
            df['MACD'] = macd_dict.get('MACD', 0)
            df['MACD_Signal'] = macd_dict.get('Signal', 0)
            df['MACD_Histogram'] = macd_dict.get('Histogram', 0)
        
        if 'VWAP' not in df.columns:
            df['VWAP'] = self.indicators.calculate_vwap(df)
        
        return df
    
    def _check_ema_alignment(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Check EMA stack alignment
        BULLISH: EMA5 > EMA12 > EMA20
        BEARISH: EMA5 < EMA12 < EMA20
        """
        latest = df.iloc[-1]
        
        ema5 = float(latest.get('EMA5', 0)) if 'EMA5' in latest.index else 0.0
        ema12 = float(latest.get('EMA12', 0)) if 'EMA12' in latest.index else 0.0
        ema20 = float(latest.get('EMA20', 0)) if 'EMA20' in latest.index else 0.0
        close = float(latest['Close']) if 'Close' in latest.index else 0.0
        
        if direction == 'bullish':
            # For CALL: Price > EMA5 > EMA12 > EMA20
            aligned = (close > ema5) and (ema5 > ema12) and (ema12 > ema20)
        else:
            # For PUT: Price < EMA5 < EMA12 < EMA20
            aligned = (close < ema5) and (ema5 < ema12) and (ema12 < ema20)
        
        logger.debug(f"EMA Alignment ({direction}): {aligned} | "
                    f"P:{close:.0f} E5:{ema5:.0f} E12:{ema12:.0f} E20:{ema20:.0f}")
        
        return aligned
    
    def _check_vwap_alignment(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Check price vs VWAP alignment
        BULLISH: Price > VWAP
        BEARISH: Price < VWAP
        """
        latest = df.iloc[-1]
        close = float(latest['Close']) if 'Close' in latest.index else 0.0
        vwap = float(latest.get('VWAP', close)) if 'VWAP' in latest.index else close
        
        if direction == 'bullish':
            aligned = close > vwap
        else:
            aligned = close < vwap
        
        logger.debug(f"VWAP Alignment ({direction}): {aligned} | "
                    f"Price:{close:.0f} VWAP:{vwap:.0f}")
        
        return aligned
    
    def _check_rsi_condition(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Check RSI momentum
        BULLISH: RSI > 60
        BEARISH: RSI < 40
        """
        latest = df.iloc[-1]
        rsi = float(latest.get('RSI', 50)) if 'RSI' in latest.index else 50.0
        
        if direction == 'bullish':
            valid = rsi > 60
        else:
            valid = rsi < 40
        
        logger.debug(f"RSI Condition ({direction}): {valid} | RSI:{rsi:.1f}")
        
        return valid
    
    def _check_macd_histogram(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Check MACD histogram direction
        BULLISH: Histogram is positive and increasing
        BEARISH: Histogram is negative and decreasing
        """
        if len(df) < 2:
            return False
        
        latest = df.iloc[-1]
        previous = df.iloc[-2]
        
        current_hist = float(latest.get('MACD_Histogram', 0)) if 'MACD_Histogram' in latest.index else 0.0
        previous_hist = float(previous.get('MACD_Histogram', 0)) if 'MACD_Histogram' in previous.index else 0.0
        
        if direction == 'bullish':
            valid = (current_hist > 0) and (current_hist > previous_hist)
        else:
            valid = (current_hist < 0) and (current_hist < previous_hist)
        
        logger.debug(f"MACD Histogram ({direction}): {valid} | "
                    f"Current:{current_hist:.4f} Previous:{previous_hist:.4f}")
        
        return valid
    
    def _check_mtf_alignment(
        self,
        intraday_df: pd.DataFrame,
        trend_df: Optional[pd.DataFrame],
        direction: str
    ) -> bool:
        """
        Multi-Timeframe validation
        5-min signal must align with 15-min trend (EMA20)
        """
        if trend_df is None or len(trend_df) < 10:
            logger.warning("Insufficient trend data for MTF check, skipping")
            return True  # Allow trade if trend data unavailable
        
        latest_intraday = intraday_df.iloc[-1]
        latest_trend = trend_df.iloc[-1]
        
        close_5m = float(latest_intraday['Close']) if 'Close' in latest_intraday.index else 0.0
        ema20_15m = float(latest_trend.get('EMA20', close_5m)) if 'EMA20' in latest_trend.index else close_5m
        
        if direction == 'bullish':
            # 5-min price should be above 15-min EMA20
            aligned = close_5m > ema20_15m
        else:
            # 5-min price should be below 15-min EMA20
            aligned = close_5m < ema20_15m
        
        logger.debug(f"MTF Alignment ({direction}): {aligned} | "
                    f"5M Close:{close_5m:.0f} 15M EMA20:{ema20_15m:.0f}")
        
        return aligned


# Test
if __name__ == "__main__":
    import yfinance as yf
    
    engine = SignalMomentumEngine()
    
    # Fetch 5-min and 15-min data
    print("\nFetching intraday data...")
    intraday = yf.download('^NSEI', period='5d', interval='5m', progress=False)
    trend = yf.download('^NSEI', period='5d', interval='15m', progress=False)
    
    print(f"✓ Got {len(intraday)} 5-min candles")
    print(f"✓ Got {len(trend)} 15-min candles")
    
    # Validate bullish signal
    print("\n" + "="*80)
    print("LAYER 2: SIGNAL & MOMENTUM ENGINE TEST")
    print("="*80)
    
    confluence_call = engine.validate_signal(intraday, trend, 'bullish')
    print(f"\nCALL SIGNAL (Bullish):")
    print(f"  EMA Aligned: {confluence_call.ema_aligned}")
    print(f"  VWAP Aligned: {confluence_call.vwap_aligned}")
    print(f"  RSI Valid: {confluence_call.rsi_valid}")
    print(f"  MACD Valid: {confluence_call.macd_valid}")
    print(f"  MTF Aligned: {confluence_call.mtf_aligned}")
    print(f"  Confluence Score: {confluence_call.confluence_score:.2f}/1.0")
    print(f"  Signal Strength: {confluence_call.signal_strength}")
    print(f"  Ready to Trade: {confluence_call.ready_to_trade}")
    
    # Validate bearish signal
    confluence_put = engine.validate_signal(intraday, trend, 'bearish')
    print(f"\nPUT SIGNAL (Bearish):")
    print(f"  EMA Aligned: {confluence_put.ema_aligned}")
    print(f"  VWAP Aligned: {confluence_put.vwap_aligned}")
    print(f"  RSI Valid: {confluence_put.rsi_valid}")
    print(f"  MACD Valid: {confluence_put.macd_valid}")
    print(f"  MTF Aligned: {confluence_put.mtf_aligned}")
    print(f"  Confluence Score: {confluence_put.confluence_score:.2f}/1.0")
    print(f"  Signal Strength: {confluence_put.signal_strength}")
    print(f"  Ready to Trade: {confluence_put.ready_to_trade}")
    
    print("\n" + "="*80)
