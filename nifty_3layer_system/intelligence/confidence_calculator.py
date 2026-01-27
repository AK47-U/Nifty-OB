"""
CONFIDENCE CALCULATOR: Maps Scenario + Confluence → Final Confidence Score
Outputs:
- SNIPER (8+): High Conviction - Full Position
- CAUTIONARY (6-7): Medium Conviction - Scalp Only  
- WAIT (<6): Low Conviction - Do Not Trade
"""

from dataclasses import dataclass
from typing import Tuple
from intelligence.scenario_classifier import ScenarioType, ScenarioOutput
from intelligence.confluence_scorer import ConfluenceScore
from loguru import logger


@dataclass
class ConfidenceOutput:
    """Final confidence assessment"""
    confidence_level: str  # "SNIPER", "CAUTIONARY", "WAIT"
    confidence_score: float  # 1-10 scale
    
    # Decision parameters
    trade_decision: str  # "BUY", "SELL", "WAIT"
    position_type: str  # "FULL", "SCALP", "NONE"
    holding_period: str  # "SWING", "SCALP", "NONE"
    risk_level: str  # LOW, MEDIUM, HIGH, EXTREME
    
    # Reasoning
    primary_reason: str
    secondary_reasons: list
    warnings: list
    
    def __str__(self):
        return f"{self.confidence_level} | Score: {self.confidence_score:.1f}/10 | {self.trade_decision}"


