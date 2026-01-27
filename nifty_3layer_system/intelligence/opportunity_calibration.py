#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPPORTUNITY CALIBRATION ENGINE
Answers: "How confidently can we capture exactly 50 points in the next 15-30 minutes?"
Not about trend direction - pure probability of hitting the target move.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time as dtime
from dataclasses import dataclass
from typing import Tuple


@dataclass
class OpportunityMetrics:
    """Confidence breakdown for 50-point capture"""
    volatility_score: float          # Is ATR sufficient for 50pts? (0-100)
    volume_sustain_score: float      # Can volume maintain the move? (0-100)
    time_of_day_score: float         # Is this a high-momentum hour? (0-100)
    location_score: float            # How far to 50pt target? (0-100)
    momentum_score: float            # Is market already moving? (0-100)
    candle_acceleration_score: float # Are candles getting bigger? (0-100)
    
    overall_confidence: float        # Final: % confident for 50pts in 15-30min (0-100)
    
    def __str__(self):
        msg = f"═══ 50-POINT CAPTURE OPPORTUNITY ═══\n"
        msg += f"Volatility (ATR):      {self.volatility_score:5.1f}%\n"
        msg += f"Volume Sustain:        {self.volume_sustain_score:5.1f}%\n"
        msg += f"Time of Day:           {self.time_of_day_score:5.1f}%\n"
        msg += f"Price Location:        {self.location_score:5.1f}%\n"
        msg += f"Current Momentum:      {self.momentum_score:5.1f}%\n"
        msg += f"Candle Acceleration:   {self.candle_acceleration_score:5.1f}%\n"
        msg += f"───────────────────────────────────\n"
        msg += f"🎯 OVERALL CONFIDENCE: {self.overall_confidence:.1f}% (50pts in 15-30min)\n"
        
        # Grade interpretation
        if self.overall_confidence >= 80:
            msg += f"   Rating: ⭐⭐⭐⭐⭐ EXCELLENT OPPORTUNITY"
        elif self.overall_confidence >= 70:
            msg += f"   Rating: ⭐⭐⭐⭐ VERY GOOD OPPORTUNITY"
        elif self.overall_confidence >= 60:
            msg += f"   Rating: ⭐⭐⭐ GOOD OPPORTUNITY"
        elif self.overall_confidence >= 50:
            msg += f"   Rating: ⭐⭐ MODERATE OPPORTUNITY"
        else:
            msg += f"   Rating: ⭐ POOR OPPORTUNITY - WAIT FOR BETTER SETUP"
        
        return msg


