#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKET STRUCTURE VALIDATOR
Validates daily market structure against MTF signals to prevent false breakout traps.
Detects: Higher highs/lows trend, opening bias, entry failure scenarios
"""

import pandas as pd
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class StructureTrend(Enum):
    """Current market structure trend classification"""
    HIGHER_HIGHS_LOWS = "BULLISH_STRUCTURE"      # Making higher highs/lows = bullish
    LOWER_HIGHS_LOWS = "BEARISH_STRUCTURE"       # Making lower highs/lows = bearish
    CHOPPY_STRUCTURE = "CHOPPY_STRUCTURE"        # No clear trend in structure
    UNKNOWN = "UNKNOWN"


class OpeningBias(Enum):
    """Where the market opened relative to support/resistance"""
    OPENED_NEAR_SUPPORT = "BULLISH_BIAS"
    OPENED_NEAR_RESISTANCE = "BEARISH_BIAS"
    OPENED_NEUTRAL = "NEUTRAL_BIAS"


@dataclass
class StructureValidation:
    """Result of market structure analysis"""
    is_valid: bool                          # Is structure consistent with MTF signal?
    structure_trend: StructureTrend          # Current market structure
    opening_bias: OpeningBias                # Opening position relative to support/resistance
    entry_failure_risk: bool                # Has entry already failed in first 5min?
    confidence_adjustment: float            # Confidence multiplier (1.0 = no change)
    warnings: list[str]                     # Detailed warning messages
    
    def __str__(self):
        msg = f"Structure: {self.structure_trend.value} | "
        msg += f"Opening: {self.opening_bias.value} | "
        msg += f"Entry Failure Risk: {self.entry_failure_risk}\n"
        msg += f"Confidence Adjustment: {self.confidence_adjustment:.2f}x\n"
        if self.warnings:
            msg += "Warnings:\n"
            for w in self.warnings:
                msg += f"  • {w}\n"
        return msg


class MarketStructure:
    """
    Validates daily market structure to prevent false breakout trades.
    Specifically addresses: "Higher timeframes bullish but day turns bearish" trap
    """
    
    def __init__(self, intraday_candles: pd.DataFrame, daily_candles: pd.DataFrame,
                 current_price: float, support_level: float, resistance_level: float,
                 market_open_time: datetime = None):
        """
        Args:
            intraday_candles: 5-minute OHLCV candles (must have columns: open, high, low, close, timestamp)
            daily_candles: Daily OHLCV candles (to detect HH/HL or LL/HL pattern)
            current_price: Current LTP
            support_level: Key support level (e.g., BC from CPR or S1)
            resistance_level: Key resistance level (e.g., TC from CPR or R1)
            market_open_time: Market open time for reference (defaults to 9:15 IST)
        """
        self.intraday = intraday_candles.copy()
        self.daily = daily_candles.copy()
        self.ltp = current_price
        self.support = support_level
        self.resistance = resistance_level
        self.market_open_time = market_open_time
        
        # Standardize column names
        self._standardize_columns()
    
    def _standardize_columns(self):
        """Ensure column names are lowercase"""
        self.intraday.columns = self.intraday.columns.str.lower()
        self.daily.columns = self.daily.columns.str.lower()
    
    def validate_against_mtf_signal(self, mtf_trend: str, mtf_confidence: float) -> StructureValidation:
        """
        Master validation function: Check if market structure supports the MTF signal.
        
        Args:
            mtf_trend: "BULLISH" or "BEARISH" from MTF analyzer
            mtf_confidence: 0-100 confidence percentage
        
        Returns:
            StructureValidation with detailed analysis
        """
        warnings = []
        confidence_adj = 1.0
        
        # Check 1: Market structure (higher highs/lows vs lower highs/lows)
        struct_trend = self._detect_structure_trend()
        struct_valid = self._is_structure_aligned(mtf_trend, struct_trend)
        if not struct_valid:
            warnings.append(f"⚠️ Market structure {struct_trend.value} contradicts MTF {mtf_trend} signal")
            confidence_adj *= 0.6
        
        # Check 2: Opening bias (where did the day open?)
        opening_bias = self._detect_opening_bias()
        bias_valid = self._is_opening_bias_aligned(mtf_trend, opening_bias)
        if not bias_valid:
            warnings.append(f"⚠️ Day opened {opening_bias.value}, conflicts with {mtf_trend} signal")
            confidence_adj *= 0.7
        
        # Check 3: Entry failure detection (failed to sustain direction in first 5m)
        entry_failed = self._detect_entry_failure()
        if entry_failed:
            warnings.append("⚠️ Entry rejection risk: Failed to sustain direction in first 5 minutes")
            confidence_adj *= 0.5
        
        # Overall validity: If structure AND opening bias both oppose MTF signal, block trade
        is_valid = struct_valid or bias_valid or (mtf_confidence < 80)  # Still allow high confidence trades
        
        return StructureValidation(
            is_valid=is_valid,
            structure_trend=struct_trend,
            opening_bias=opening_bias,
            entry_failure_risk=entry_failed,
            confidence_adjustment=confidence_adj,
            warnings=warnings
        )
    
    def _detect_structure_trend(self) -> StructureTrend:
        """
        Detect if market is making higher highs/lows (bullish) or lower highs/lows (bearish).
        Compares last 5 days.
        """
        if len(self.daily) < 5:
            return StructureTrend.UNKNOWN
        
        recent_5 = self.daily.tail(5)
        highs = recent_5['high'].values
        lows = recent_5['low'].values
        
        # Count higher and lower patterns
        higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
        
        lower_highs = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
        lower_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        
        # Bullish structure: HH AND HL (both higher)
        if higher_highs >= 3 and higher_lows >= 3:
            return StructureTrend.HIGHER_HIGHS_LOWS
        
        # Bearish structure: LH AND LL (both lower)
        if lower_highs >= 3 and lower_lows >= 3:
            return StructureTrend.LOWER_HIGHS_LOWS
        
        # Choppy if mixed
        return StructureTrend.CHOPPY_STRUCTURE
    
    def _is_structure_aligned(self, mtf_trend: str, struct_trend: StructureTrend) -> bool:
        """Check if market structure aligns with MTF trend"""
        if struct_trend == StructureTrend.UNKNOWN or struct_trend == StructureTrend.CHOPPY_STRUCTURE:
            return True  # Don't block on unclear structure
        
        if mtf_trend == "BULLISH" and struct_trend == StructureTrend.HIGHER_HIGHS_LOWS:
            return True
        
        if mtf_trend == "BEARISH" and struct_trend == StructureTrend.LOWER_HIGHS_LOWS:
            return True
        
        return False
    
    def _detect_opening_bias(self) -> OpeningBias:
        """
        Detect where the market opened today relative to support/resistance.
        
        Opening near support = bullish bias (buyers waiting at support)
        Opening near resistance = bearish bias (sellers waiting at resistance)
        Opening neutral = no clear bias
        """
        if len(self.intraday) < 1:
            return OpeningBias.OPENED_NEUTRAL
        
        # Get today's open (first 5m candle of the day)
        today_open = self.intraday.iloc[0]['open']
        
        # Distance to support and resistance
        dist_to_support = today_open - self.support
        dist_to_resistance = self.resistance - today_open
        
        support_zone = 50  # pts threshold - if within 50 pts of support/resistance
        
        # Opened near support (bullish bias)
        if dist_to_support <= support_zone and dist_to_support > 0:
            return OpeningBias.OPENED_NEAR_SUPPORT
        
        # Opened near resistance (bearish bias)
        if dist_to_resistance <= support_zone and dist_to_resistance > 0:
            return OpeningBias.OPENED_NEAR_RESISTANCE
        
        # Neutral
        return OpeningBias.OPENED_NEUTRAL
    
    def _is_opening_bias_aligned(self, mtf_trend: str, opening_bias: OpeningBias) -> bool:
        """Check if opening position supports the MTF trend"""
        if opening_bias == OpeningBias.OPENED_NEUTRAL:
            return True  # Neutral opening doesn't contradict
        
        if mtf_trend == "BULLISH" and opening_bias == OpeningBias.OPENED_NEAR_SUPPORT:
            return True
        
        if mtf_trend == "BEARISH" and opening_bias == OpeningBias.OPENED_NEAR_RESISTANCE:
            return True
        
        return False
    
    def _detect_entry_failure(self) -> bool:
        """
        Detect if price has already failed to sustain the expected direction.
        
        For bullish signal: Price should be rising or holding above support
        For bearish signal: Price should be falling or holding below resistance
        
        If first 5 minutes show reversal, entry is already risky.
        """
        if len(self.intraday) < 2:
            return False
        
        # Get first 5-minute candle (market open)
        first_candle = self.intraday.iloc[0]
        latest_candle = self.intraday.iloc[-1]
        
        first_open = first_candle['open']
        first_close = first_candle['close']
        latest_close = latest_candle['close']
        
        # Bullish candle at open (buyers in control initially)
        bullish_open = first_close > first_open
        
        # Bearish candle at open (sellers in control initially)
        bearish_open = first_close < first_open
        
        # If opened bullish but latest close is below first open, entry failed for bullish trade
        if bullish_open and latest_close < first_open:
            return True
        
        # If opened bearish but latest close is above first open, entry failed for bearish trade
        if bearish_open and latest_close > first_open:
            return True
        
        return False
    
    def get_daily_ohlc_summary(self) -> dict:
        """Get summary of today's OHLC for context"""
        if len(self.daily) < 1:
            return {}
        
        today = self.daily.iloc[-1]
        return {
            'open': float(today['open']),
            'high': float(today['high']),
            'low': float(today['low']),
            'close': float(today['close']),
            'range': float(today['high'] - today['low']),
        }