class ConfidenceCalculator:
    """
    Synthesizes Scenario + Confluence into Final Confidence Level
    """
    
    def __init__(self):
        self.logger = logger
    
    def calculate(
        self,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        scenario_signal_strength: float = 0.5
    ) -> ConfidenceOutput:
        """
        Calculate final confidence by combining:
        1. Scenario type (highest weight)
        2. Confluence score (confirmation)
        3. Option flow strength
        4. Risk-reward alignment
        
        Args:
            scenario: Output from ScenarioClassifier
            confluence: Output from ConfluenceScorer
            scenario_signal_strength: Raw scenario trigger strength (0-1)
        
        Returns:
            ConfidenceOutput with decision and reasoning
        """
        
        warnings = []
        secondary_reasons = []
        
        # ============ SCENARIO 1: CHOPPY ============
        if scenario.scenario == ScenarioType.CHOPPY:
            confidence, decision, position, holding = 3.0, "WAIT", "NONE", "NONE"
            primary_reason = "Market is directionless (Choppy). CPR is wide, volume is low, MACD is flat."
            secondary_reasons = [
                "No clear trend direction",
                "Risk of whipsaws and false breakouts",
                "Wait for CPR to narrow or clear breakout with volume"
            ]
            warnings = ["AVOID TRADING", "Cash is a position"]
        
        # ============ SCENARIO 2: TREND ============
        elif scenario.scenario == ScenarioType.TREND:
            # High confluence = SNIPER (8+)
            # Medium confluence = CAUTIONARY (6-7)
            # Low confluence = WAIT
            
            if confluence.overall_score >= 7.5:
                # Very high confluence + trend = SNIPER
                confidence = 8.5 + (confluence.overall_score - 7.5) * 0.5
                confidence = min(confidence, 10.0)
                decision = "BUY" if scenario.market_bias == "BULLISH" else "SELL"
                position = "FULL"
                holding = "SWING"
                
                primary_reason = (
                    f"HIGH CONVICTION {scenario.market_bias} TREND: "
                    f"EMA Ribbon aligned + Confluence {confluence.overall_score:.1f}/10 + "
                    f"Institutional positioning detected"
                )
                secondary_reasons = [
                    f"Price > all 6 EMAs (Bullish Fan)" if scenario.market_bias == "BULLISH" else "Price < all 6 EMAs",
                    f"RSI in {scenario.market_bias} zone",
                    f"MACD histogram {'rising' if scenario.market_bias == 'BULLISH' else 'falling'}",
                    f"Call unwinding detected" if scenario.market_bias == "BULLISH" else "Put unwinding detected",
                    f"Level confluence: {confluence.quality_description}"
                ]
                warnings = ["Watch for exhaustion at PDH/R1", "Trail SL on Target 2"]
            
            elif confluence.overall_score >= 5.5:
                # Medium confluence + trend = CAUTIONARY
                confidence = 6.0 + (confluence.overall_score - 5.5) * 0.5
                decision = "BUY" if scenario.market_bias == "BULLISH" else "SELL"
                position = "SCALP"
                holding = "SCALP"
                
                primary_reason = (
                    f"GOOD {scenario.market_bias} SETUP: "
                    f"Trend confirmed but some mixed signals (Confluence: {confluence.overall_score:.1f}/10)"
                )
                secondary_reasons = [
                    "EMA alignment is decent",
                    "Confluence is good but not perfect",
                    "Scalp-friendly R:R, but avoid holding overnight"
                ]
                warnings = [
                    "Exit at Target 1 (100%)",
                    "Do NOT hold for Target 2",
                    "Risk:Reward is 1:1.5-1.8 (acceptable for scalp)"
                ]
            
            else:
                # Low confluence + trend = CAUTION
                confidence = 4.5
                decision = "WAIT"
                position = "NONE"
                holding = "NONE"
                
                primary_reason = (
                    f"Weak {scenario.market_bias} confluence ({confluence.overall_score:.1f}/10). "
                    f"Too many conflicting signals. Better setups available."
                )
                secondary_reasons = [
                    "Trend direction unclear",
                    "Levels not confirming",
                    "Wait for better confluence"
                ]
                warnings = ["AVOID"]
        
        # ============ SCENARIO 3: TRAP ============
        elif scenario.scenario == ScenarioType.TRAP:
            if confluence.overall_score >= 6.5:
                # Good divergence + trap = CAUTIONARY SCALP
                confidence = 6.5
                decision = "SELL" if scenario.market_bias == "BEARISH" else "BUY"
                position = "SCALP"
                holding = "SCALP"
                
                primary_reason = (
                    f"TRAP DETECTED: Price rejected at {scenario.market_bias} extreme "
                    f"(RSI/MACD divergence). Mean reversion scalp opportunity."
                )
                secondary_reasons = [
                    f"Bearish/Bullish divergence strength: {scenario.divergence.divergence_strength:.2f}",
                    "Liquidity trap likely - fast exit needed",
                    "Heavy option writing detected"
                ]
                warnings = [
                    "SCALP ONLY - Exit at Target 1 (100%)",
                    "Tight stop loss (100 ticks from entry)",
                    "Do NOT hold past 3:15 PM"
                ]
            else:
                confidence = 4.5
                decision = "WAIT"
                position = "NONE"
                holding = "NONE"
                
                primary_reason = (
                    f"Trap suspected but weak confluence. "
                    f"Divergence may be false. Wait for confirmation."
                )
                secondary_reasons = [
                    "Weak mean reversion setup",
                    "Better scalping opportunities elsewhere"
                ]
                warnings = ["AVOID for now"]
        
        # ============ SCENARIO 4: VOLATILITY ============
        elif scenario.scenario == ScenarioType.VOLATILITY:
            confidence = 2.0
            decision = "WAIT"
            position = "NONE"
            holding = "NONE"
            
            primary_reason = (
                "EXTREME VOLATILITY: VIX spike, wide spreads, ATR expansion. "
                "IV crush risk is too high. Premiums are erratic."
            )
            secondary_reasons = [
                "Technical levels are being ignored",
                "Theta/IV decay working against long options",
                "Institutional hedging active"
            ]
            warnings = [
                "DO NOT TRADE",
                "Wait for VIX to stabilize",
                "If forced to trade, use tight stops"
            ]
        
        # ============ SCENARIO 5: INSTI-DRIVE ============
        elif scenario.scenario == ScenarioType.INSTI_DRIVE:
            if confluence.overall_score >= 7.0:
                # Strong EOD positioning + good confluence = SNIPER MOMENTUM
                confidence = 8.0 + min((confluence.overall_score - 7.0) * 0.3, 1.0)
                confidence = min(confidence, 9.5)
                decision = "BUY" if scenario.market_bias == "BULLISH" else "SELL"
                position = "FULL"
                holding = "MOMENTUM"
                
                primary_reason = (
                    f"INSTITUTIONAL DRIVE: 3PM+ EOD positioning with OI buildup, "
                    f"volume surge, and {scenario.market_bias} momentum. "
                    f"Confluence {confluence.overall_score:.1f}/10 confirms."
                )
                secondary_reasons = [
                    "Fresh EMA Golden Cross detected",
                    "Massive OI addition in direction",
                    "Volume spike (>150% of 20MA)",
                    "Institutional momentum play - high velocity expected"
                ]
                warnings = [
                    "Use DYNAMIC trailing SL",
                    "Exit before 3:20 PM if taking SCALP",
                    "Hold for Target 2 if BTST conviction (next day opening gap)"
                ]
            else:
                confidence = 5.5
                decision = "SCALP"
                position = "SCALP"
                holding = "SCALP"
                
                primary_reason = (
                    f"EOD momentum setup but weaker confluence. "
                    f"Fast momentum scalp available (confluence: {confluence.overall_score:.1f}/10)."
                )
                secondary_reasons = [
                    "OI building but levels not confirming well",
                    "Scalp-friendly but risky for overnight hold"
                ]
                warnings = [
                    "Exit before close (3:30 PM)",
                    "BTST is risky - take profits"
                ]
        
        # ============ DEFAULT ============
        else:
            confidence = 3.0
            decision = "WAIT"
            position = "NONE"
            holding = "NONE"
            primary_reason = "No clear trading opportunity. Wait for setup."
            secondary_reasons = []
            warnings = ["AVOID"]
        
        # Determine confidence level
        if confidence >= 8:
            conf_level = "SNIPER"
        elif confidence >= 6:
            conf_level = "CAUTIONARY"
        else:
            conf_level = "WAIT"
        
        return ConfidenceOutput(
            confidence_level=conf_level,
            confidence_score=confidence,
            trade_decision=decision,
            position_type=position,
            holding_period=holding,
            risk_level=scenario.risk_level,
            primary_reason=primary_reason,
            secondary_reasons=secondary_reasons,
            warnings=warnings
        )