class OpportunityCalibration:
    """
    Calibrates confidence specifically for capturing 50 points in 15-30 minutes.
    This is NOT about direction, but pure probability of hitting the target move.
    """
    
    TARGET_POINTS = 50  # Always aiming for this
    TARGET_TIMEFRAME_MIN = 15
    TARGET_TIMEFRAME_MAX = 30
    
    def __init__(self, intraday_candles: pd.DataFrame, atr_value: float,
                 current_price: float, volume_ratio: float, direction: str = "UNKNOWN"):
        """
        Args:
            intraday_candles: 5-min OHLCV dataframe
            atr_value: Current ATR (14-period)
            current_price: Current LTP
            volume_ratio: Current vol / 20-period avg vol
            direction: "BULLISH", "BEARISH", or "UNKNOWN" (for opportunistic trades)
        """
        self.candles = intraday_candles.copy()
        self.candles.columns = self.candles.columns.str.lower()
        self.atr = atr_value
        self.ltp = current_price
        self.vol_ratio = volume_ratio
        self.direction = direction
        
        self._now = datetime.now()
    
    def calculate(self) -> OpportunityMetrics:
        """Master calculation: return confidence for 50-point capture"""
        
        vol_score = self._score_volatility()
        vol_sustain_score = self._score_volume_sustain()
        time_score = self._score_time_of_day()
        location_score = self._score_price_location()
        momentum_score = self._score_current_momentum()
        accel_score = self._score_candle_acceleration()
        
        # Weighted average (all factors equally important for raw opportunity)
        weights = [0.20, 0.15, 0.15, 0.15, 0.20, 0.15]  # vol, vol_sustain, time, location, momentum, accel
        overall = (
            vol_score * weights[0] +
            vol_sustain_score * weights[1] +
            time_score * weights[2] +
            location_score * weights[3] +
            momentum_score * weights[4] +
            accel_score * weights[5]
        )
        
        return OpportunityMetrics(
            volatility_score=vol_score,
            volume_sustain_score=vol_sustain_score,
            time_of_day_score=time_score,
            location_score=location_score,
            momentum_score=momentum_score,
            candle_acceleration_score=accel_score,
            overall_confidence=overall
        )
    
    def _score_volatility(self) -> float:
        """
        Is current ATR sufficient to move 50 points in 15-30 minutes?
        ATR is a 14-period gauge of typical daily movement.
        
        For 50pts in 15-30min:
        - If ATR >= 50: 100% (highly volatile)
        - If ATR == 35: ~70% (moderate volatility, doable)
        - If ATR == 20: ~30% (low volatility, hard)
        - If ATR < 10: 5% (insufficient)
        """
        if self.atr < 10:
            return 5.0
        elif self.atr >= 50:
            return 100.0
        else:
            # Linear scaling: ATR 10-50 → confidence 5-100
            return 5.0 + (self.atr - 10) * (95.0 / 40.0)
    
    def _score_volume_sustain(self) -> float:
        """
        Can volume sustain the 50-point move without exhausting?
        
        - Volume ratio >= 1.2x: 90% (strong buying/selling power)
        - Volume ratio 0.8-1.2x: 70% (normal, sustainable)
        - Volume ratio 0.5-0.8x: 40% (weak, may reverse quickly)
        - Volume ratio < 0.5x: 10% (critical weakness)
        """
        if self.vol_ratio < 0.5:
            return 10.0
        elif self.vol_ratio < 0.8:
            return 40.0
        elif self.vol_ratio < 1.2:
            return 70.0
        else:
            return min(95.0, 90.0 + (self.vol_ratio - 1.2) * 10)
    
    def _score_time_of_day(self) -> float:
        """
        Which hour of the trading day is it? Some hours have higher volatility.
        
        IST times:
        - 09:15-09:45: HIGH (gap fill, opening momentum) → 85%
        - 10:00-11:00: MEDIUM-HIGH (post-open, trend establishment) → 75%
        - 11:00-13:00: MEDIUM (mid-day, moderate volatility) → 60%
        - 13:00-14:30: MEDIUM (lunch time, variable) → 55%
        - 14:30-15:00: HIGH (pre-close, institutional moves) → 80%
        - 15:00-15:30: VERY HIGH (final hour, close positioning) → 90%
        """
        now = self._now.time()
        
        if dtime(9, 15) <= now < dtime(9, 45):
            return 85.0
        elif dtime(9, 45) <= now < dtime(11, 0):
            return 75.0
        elif dtime(11, 0) <= now < dtime(13, 0):
            return 60.0
        elif dtime(13, 0) <= now < dtime(14, 30):
            return 55.0
        elif dtime(14, 30) <= now < dtime(15, 0):
            return 80.0
        elif dtime(15, 0) <= now < dtime(15, 30):
            return 90.0
        else:
            return 20.0  # Market closed
    
    def _score_price_location(self) -> float:
        """
        How far is current price from the 50-point target?
        Closer = higher probability (less distance to cover).
        
        Logic: 50 points away is 100% distance to target
        - At entry (0 pts away): 100% confidence
        - 10 pts away from target: 95%
        - 25 pts away from target: 85%
        - 50 pts away from target: 60% (maximum distance, hardest)
        
        Since we don't know entry yet, use CPR/Support levels as reference.
        """
        if len(self.candles) < 5:
            return 50.0  # Default if insufficient data
        
        # Get recent high and low to estimate volatility location
        recent_high = self.candles['high'].iloc[-5:].max()
        recent_low = self.candles['low'].iloc[-5:].min()
        recent_range = recent_high - recent_low
        
        # If price is in upper part of range and we're bullish: need to go higher
        # If price is in lower part of range and we're bearish: need to go lower
        # Location score reflects: how much room is left?
        
        upper_bound = recent_high + self.TARGET_POINTS
        lower_bound = recent_low - self.TARGET_POINTS
        
        # Price closer to middle of range = higher confidence (more room)
        price_pct_in_range = (self.ltp - recent_low) / (recent_range + 1e-6)
        
        if price_pct_in_range < 0.2 or price_pct_in_range > 0.8:
            # At extremes: harder to move 50 more points
            return 50.0
        else:
            # In middle: more room to move
            return 75.0
    
    def _score_current_momentum(self) -> float:
        """
        Is the market already moving in the expected direction?
        Recent candle momentum accelerates the 50-point capture.
        
        - Last 3 candles all green (bullish) or all red (bearish): 85% (strong momentum)
        - Majority direction (2 of 3): 70% (moderate momentum)
        - Mixed (1-1-1): 50% (no clear momentum)
        - Opposite to expected: 30% (headwind)
        """
        if len(self.candles) < 3:
            return 50.0
        
        last_3 = self.candles.tail(3)
        bullish_count = sum(1 for idx, row in last_3.iterrows() if row['close'] > row['open'])
        
        if bullish_count == 3:
            momentum_val = 85.0 if self.direction == "BULLISH" else 45.0
        elif bullish_count == 2:
            momentum_val = 70.0 if self.direction == "BULLISH" else 50.0
        elif bullish_count == 1:
            momentum_val = 50.0
        else:  # 0 bullish candles = all bearish
            momentum_val = 45.0 if self.direction == "BULLISH" else 85.0
        
        return momentum_val
    
    def _score_candle_acceleration(self) -> float:
        """
        Are candles getting bigger (acceleration) or smaller (deceleration)?
        Bigger candles = market is speeding up = higher chance of 50pt in next 15-30min.
        
        Compare last 3 candles to previous 3 candles:
        - Last avg > Previous avg by 20%+: 85% (acceleration)
        - Last avg > Previous avg by 5-20%: 70% (slight acceleration)
        - Last avg ≈ Previous avg: 60% (steady)
        - Last avg < Previous avg by 5-20%: 40% (slight deceleration)
        - Last avg < Previous avg by 20%+: 20% (strong deceleration, losing steam)
        """
        if len(self.candles) < 6:
            return 50.0  # Default
        
        # Get last 3 and previous 3 candles
        last_3 = self.candles.tail(3)
        prev_3 = self.candles.iloc[-6:-3]
        
        # Calculate average candle size (high - low)
        last_3_sizes = (last_3['high'] - last_3['low']).values
        prev_3_sizes = (prev_3['high'] - prev_3['low']).values
        
        last_avg = np.mean(last_3_sizes)
        prev_avg = np.mean(prev_3_sizes)
        
        if prev_avg == 0:
            return 50.0
        
        pct_change = ((last_avg - prev_avg) / prev_avg) * 100
        
        if pct_change >= 20:
            return 85.0
        elif pct_change >= 5:
            return 70.0
        elif pct_change >= -5:
            return 60.0
        elif pct_change >= -20:
            return 40.0
        else:
            return 20.0
    
    def get_opportunity_window(self) -> Tuple[float, float]:
        """
        Returns (start_time, end_time) of the next 15-30 min window in minutes from now.
        Used for: "Check this opportunity in X-Y minutes from now"
        """
        return (self.TARGET_TIMEFRAME_MIN, self.TARGET_TIMEFRAME_MAX)
    
    def get_recommendation(self, confidence: float) -> str:
        """
        Trading recommendation based on 50-point capture confidence.
        """
        if confidence >= 85:
            return "🟢 EXECUTE: Excellent setup for 50pt capture - trade immediately"
        elif confidence >= 75:
            return "🟢 EXECUTE: Good setup for 50pt capture - proceed with full size"
        elif confidence >= 65:
            return "🟡 EXECUTE with CAUTION: Decent setup - use half size, tight SL"
        elif confidence >= 55:
            return "🟡 CONSIDER: Moderate setup - only if high conviction direction, use small size"
        elif confidence >= 45:
            return "⚠️  WAIT: Below-average setup - better opportunities coming, skip this one"
        else:
            return "🔴 SKIP: Poor setup - insufficient volatility/volume/momentum for 50pts"
