#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKET CONDITION CLASSIFIER
Classifies intraday market into 4 conditions based on volatility + volume metrics
Uses ATR, Volume Ratio, Current Range, MACD, RSI
"""

from dataclasses import dataclass
from enum import Enum


class MarketCondition(Enum):
    """Market volatility classification"""
    QUIET = "QUIET"           # 0.2% - 0.4% move expected (50-100 pts NIFTY)
    NORMAL = "NORMAL"         # 0.6% - 0.9% move expected (150-230 pts NIFTY)
    HIGH = "HIGH"             # 1.2% - 2.0% move expected (300-500 pts NIFTY)
    EXTREME = "EXTREME"       # 2.5%+ move expected (630+ pts NIFTY)


class SetupQuality(Enum):
    """Trade setup quality based on 67 metrics"""
    WEAK = "WEAK"             # <40% confidence
    MODERATE = "MODERATE"     # 40-65% confidence
    STRONG = "STRONG"         # 65-85% confidence
    EXCELLENT = "EXCELLENT"   # 85-100% confidence


@dataclass
class MarketClassification:
    """Result of market condition analysis"""
    condition: MarketCondition
    setup_quality: SetupQuality
    
    # Dynamic adjustments based on condition
    entry_precision: float      # ±X points for entry zone
    stop_loss_points: float     # Minimum SL distance
    target1_points: float       # Dynamic T1
    target2_points: float       # Dynamic T2
    position_size_multiplier: float  # 0.5 = half position, 1.25 = 125%
    
    # Supporting metrics
    atr_ratio: float            # ATR / Current Price
    volume_ratio: float         # Current Vol / 20-period avg
    market_volatility_pct: float  # Expected move percentage


def classify_market_condition(
    atr: float,
    volume_ratio: float,
    current_range: float,
    macd_value: float,
    rsi_value: float,
    current_price: float
) -> MarketCondition:
    """
    Classify market into QUIET/NORMAL/HIGH/EXTREME based on 5 metrics.
    
    Args:
        atr: Average True Range (14 period)
        volume_ratio: Current volume / 20-period average
        current_range: High - Low of current candle
        macd_value: MACD histogram (raw value, will be normalized)
        rsi_value: RSI (0-100)
        current_price: Current LTP for normalization
    
    Returns:
        MarketCondition enum
    """
    
    # Calculate normalized ATR ratio
    atr_ratio = atr / current_price if current_price > 0 else 0
    
    # Normalize MACD by dividing by current price to compare across instruments
    # MACD histogram can range widely, normalize to 0-1 scale relative to price
    macd_normalized = abs(macd_value) / current_price if current_price > 0 else 0
    
    # Thresholds for classification
    # QUIET: Low volatility, low volume, weak momentum
    if atr_ratio < 0.003 and volume_ratio < 0.7:
        if macd_normalized < 0.0002 and 40 < rsi_value < 60:
            return MarketCondition.QUIET
    
    # NORMAL: Moderate volatility, normal volume, moderate momentum
    if atr_ratio < 0.009 and volume_ratio < 1.2:
        if macd_normalized < 0.0005 and 30 < rsi_value < 70:
            return MarketCondition.NORMAL
    
    # HIGH: High volatility, high volume, strong momentum
    if atr_ratio < 0.020 and volume_ratio < 2.0:
        if macd_normalized < 0.0008:
            return MarketCondition.HIGH
    
    # EXTREME: Very high volatility, very high volume, extreme momentum/RSI
    return MarketCondition.EXTREME


def classify_setup_quality(overall_confidence: float) -> SetupQuality:
    """
    Classify setup quality based on overall confidence score (0-100).
    
    Args:
        overall_confidence: Overall confidence percentage (0-100)
    
    Returns:
        SetupQuality enum
    """
    if overall_confidence >= 85:
        return SetupQuality.EXCELLENT
    elif overall_confidence >= 65:
        return SetupQuality.STRONG
    elif overall_confidence >= 40:
        return SetupQuality.MODERATE
    else:
        return SetupQuality.WEAK


def get_dynamic_parameters(
    market_condition: MarketCondition,
    setup_quality: SetupQuality,
    atr: float,
    volume_ratio: float,
    current_price: float
) -> MarketClassification:
    """
    Calculate dynamic entry/SL/targets based on market condition + setup quality.
    
    Args:
        market_condition: Market condition (QUIET/NORMAL/HIGH/EXTREME)
        setup_quality: Setup quality (WEAK/MODERATE/STRONG/EXCELLENT)
        atr: Average True Range for context
        volume_ratio: Volume ratio for context
        current_price: Current price for context
    
    Returns:
        MarketClassification with all dynamic parameters
    """
    
    atr_ratio = atr / current_price if current_price > 0 else 0
    
    # Base parameters by condition
    if market_condition == MarketCondition.QUIET:
        entry_precision = 3
        sl_base = 10
        t1_base = 20
        t2_base = 35
        position_multiplier_base = 0.5
        volatility_pct = 0.003
    
    elif market_condition == MarketCondition.NORMAL:
        entry_precision = 5
        sl_base = 15
        t1_base = 45
        t2_base = 75
        position_multiplier_base = 1.0
        volatility_pct = 0.007
    
    elif market_condition == MarketCondition.HIGH:
        entry_precision = 8
        sl_base = 25
        t1_base = 90
        t2_base = 135
        position_multiplier_base = 0.8
        volatility_pct = 0.015
    
    else:  # EXTREME
        entry_precision = 12
        sl_base = 50
        t1_base = 175
        t2_base = 300
        position_multiplier_base = 0.5
        volatility_pct = 0.035
    
    # Adjust by setup quality
    if setup_quality == SetupQuality.WEAK:
        # WEAK: Don't trade, or use absolute minimum
        entry_precision *= 0.8
        sl_base *= 1.2
        t1_base *= 0.5
        t2_base *= 0.5
        position_multiplier = 0  # Skip trade
    
    elif setup_quality == SetupQuality.MODERATE:
        # MODERATE: Conservative positions
        entry_precision *= 0.9
        sl_base *= 1.1
        t1_base *= 0.75
        t2_base *= 0.75
        position_multiplier = position_multiplier_base * 0.5
    
    elif setup_quality == SetupQuality.STRONG:
        # STRONG: Normal positions
        entry_precision *= 1.0
        sl_base *= 1.0
        t1_base *= 1.0
        t2_base *= 1.0
        position_multiplier = position_multiplier_base * 1.0
    
    else:  # EXCELLENT
        # EXCELLENT: Aggressive positions (except in EXTREME condition)
        entry_precision *= 1.1
        sl_base *= 0.9
        t1_base *= 1.15
        t2_base *= 1.15
        if market_condition == MarketCondition.EXTREME:
            position_multiplier = position_multiplier_base * 1.0  # Don't oversize in EXTREME
        else:
            position_multiplier = position_multiplier_base * 1.25
    
    return MarketClassification(
        condition=market_condition,
        setup_quality=setup_quality,
        entry_precision=round(entry_precision, 1),
        stop_loss_points=round(sl_base, 1),
        target1_points=round(t1_base, 1),
        target2_points=round(t2_base, 1),
        position_size_multiplier=round(position_multiplier, 2),
        atr_ratio=round(atr_ratio, 4),
        volume_ratio=round(volume_ratio, 2),
        market_volatility_pct=round(volatility_pct, 4)
    )


def get_expected_move(
    market_condition: MarketCondition,
    current_price: float
) -> dict:
    """
    Get expected point move for NIFTY and SENSEX based on market condition.
    
    Args:
        market_condition: Market condition
        current_price: Current spot price
    
    Returns:
        Dict with expected moves in points for different instruments
    """
    
    if market_condition == MarketCondition.QUIET:
        return {
            "NIFTY": {"min": 50, "max": 100},
            "SENSEX": {"min": 165, "max": 330},
            "description": "Quiet/Flat market (0.2-0.4%)"
        }
    
    elif market_condition == MarketCondition.NORMAL:
        return {
            "NIFTY": {"min": 150, "max": 230},
            "SENSEX": {"min": 500, "max": 750},
            "description": "Normal/Average market (0.6-0.9%)"
        }
    
    elif market_condition == MarketCondition.HIGH:
        return {
            "NIFTY": {"min": 300, "max": 500},
            "SENSEX": {"min": 1000, "max": 1650},
            "description": "High volatility market (1.2-2.0%)"
        }
    
    else:  # EXTREME
        return {
            "NIFTY": {"min": 630, "max": 1000},
            "SENSEX": {"min": 2000, "max": 3300},
            "description": "Extreme volatility market (2.5%+)"
        }


# Display helper
def format_classification(classification: MarketClassification) -> str:
    """Format classification for display"""
    return f"""
Market Condition: {classification.condition.value} | Setup Quality: {classification.setup_quality.value}
  Entry Precision: ±{classification.entry_precision} pts
  Stop Loss: {classification.stop_loss_points} pts
  Target 1: {classification.target1_points} pts | Target 2: {classification.target2_points} pts
  Position Size: {classification.position_size_multiplier}x
"""
