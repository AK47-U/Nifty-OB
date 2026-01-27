"""
CONFLUENCE SCORER: Dynamic Confluence Analysis Engine
Calculates 1-10 confluence score based on:
- How many technical factors align at current price
- Level quality (Monthly + CPR + PDH/PDL overlap)
- Indicator alignment (EMAs, RSI, MACD)
- Option flow agreement (PCR, OI direction)
- Volume + Volatility confirmation
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from loguru import logger
import math


@dataclass
class ConfluenceFactors:
    """Individual confluence factors scored 0-1"""
    # Level factors
    at_monthly_level: float = 0.0       # Is price at monthly file level?
    cpr_alignment: float = 0.0          # Is CPR element (TC/Pivot/BC) nearby?
    pdh_pdl_proximity: float = 0.0      # Is price near PDH/PDL?
    level_overlap: float = 0.0          # Multiple levels align (Monthly=CPR=PDH)?
    
    # Trend factors
    ema_5_12_20_alignment: float = 0.0  # Short-term EMA alignment
    ema_50_100_200_alignment: float = 0.0  # Long-term trend
    price_above_200ema: float = 0.0     # Price > 200 EMA (bullish anchor)
    price_overextension: float = 0.0    # Price too far from 200 EMA? (risky)
    
    # Momentum factors
    rsi_in_trend_zone: float = 0.0      # RSI in strong zone (>60 for bullish)
    macd_positive_divergence: float = 0.0  # MACD histogram aligned with trend
    no_rsi_divergence: float = 0.0      # No bearish divergence
    no_macd_divergence: float = 0.0     # No bearish MACD divergence
    
    # Volume factors
    volume_above_20ma: float = 0.0      # Volume confirmation
    volume_surge: float = 0.0           # Volume spike detected
    
    # Option flow factors
    pcr_aligned: float = 0.0            # PCR matches direction
    oi_buildup: float = 0.0             # OI adding up in direction
    call_unwinding: float = 0.0         # Call unwinding (bullish) or put
    
    # Time factors
    high_prob_window: float = 0.0       # Trading during 9:15-11:00 or 2:30-3:30
    post_eod_setup: float = 0.0         # EOD institutional positioning
    
    def to_list(self) -> List[float]:
        """Convert all factors to a list for averaging"""
        return [
            self.at_monthly_level,
            self.cpr_alignment,
            self.pdh_pdl_proximity,
            self.level_overlap,
            self.ema_5_12_20_alignment,
            self.ema_50_100_200_alignment,
            self.price_above_200ema,
            self.price_overextension,
            self.rsi_in_trend_zone,
            self.macd_positive_divergence,
            self.no_rsi_divergence,
            self.no_macd_divergence,
            self.volume_above_20ma,
            self.volume_surge,
            self.pcr_aligned,
            self.oi_buildup,
            self.call_unwinding,
            self.high_prob_window,
            self.post_eod_setup
        ]


@dataclass
class ConfluenceScore:
    """Final confluence score output"""
    overall_score: float  # 1-10
    score_breakdown: Dict[str, float]  # Each category's contribution
    factors: ConfluenceFactors
    interpretation: str  # Human-readable interpretation
    quality_description: str  # Is it WEAK, GOOD, STRONG, VERY_STRONG?
    
    def __str__(self):
        return f"Confluence: {self.overall_score:.1f}/10 ({self.quality_description})"


class ConfluenceScorer:
    """
    Dynamically calculates confluence score based on multiple technical factors
    Scores each factor 0-1, then synthesizes into 1-10 scale
    """
    
    def __init__(self, monthly_levels: List[float] = None):
        """
        Initialize scorer with optional monthly levels
        
        Args:
            monthly_levels: List of support/resistance levels from monthly file
        """
        self.monthly_levels = monthly_levels or []
        self.logger = logger
        self.tolerance_pct = 0.05  # 0.05% tolerance for level proximity
    
    def score(
        self,
        ltp: float,
        cpr_pivot: float,
        cpr_tc: float,
        cpr_bc: float,
        pdh: float,
        pdl: float,
        ema_5: float,
        ema_12: float,
        ema_20: float,
        ema_50: float,
        ema_100: float,
        ema_200: float,
        rsi: float,
        macd_histogram: float,
        macd_line: float,
        volume: float,
        volume_20ma: float,
        pcr: float,
        call_oi_change: int,
        put_oi_change: int,
        bid_ask_spread: float,
        rsi_divergence_strength: float = 0.0,
        macd_divergence_strength: float = 0.0,
        trend_bias: str = "NEUTRAL",  # BULLISH, BEARISH, NEUTRAL
        in_high_prob_window: bool = False,
        in_eod_window: bool = False
    ) -> ConfluenceScore:
        """
        Calculate dynamic confluence score (1-10)
        
        Args:
            All technical indicators and context
            trend_bias: Expected direction (BULLISH/BEARISH/NEUTRAL)
        
        Returns:
            ConfluenceScore with breakdown
        """
        factors = ConfluenceFactors()
        
        # ===== LEVEL FACTORS (Most Important) =====
        
        # 1. At Monthly Level?
        factors.at_monthly_level = self._proximity_to_monthly_levels(ltp)
        
        # 2. CPR Alignment
        factors.cpr_alignment = self._proximity_to_cpr(ltp, cpr_pivot, cpr_tc, cpr_bc)
        
        # 3. PDH/PDL Proximity
        factors.pdh_pdl_proximity = self._proximity_to_pdh_pdl(ltp, pdh, pdl)
        
        # 4. Level Overlap (Multiple levels at same price)
        factors.level_overlap = self._detect_level_confluence(
            ltp, cpr_pivot, cpr_tc, cpr_bc, pdh, pdl
        )
        
        # ===== TREND FACTORS =====
        
        # 5. Short-term EMA alignment (5, 12, 20)
        factors.ema_5_12_20_alignment = self._ema_short_term_alignment(
            ltp, ema_5, ema_12, ema_20, trend_bias
        )
        
        # 6. Long-term EMA alignment (50, 100, 200)
        factors.ema_50_100_200_alignment = self._ema_long_term_alignment(
            ltp, ema_50, ema_100, ema_200, trend_bias
        )
        
        # 7. Price above/below 200 EMA (Structural alignment)
        if trend_bias == "BULLISH":
            factors.price_above_200ema = 1.0 if ltp > ema_200 else 0.5
        elif trend_bias == "BEARISH":
            factors.price_above_200ema = 1.0 if ltp < ema_200 else 0.5
        else:
            factors.price_above_200ema = 0.5
        
        # 8. Price overextension (Too far from 200 EMA = risky)
        distance_from_200ema = abs(ltp - ema_200)
        atr_proxy = distance_from_200ema * 0.05  # Rough ATR proxy
        if distance_from_200ema > atr_proxy * 2:  # 2x ATR away = overextended
            factors.price_overextension = 0.2  # Reduce score (risky)
        else:
            factors.price_overextension = 0.8  # Normal distance
        
        # ===== MOMENTUM FACTORS =====
        
        # 9. RSI in trend zone
        if trend_bias == "BULLISH":
            if rsi > 60:
                factors.rsi_in_trend_zone = 1.0  # Strong
            elif rsi > 50:
                factors.rsi_in_trend_zone = 0.8  # Good
            else:
                factors.rsi_in_trend_zone = 0.3  # Weak for uptrend
        elif trend_bias == "BEARISH":
            if rsi < 40:
                factors.rsi_in_trend_zone = 1.0  # Strong
            elif rsi < 50:
                factors.rsi_in_trend_zone = 0.8  # Good
            else:
                factors.rsi_in_trend_zone = 0.3  # Weak for downtrend
        else:
            factors.rsi_in_trend_zone = 0.5 if 40 <= rsi <= 60 else 0.3
        
        # 10. MACD histogram positive/negative (matches direction)
        if trend_bias == "BULLISH":
            factors.macd_positive_divergence = 1.0 if macd_histogram > 0 else 0.3
        elif trend_bias == "BEARISH":
            factors.macd_positive_divergence = 1.0 if macd_histogram < 0 else 0.3
        else:
            factors.macd_positive_divergence = 0.5
        
        # 11. No RSI divergence
        factors.no_rsi_divergence = 1.0 - rsi_divergence_strength
        
        # 12. No MACD divergence
        factors.no_macd_divergence = 1.0 - macd_divergence_strength
        
        # ===== VOLUME FACTORS =====
        
        # 13. Volume above 20MA
        vol_ratio = volume / volume_20ma if volume_20ma > 0 else 1
        if vol_ratio > 1.0:
            factors.volume_above_20ma = min(1.0, vol_ratio / 1.5)
        else:
            factors.volume_above_20ma = 0.5
        
        # 14. Volume spike (>150% of 20MA)
        if vol_ratio > 1.5:
            factors.volume_surge = 1.0
        elif vol_ratio > 1.2:
            factors.volume_surge = 0.7
        else:
            factors.volume_surge = 0.3
        
        # ===== OPTION FLOW FACTORS =====
        
        # 15. PCR aligned with direction
        if trend_bias == "BULLISH":
            factors.pcr_aligned = 1.0 if pcr > 1.2 else (0.5 if pcr > 0.9 else 0.2)
        elif trend_bias == "BEARISH":
            factors.pcr_aligned = 1.0 if pcr < 0.8 else (0.5 if pcr < 1.1 else 0.2)
        else:
            factors.pcr_aligned = 0.5
        
        # 16. OI buildup in direction
        if trend_bias == "BULLISH":
            factors.oi_buildup = 1.0 if call_oi_change > 10000 else (0.5 if call_oi_change > 0 else 0.2)
        elif trend_bias == "BEARISH":
            factors.oi_buildup = 1.0 if put_oi_change > 10000 else (0.5 if put_oi_change > 0 else 0.2)
        else:
            factors.oi_buildup = 0.5
        
        # 17. Call/Put unwinding (institutional exit)
        if trend_bias == "BULLISH" and call_oi_change < -10000:
            factors.call_unwinding = 1.0  # Calls being unwound = bullish
        elif trend_bias == "BEARISH" and put_oi_change < -10000:
            factors.call_unwinding = 1.0  # Puts being unwound = bearish
        else:
            factors.call_unwinding = 0.5
        
        # ===== TIME FACTORS =====
        
        # 18. High probability window (9:15-11:00, 2:30-3:30)
        factors.high_prob_window = 1.0 if in_high_prob_window else 0.5
        
        # 19. Post-EOD setup (3PM+ institutional drive)
        factors.post_eod_setup = 1.0 if in_eod_window else 0.5
        
        # ===== SYNTHESIZE SCORE =====
        
        # Weight factors by importance
        weights = {
            'level_factors': 0.25,      # Levels are primary (25%)
            'trend_factors': 0.25,      # Trend confirmation (25%)
            'momentum_factors': 0.20,   # Momentum health (20%)
            'flow_factors': 0.15,       # Option flow (15%)
            'volume_time_factors': 0.15 # Volume + Time (15%)
        }
        
        level_score = (factors.at_monthly_level + factors.cpr_alignment + 
                      factors.pdh_pdl_proximity + factors.level_overlap) / 4
        
        trend_score = (factors.ema_5_12_20_alignment + factors.ema_50_100_200_alignment +
                      factors.price_above_200ema + factors.price_overextension) / 4
        
        momentum_score = (factors.rsi_in_trend_zone + factors.macd_positive_divergence +
                         factors.no_rsi_divergence + factors.no_macd_divergence) / 4
        
        flow_score = (factors.pcr_aligned + factors.oi_buildup + 
                     factors.call_unwinding) / 3
        
        volume_time_score = (factors.volume_above_20ma + factors.volume_surge +
                            factors.high_prob_window + factors.post_eod_setup) / 4
        
        overall = (
            level_score * weights['level_factors'] +
            trend_score * weights['trend_factors'] +
            momentum_score * weights['momentum_factors'] +
            flow_score * weights['flow_factors'] +
            volume_time_score * weights['volume_time_factors']
        )
        
        # Convert 0-1 to 1-10 scale
        confluence_1_to_10 = 1 + (overall * 9)
        
        # Determine quality
        if confluence_1_to_10 >= 8.5:
            quality = "VERY_STRONG"
        elif confluence_1_to_10 >= 7:
            quality = "STRONG"
        elif confluence_1_to_10 >= 5.5:
            quality = "GOOD"
        elif confluence_1_to_10 >= 4:
            quality = "WEAK"
        else:
            quality = "VERY_WEAK"
        
        interpretation = self._generate_interpretation(confluence_1_to_10, factors, trend_bias)
        
        return ConfluenceScore(
            overall_score=confluence_1_to_10,
            score_breakdown={
                'level_factors': level_score,
                'trend_factors': trend_score,
                'momentum_factors': momentum_score,
                'flow_factors': flow_score,
                'volume_time_score': volume_time_score
            },
            factors=factors,
            interpretation=interpretation,
            quality_description=quality
        )
    
    def _proximity_to_monthly_levels(self, ltp: float) -> float:
        """Check proximity to monthly file levels"""
        if not self.monthly_levels:
            return 0.0
        
        min_distance_pct = min([abs(ltp - level) / ltp * 100 for level in self.monthly_levels])
        
        if min_distance_pct < self.tolerance_pct:
            return 1.0
        elif min_distance_pct < self.tolerance_pct * 3:
            return 0.8
        elif min_distance_pct < self.tolerance_pct * 5:
            return 0.5
        else:
            return 0.0
    
    def _proximity_to_cpr(self, ltp: float, pivot: float, tc: float, bc: float) -> float:
        """Check if price is at CPR levels"""
        cpr_width = tc - bc
        tolerance = cpr_width * 0.05
        
        # Exact CPR elements
        if abs(ltp - pivot) < tolerance:
            return 1.0  # At pivot
        elif abs(ltp - tc) < tolerance:
            return 0.9  # At TC
        elif abs(ltp - bc) < tolerance:
            return 0.9  # At BC
        elif bc <= ltp <= tc:
            return 0.6  # Inside CPR
        else:
            return 0.2
    
    def _proximity_to_pdh_pdl(self, ltp: float, pdh: float, pdl: float) -> float:
        """Check proximity to PDH/PDL"""
        range_size = pdh - pdl
        tolerance = range_size * 0.02
        
        if abs(ltp - pdh) < tolerance:
            return 1.0
        elif abs(ltp - pdl) < tolerance:
            return 1.0
        elif abs(ltp - pdh) < tolerance * 3:
            return 0.7
        elif abs(ltp - pdl) < tolerance * 3:
            return 0.7
        else:
            return 0.2
    
    def _detect_level_confluence(self, ltp: float, cpr_pivot: float, cpr_tc: float, 
                                  cpr_bc: float, pdh: float, pdl: float) -> float:
        """
        Detect MULTIPLE levels at same price (Maximum Confluence)
        If Monthly Level = CPR Pivot = PDH, score is HIGH
        """
        tolerance = 50  # 50 points tolerance
        
        levels_aligned = []
        if abs(ltp - cpr_pivot) < tolerance:
            levels_aligned.append("pivot")
        if abs(ltp - cpr_tc) < tolerance:
            levels_aligned.append("tc")
        if abs(ltp - cpr_bc) < tolerance:
            levels_aligned.append("bc")
        if abs(ltp - pdh) < tolerance:
            levels_aligned.append("pdh")
        if abs(ltp - pdl) < tolerance:
            levels_aligned.append("pdl")
        
        # Score based on how many levels overlap
        if len(levels_aligned) >= 3:
            return 1.0  # Super confluence
        elif len(levels_aligned) >= 2:
            return 0.8
        elif len(levels_aligned) >= 1:
            return 0.6
        else:
            return 0.2
    
    def _ema_short_term_alignment(self, ltp: float, ema_5: float, ema_12: float, 
                                   ema_20: float, trend_bias: str) -> float:
        """Score short-term EMA alignment"""
        if trend_bias == "BULLISH":
            if ema_5 > ema_12 > ema_20 and ltp > ema_5:
                return 1.0
            elif ema_5 > ema_12 > ema_20:
                return 0.8
            elif ema_5 > ema_12:
                return 0.5
            else:
                return 0.2
        elif trend_bias == "BEARISH":
            if ema_5 < ema_12 < ema_20 and ltp < ema_5:
                return 1.0
            elif ema_5 < ema_12 < ema_20:
                return 0.8
            elif ema_5 < ema_12:
                return 0.5
            else:
                return 0.2
        else:
            return 0.5
    
    def _ema_long_term_alignment(self, ltp: float, ema_50: float, ema_100: float, 
                                  ema_200: float, trend_bias: str) -> float:
        """Score long-term EMA alignment"""
        if trend_bias == "BULLISH":
            if ema_50 > ema_100 > ema_200:
                return 1.0
            elif ema_50 > ema_100 or ema_100 > ema_200:
                return 0.6
            else:
                return 0.2
        elif trend_bias == "BEARISH":
            if ema_50 < ema_100 < ema_200:
                return 1.0
            elif ema_50 < ema_100 or ema_100 < ema_200:
                return 0.6
            else:
                return 0.2
        else:
            return 0.5
    
    def _generate_interpretation(self, score: float, factors: ConfluenceFactors, 
                                  trend_bias: str) -> str:
        """Generate human-readable interpretation"""
        if score >= 8.5:
            return f"VERY STRONG {trend_bias} CONFLUENCE: Multiple factors aligned perfectly. High probability setup."
        elif score >= 7:
            return f"STRONG {trend_bias} SETUP: Key levels + indicators confirm direction. Good R:R opportunity."
        elif score >= 5.5:
            return f"GOOD SETUP: Decent confluence, but some conflicting signals. Proceed with caution."
        elif score >= 4:
            return f"WEAK SETUP: Mixed signals. Better opportunities likely elsewhere."
        else:
            return f"VERY WEAK: Avoid trading. Wait for clearer setup."
