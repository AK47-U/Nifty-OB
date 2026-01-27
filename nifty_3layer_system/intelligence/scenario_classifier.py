"""
SCENARIO CLASSIFIER: Intelligent Signal Classification Engine
Dynamically classifies market into 5 scenarios based on LIVE technical analysis
- Scenario 1: CHOPPY (Low Confluence, Wide CPR, Low Volume)
- Scenario 2: TREND (Strong EMA Alignment, Momentum Intact)
- Scenario 3: TRAP (Failed Breakout, Divergence, Liquidity Trap)
- Scenario 4: VOLATILITY (VIX Spike, Wide Spreads, High Risk)
- Scenario 5: INSTI-DRIVE (3PM Drive, OI Buildup, Institutional Flow)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
from loguru import logger
import pandas as pd
from datetime import datetime

class ScenarioType(Enum):
    CHOPPY = "CHOPPY"           # Wait Signal
    TREND = "TREND"             # Execution Signal
    TRAP = "TRAP"               # Reversal Signal
    VOLATILITY = "VOLATILITY"   # Avoid Signal
    INSTI_DRIVE = "INSTI-DRIVE" # Momentum Scalp Signal


@dataclass
class TechnicalContext:
    """Complete technical snapshot for scenario classification"""
    ltp: float
    cpr_pivot: float
    cpr_tc: float
    cpr_bc: float
    cpr_width: float
    pdh: float  # Previous Day High
    pdl: float  # Previous Day Low
    
    # EMA Band (all 6)
    ema_5: float
    ema_12: float
    ema_20: float
    ema_50: float
    ema_100: float
    ema_200: float
    
    # Momentum
    rsi: float
    macd_histogram: float
    macd_signal: float
    macd_line: float
    
    # Volume & Volatility
    volume: float
    volume_20ma: float
    atr: float
    vix: float
    
    # Time context
    current_hour: int
    current_minute: int
    
    # Option Flow
    pcr: float  # Put-Call Ratio
    call_oi_change: int  # Change in Call OI
    put_oi_change: int   # Change in Put OI
    bid_ask_spread: float  # Bid-Ask spread in ticks


@dataclass
class DivergenceSignals:
    """Detects RSI/MACD divergences"""
    rsi_bearish_div: bool = False
    rsi_bullish_div: bool = False
    macd_bearish_div: bool = False
    macd_bullish_div: bool = False
    divergence_strength: float = 0.0  # 0-1 scale


@dataclass
class ScenarioOutput:
    """Scenario classification result"""
    scenario: ScenarioType
    confidence_signal: float  # 0-1 (used by confidence_scorer later)
    primary_trigger: str  # Which condition triggered this scenario
    secondary_triggers: List[str]  # Supporting conditions
    risk_level: str  # Low, Medium, High, Extreme
    action: str  # WAIT, EXECUTE, REVERSAL, AVOID, MOMENTUM_SCALP
    market_bias: str  # BULLISH, BEARISH, NEUTRAL
    divergence: DivergenceSignals
    
    def __str__(self):
        return f"{self.scenario.value} | Risk: {self.risk_level} | Action: {self.action}"


class ScenarioClassifier:
    """
    Dynamic scenario classification based on 5 distinct market conditions
    Each scenario triggers different trading actions
    """
    
    def __init__(self):
        self.logger = logger
        self.rsi_history: List[float] = []
        self.macd_history: List[float] = []
        self.price_history: List[float] = []
        
    def classify(self, context: TechnicalContext) -> ScenarioOutput:
        """
        Main classification function - routes to scenario detector
        
        Args:
            context: Complete technical snapshot
        
        Returns:
            ScenarioOutput with scenario type and reasoning
        """
        # Update history for divergence detection
        self.rsi_history.append(context.rsi)
        self.macd_history.append(context.macd_line)
        self.price_history.append(context.ltp)
        
        # Keep last 30 candles only
        if len(self.rsi_history) > 30:
            self.rsi_history.pop(0)
            self.macd_history.pop(0)
            self.price_history.pop(0)
        
        # Detect divergences
        divergence = self._detect_divergences(context)
        
        # EMA alignment check
        ema_trend = self._analyze_ema_ribbon(context)
        
        # CPR analysis
        cpr_analysis = self._analyze_cpr(context)
        
        # Volume analysis
        volume_analysis = self._analyze_volume(context)
        
        # Option flow analysis
        option_analysis = self._analyze_option_flow(context)
        
        # Time-based context
        is_high_prob_window, is_eod_window = self._check_time_window(context)
        
        # ============ SCENARIO 1: CHOPPY ============
        # Require multiple choppy conditions to avoid over-triggering
        width_pts = cpr_analysis['width']
        wide_cpr_threshold = max(70, 2 * context.atr)
        is_wide_cpr = width_pts > wide_cpr_threshold
        is_low_vol = volume_analysis['is_low'] and volume_analysis['vol_pct'] < 60
        is_flat_macd = abs(context.macd_histogram) < (0.25 * context.atr)
        is_mixed_ema = not ema_trend['aligned']

        choppy_score = 0
        choppy_score += 1 if is_wide_cpr else 0
        choppy_score += 1 if is_low_vol else 0
        choppy_score += 1 if is_flat_macd else 0
        choppy_score += 1 if is_mixed_ema else 0

        if choppy_score >= 3:
            trigger_parts = []
            if is_wide_cpr:
                trigger_parts.append(f"Wide CPR {width_pts:.0f}pts")
            if is_low_vol:
                trigger_parts.append(f"Low Vol {volume_analysis['vol_pct']:.0f}%")
            if is_flat_macd:
                trigger_parts.append("Flat MACD")
            if is_mixed_ema:
                trigger_parts.append("Mixed EMAs")

            primary = "Choppy: " + " + ".join(trigger_parts) if trigger_parts else "Choppy: Mixed signals"

            macd_desc = (
                f"MACD Histogram: {context.macd_histogram:.2f} (near zero)"
                if is_flat_macd
                else f"MACD Histogram: {context.macd_histogram:.2f} (strong)"
            )

            return ScenarioOutput(
                scenario=ScenarioType.CHOPPY,
                confidence_signal=0.3,
                primary_trigger=primary,
                secondary_triggers=[
                    f"Volume {volume_analysis['vol_pct']:.0f}% of 20MA",
                    macd_desc,
                    f"RSI: {context.rsi:.0f} (choppy zone 40-60)"
                ],
                risk_level="Low",
                action="WAIT",
                market_bias="NEUTRAL",
                divergence=divergence
            )
        
        # ============ SCENARIO 2: TREND ============
        if (ema_trend['aligned'] and 
            ema_trend['direction'] == 'BULLISH' and
            context.rsi > 50 and
            context.macd_histogram > 0 and
            not divergence.rsi_bearish_div and
            option_analysis['pcr_signal'] == 'BULLISH'):
            
            return ScenarioOutput(
                scenario=ScenarioType.TREND,
                confidence_signal=0.85,
                primary_trigger=f"EMA Ribbon Aligned ({ema_trend['band']}) + Bullish PCR ({context.pcr:.2f})",
                secondary_triggers=[
                    f"Price > all 6 EMAs (Bullish Fan)",
                    f"RSI: {context.rsi:.0f} (Strong, no divergence)",
                    f"MACD Histogram: {context.macd_histogram:.2f} (Rising)",
                    f"Call Unwinding: {option_analysis['call_unwinding']} contracts"
                ],
                risk_level="Medium",
                action="EXECUTE",
                market_bias="BULLISH",
                divergence=divergence
            )
        
        # ============ SCENARIO 2B: TREND (BEARISH) ============
        if (ema_trend['aligned'] and 
            ema_trend['direction'] == 'BEARISH' and
            context.rsi < 50 and
            context.macd_histogram < 0 and
            not divergence.rsi_bullish_div and
            option_analysis['pcr_signal'] == 'BEARISH'):
            
            return ScenarioOutput(
                scenario=ScenarioType.TREND,
                confidence_signal=0.85,
                primary_trigger=f"EMA Ribbon Aligned ({ema_trend['band']}) + Bearish PCR ({context.pcr:.2f})",
                secondary_triggers=[
                    f"Price < all 6 EMAs (Bearish Fan)",
                    f"RSI: {context.rsi:.0f} (Weak, no divergence)",
                    f"MACD Histogram: {context.macd_histogram:.2f} (Falling)",
                    f"Put Unwinding: {option_analysis['put_unwinding']} contracts"
                ],
                risk_level="Medium",
                action="EXECUTE",
                market_bias="BEARISH",
                divergence=divergence
            )
        
        # ============ SCENARIO 3: TRAP ============
        if ((divergence.rsi_bearish_div or divergence.macd_bearish_div) and
            context.ltp > context.pdh and
            option_analysis['heavy_call_writing'] and
            context.rsi > 68):
            
            return ScenarioOutput(
                scenario=ScenarioType.TRAP,
                confidence_signal=0.75,
                primary_trigger=f"RSI/MACD Divergence + Price rejected at PDH ({context.pdh:.0f})",
                secondary_triggers=[
                    f"Bearish Divergence Strength: {divergence.divergence_strength:.2f}",
                    f"Price above PDH but MACD/RSI declining",
                    f"Heavy Call Writing detected: {option_analysis['call_oi_change']} contracts",
                    f"PCR at neutral {context.pcr:.2f}"
                ],
                risk_level="High",
                action="REVERSAL",
                market_bias="BEARISH",
                divergence=divergence
            )
        
        # ============ SCENARIO 3B: TRAP (BEARISH) ============
        if ((divergence.rsi_bullish_div or divergence.macd_bullish_div) and
            context.ltp < context.pdl and
            option_analysis['heavy_put_writing'] and
            context.rsi < 32):
            
            return ScenarioOutput(
                scenario=ScenarioType.TRAP,
                confidence_signal=0.75,
                primary_trigger=f"RSI/MACD Divergence + Price rejected at PDL ({context.pdl:.0f})",
                secondary_triggers=[
                    f"Bullish Divergence Strength: {divergence.divergence_strength:.2f}",
                    f"Price below PDL but MACD/RSI rising",
                    f"Heavy Put Writing detected: {option_analysis['put_oi_change']} contracts",
                    f"PCR at neutral {context.pcr:.2f}"
                ],
                risk_level="High",
                action="REVERSAL",
                market_bias="BULLISH",
                divergence=divergence
            )
        
        # ============ SCENARIO 4: VOLATILITY ============
        if (context.vix > 15 or 
            context.atr > context.atr * 1.3 or
            context.bid_ask_spread > 5):
            
            return ScenarioOutput(
                scenario=ScenarioType.VOLATILITY,
                confidence_signal=0.2,
                primary_trigger=f"VIX Spike ({context.vix:.1f}) OR Wide Spreads ({context.bid_ask_spread:.0f} ticks)",
                secondary_triggers=[
                    f"ATR: {context.atr:.0f} (Expansion detected)",
                    f"Bid-Ask Spread: {context.bid_ask_spread:.1f} ticks",
                    f"IV Crush Risk: HIGH"
                ],
                risk_level="Extreme",
                action="AVOID",
                market_bias="NEUTRAL",
                divergence=divergence
            )
        
        # ============ SCENARIO 5: INSTI-DRIVE ============
        if (is_eod_window and
            volume_analysis['vol_pct'] > 1.5 and
            ema_trend['aligned'] and
            option_analysis['oi_buildup'] and
            is_high_prob_window):
            
            return ScenarioOutput(
                scenario=ScenarioType.INSTI_DRIVE,
                confidence_signal=0.80,
                primary_trigger=f"3PM EOD Drive + Volume Spike ({volume_analysis['vol_pct']:.0f}% of 20MA) + OI Buildup",
                secondary_triggers=[
                    f"Time: {context.current_hour}:{context.current_minute:02d} (EOD window)",
                    f"Fresh EMA Golden Cross detected",
                    f"Aggressive OI addition: {option_analysis['oi_buildup_qty']} contracts",
                    f"Volume surge: {volume_analysis['vol_pct']:.1f}x average"
                ],
                risk_level="High",
                action="MOMENTUM_SCALP",
                market_bias=ema_trend['direction'],
                divergence=divergence
            )
        
        # ============ DEFAULT: No clear scenario ============
        return ScenarioOutput(
            scenario=ScenarioType.CHOPPY,
            confidence_signal=0.4,
            primary_trigger="No clear scenario detected",
            secondary_triggers=["Mixed signals", "Wait for clearer setup"],
            risk_level="Medium",
            action="WAIT",
            market_bias="NEUTRAL",
            divergence=divergence
        )
    
    def _analyze_ema_ribbon(self, ctx: TechnicalContext) -> Dict:
        """Analyze EMA alignment for trend determination"""
        # Bullish alignment: 5 > 12 > 20 > 50 > 100 > 200
        bullish_count = sum([
            ctx.ema_5 > ctx.ema_12,
            ctx.ema_12 > ctx.ema_20,
            ctx.ema_20 > ctx.ema_50,
            ctx.ema_50 > ctx.ema_100,
            ctx.ema_100 > ctx.ema_200
        ])
        
        # Bearish alignment: 5 < 12 < 20 < 50 < 100 < 200
        bearish_count = sum([
            ctx.ema_5 < ctx.ema_12,
            ctx.ema_12 < ctx.ema_20,
            ctx.ema_20 < ctx.ema_50,
            ctx.ema_50 < ctx.ema_100,
            ctx.ema_100 < ctx.ema_200
        ])
        
        if bullish_count >= 4:
            return {
                'aligned': True,
                'direction': 'BULLISH',
                'strength': bullish_count / 5,
                'band': f"EMA Ribbon Bullish (Price > all 6 EMAs)"
            }
        elif bearish_count >= 4:
            return {
                'aligned': True,
                'direction': 'BEARISH',
                'strength': bearish_count / 5,
                'band': f"EMA Ribbon Bearish (Price < all 6 EMAs)"
            }
        else:
            return {
                'aligned': False,
                'direction': 'MIXED',
                'strength': 0,
                'band': f"No clear alignment"
            }
    
    def _analyze_cpr(self, ctx: TechnicalContext) -> Dict:
        """Analyze CPR levels and zones"""
        return {
            'width': ctx.cpr_tc - ctx.cpr_bc,
            'pivot': ctx.cpr_pivot,
            'tc': ctx.cpr_tc,
            'bc': ctx.cpr_bc,
            'price_in_cpr': ctx.cpr_bc <= ctx.ltp <= ctx.cpr_tc
        }
    
    def _analyze_volume(self, ctx: TechnicalContext) -> Dict:
        """Analyze volume against 20MA"""
        vol_pct = (ctx.volume / ctx.volume_20ma) * 100 if ctx.volume_20ma > 0 else 0
        
        return {
            'current': ctx.volume,
            'vol_20ma': ctx.volume_20ma,
            'vol_pct': vol_pct,
            'is_low': vol_pct < 60,
            'is_spike': vol_pct > 150
        }
    
    def _analyze_option_flow(self, ctx: TechnicalContext) -> Dict:
        """Analyze PCR and OI changes for institutional flow"""
        # PCR signals
        if ctx.pcr > 1.2:
            pcr_signal = 'BULLISH'  # More puts = fear = buy dip
        elif ctx.pcr < 0.8:
            pcr_signal = 'BEARISH'  # More calls = greed = sell strength
        else:
            pcr_signal = 'NEUTRAL'
        
        # OI buildup detection
        call_unwinding = ctx.call_oi_change < -10000
        put_unwinding = ctx.put_oi_change < -10000
        oi_buildup = abs(ctx.call_oi_change) > 50000 or abs(ctx.put_oi_change) > 50000
        
        return {
            'pcr': ctx.pcr,
            'pcr_signal': pcr_signal,
            'call_oi_change': ctx.call_oi_change,
            'put_oi_change': ctx.put_oi_change,
            'call_unwinding': abs(ctx.call_oi_change) if call_unwinding else 0,
            'put_unwinding': abs(ctx.put_oi_change) if put_unwinding else 0,
            'heavy_call_writing': ctx.call_oi_change > 50000,
            'heavy_put_writing': ctx.put_oi_change > 50000,
            'oi_buildup': oi_buildup,
            'oi_buildup_qty': max(abs(ctx.call_oi_change), abs(ctx.put_oi_change))
        }
    
    def _check_time_window(self, ctx: TechnicalContext) -> Tuple[bool, bool]:
        """Check if we're in high-probability trading windows"""
        hour = ctx.current_hour
        minute = ctx.current_minute
        
        # High-probability windows
        high_prob = (9 <= hour < 11) or (13 <= hour < 15)  # 9:15-11:00 & 13:30-15:00
        eod_window = (14 <= hour < 15 and 30 <= minute)  # 3:30 PM onwards
        
        return high_prob, eod_window
    
    def _detect_divergences(self, ctx: TechnicalContext) -> DivergenceSignals:
        """Detect RSI and MACD divergences from price"""
        divergence = DivergenceSignals()
        
        if len(self.rsi_history) < 5 or len(self.price_history) < 5:
            return divergence  # Not enough data
        
        # Bearish divergence: Price makes higher high, RSI makes lower high
        if (self.price_history[-1] > self.price_history[-3] and
            self.rsi_history[-1] < self.rsi_history[-3]):
            divergence.rsi_bearish_div = True
            divergence.divergence_strength = 0.7
        
        # Bullish divergence: Price makes lower low, RSI makes higher low
        if (self.price_history[-1] < self.price_history[-3] and
            self.rsi_history[-1] > self.rsi_history[-3]):
            divergence.rsi_bullish_div = True
            divergence.divergence_strength = 0.7
        
        # MACD divergences (similar logic)
        if (self.price_history[-1] > self.price_history[-3] and
            self.macd_history[-1] < self.macd_history[-3]):
            divergence.macd_bearish_div = True
            divergence.divergence_strength = max(divergence.divergence_strength, 0.6)
        
        if (self.price_history[-1] < self.price_history[-3] and
            self.macd_history[-1] > self.macd_history[-3]):
            divergence.macd_bullish_div = True
            divergence.divergence_strength = max(divergence.divergence_strength, 0.6)
        
        return divergence
