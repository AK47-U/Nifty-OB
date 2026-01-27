"""
COPILOT FORMATTER: Renders Trading Recommendations in Sniper Format
Outputs human-friendly AI COPILOT recommendations:
- 🎯 SNIPER: High Conviction (8+)
- ⚠️ CAUTIONARY: Medium Conviction (6-7)
- 🚫 WAIT: Low Conviction (<6)
"""

from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
from intelligence.scenario_classifier import ScenarioOutput
from intelligence.confluence_scorer import ConfluenceScore
from intelligence.confidence_calculator import ConfidenceOutput
from loguru import logger


@dataclass
class CopilotRecommendation:
    """Complete copilot trading recommendation"""
    timestamp: datetime
    confidence_output: ConfidenceOutput
    scenario: ScenarioOutput
    confluence: ConfluenceScore
    
    # Trade specifics
    entry_price: float
    strike_suggestion: int
    side: str  # CALL or PUT
    
    # Levels
    ltp: float
    upside_barrier: float
    downside_floor: float
    key_support: float
    
    # Risk management
    stop_loss: float
    target_1: float
    target_2: Optional[float]
    risk_per_contract: float
    max_profit_t1: float
    max_profit_t2: Optional[float]
    risk_reward_1: float
    risk_reward_2: Optional[float]
    
    # Strategy
    quantity: int
    exit_plan: str


class CopilotFormatter:
    """
    Formats technical analysis + scenarios into human-friendly AI copilot output
    """
    
    def __init__(self):
        self.logger = logger
    
    def format_sniper_output(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        
        # Market data
        ltp: float,
        pdh: float,
        pdl: float,
        cpr_pivot: float,
        r1: float,
        r2: float,
        s1: float,
        s2: float,
        
        # Options
        atm_strike: float,
        atm_delta: float,
        atm_ce_ltp: float,
        atm_pe_ltp: float,
        atm_iv: float,
        
        # ATR for SL
        atr: float,
        
        # Capital
        capital: float,
        risk_pct: float = 1.0
    ) -> str:
        """
        Format complete sniper recommendation
        
        Returns:
            Formatted string output
        """
        
        # ========== BUILD RECOMMENDATION ==========
        
        if confidence.confidence_level == "SNIPER":
            return self._format_sniper(
                confidence, scenario, confluence,
                ltp, pdh, pdl, cpr_pivot, r1, r2, s1, s2,
                atm_strike, atm_delta, atm_ce_ltp, atm_pe_ltp, atm_iv,
                atr, capital, risk_pct
            )
        
        elif confidence.confidence_level == "CAUTIONARY":
            return self._format_cautionary(
                confidence, scenario, confluence,
                ltp, pdh, pdl, cpr_pivot, r1, r2, s1, s2,
                atm_strike, atm_delta, atm_ce_ltp, atm_pe_ltp, atm_iv,
                atr, capital, risk_pct
            )
        
        else:
            return self._format_wait(confidence, scenario, confluence, ltp)
    
    def _format_sniper(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        ltp: float, pdh: float, pdl: float, cpr_pivot: float,
        r1: float, r2: float, s1: float, s2: float,
        atm_strike: float, atm_delta: float, atm_ce_ltp: float,
        atm_pe_ltp: float, atm_iv: float,
        atr: float, capital: float, risk_pct: float
    ) -> str:
        """Format SNIPER (8+) output"""
        
        # Determine direction and strike
        if confidence.trade_decision == "BUY":
            side = "CALL"
            strike = int(atm_strike)
            entry_price = atm_ce_ltp
        else:
            side = "PUT"
            strike = int(atm_strike)
            entry_price = atm_pe_ltp
        
        # Calculate levels
        if side == "CALL":
            upside_barrier = pdh
            downside_floor = cpr_pivot
            stop_loss = entry_price - (atr * 0.8)
        else:
            upside_barrier = cpr_pivot
            downside_floor = pdl
            stop_loss = entry_price + (atr * 0.8)
        
        risk = abs(entry_price - stop_loss)
        target_1 = entry_price + (risk * 1.6) if side == "CALL" else entry_price - (risk * 1.6)
        target_2 = entry_price + (risk * 3.0) if side == "CALL" else entry_price - (risk * 3.0)
        
        # Position sizing
        capital_for_trade = capital * (risk_pct / 100)
        contracts = max(1, int(capital_for_trade / (risk * 100)))
        
        output = f"""
{'='*90}
🎯 SNIPER: HIGH CONVICTION {scenario.market_bias} [Confidence: {confidence.confidence_score:.1f}/10]
{'='*90}

WHY ARE YOU TAKING THIS TRADE?
{'─'*90}
Scenario: {scenario.scenario.value} (Execution Signal)
├─ Logic: {confidence.primary_reason}
├─ Confluence: {confluence.overall_score:.1f}/10 ({confluence.quality_description})
├─ Momentum: {scenario.secondary_triggers[0] if scenario.secondary_triggers else 'Aligned'}
├─ Option Flow: {scenario.secondary_triggers[1] if len(scenario.secondary_triggers) > 1 else 'Bullish'}
└─ Conviction: {confidence.confidence_score:.1f}/10 (Institutional positioning detected)

WHEN SHOULD YOU TAKE THIS TRADE?
{'─'*90}
├─ NOW ✓ (Price at {ltp:.0f} - In strike zone: {cpr_pivot:.0f} ± 100)
├─ High Probability Window: ✓ Active
├─ Trigger: {scenario.primary_trigger}
└─ ⚠️ Alert: Watch for rejection at {pdh:.0f} (PDH). Exit if price rejects here.

THE LEVELS (Your Trading Grid)
{'─'*90}
Current LTP:          {ltp:.0f}
Upside Barrier:       {upside_barrier:.0f} ({side} Exit Target 1) ⚠️ Trap Zone
Strike Zone:          {cpr_pivot:.0f} ± 100 (Your Entry Zone) ← YOU ARE HERE
Support Floor:        {downside_floor:.0f} (SL Zone)
Key Support:          {s1:.0f} (S1 + Daily Pivot)

EXECUTION PLAN (The Trade)
{'─'*90}
Entry Strike:         {strike} {side}
Entry Price:          ₹{entry_price:.0f}-{entry_price+5:.0f}
Stop Loss:            ₹{stop_loss:.0f} (Tight risk below CPR/PDH)
Risk Per Contract:    ₹{risk*100:.0f}

Target 1:             ₹{target_1:.0f} (Exit 70% | Profit: ₹{(target_1-entry_price)*100:.0f})
Target 2:             ₹{target_2:.0f} (Exit 30% | Profit: ₹{(target_2-entry_price)*100:.0f}, Trail SL)

Risk:Reward Ratio:    1:{(target_1-entry_price)/risk:.2f} (T1) | 1:{(target_2-entry_price)/risk:.2f} (T2)
Quantity:             {contracts} lot(s)
Max Risk Capital:     ₹{risk*100*contracts:.0f}
Max Profit (T1):      ₹{(target_1-entry_price)*100*contracts*0.7:.0f}
Max Profit (T2):      ₹{(target_2-entry_price)*100*contracts*0.3:.0f}

SUPPORTING ANALYSIS
{'─'*90}
Level Confluence Score:     {confluence.score_breakdown['level_factors']:.1f}/1.0
Trend Strength:             {confluence.score_breakdown['trend_factors']:.1f}/1.0
Momentum Health:            {confluence.score_breakdown['momentum_factors']:.1f}/1.0
Option Flow Agreement:      {confluence.score_breakdown['flow_factors']:.1f}/1.0

Confluence Factors:
"""
        
        # Add confluence details
        if confluence.factors.at_monthly_level > 0:
            output += f"├─ Monthly Level Proximity: ✓\n"
        if confluence.factors.level_overlap > 0.5:
            output += f"├─ Multiple Levels Overlapping: ✓ (Super Confluence)\n"
        if confluence.factors.ema_5_12_20_alignment > 0.7:
            output += f"├─ Short-term EMA Alignment: ✓\n"
        if confidence.secondary_reasons:
            for reason in confidence.secondary_reasons[:3]:
                output += f"├─ {reason}\n"
        
        output += f"""
ALERTS & INSTRUCTIONS
{'─'*90}
"""
        
        for warning in confidence.warnings[:2]:
            output += f"⚠️  {warning}\n"
        
        output += f"""
ACTION
{'─'*90}
✅ EXECUTE NOW | Full Position | Swing Trade Target

EXIT PLAN:
1️⃣  Hit Target 1 @ ₹{target_1:.0f} → Exit 70% (Secure profits)
2️⃣  Trail remaining 30% → Target 2 @ ₹{target_2:.0f} (Max upside)
3️⃣  Strict SL @ ₹{stop_loss:.0f} (Capital preservation)

Next Review: When Target 1 hits or price approaches {upside_barrier:.0f}
{'='*90}
"""
        return output
    
    def _format_cautionary(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        ltp: float, pdh: float, pdl: float, cpr_pivot: float,
        r1: float, r2: float, s1: float, s2: float,
        atm_strike: float, atm_delta: float, atm_ce_ltp: float,
        atm_pe_ltp: float, atm_iv: float,
        atr: float, capital: float, risk_pct: float
    ) -> str:
        """Format CAUTIONARY (6-7) output"""
        
        # Determine direction
        if confidence.trade_decision == "BUY":
            side = "CALL"
            strike = int(atm_strike)
            entry_price = atm_ce_ltp
        else:
            side = "PUT"
            strike = int(atm_strike)
            entry_price = atm_pe_ltp
        
        # Calculate for scalp (quick trade)
        stop_loss = entry_price - (atr * 0.6) if side == "CALL" else entry_price + (atr * 0.6)
        risk = abs(entry_price - stop_loss)
        target_1 = entry_price + (risk * 1.8) if side == "CALL" else entry_price - (risk * 1.8)
        
        output = f"""
{'='*90}
⚠️  CAUTIONARY: SCALP ONLY [Confidence: {confidence.confidence_score:.1f}/10]
{'='*90}

WHY ARE YOU TAKING THIS TRADE?
{'─'*90}
Scenario: {scenario.scenario.value}
├─ Logic: {confidence.primary_reason}
├─ Confluence: {confluence.overall_score:.1f}/10 ({confluence.quality_description})
├─ Risk Level: {confidence.risk_level} (Proceed cautiously)
└─ Conviction: MEDIUM (Good setup, but some conflicting signals)

WHEN SHOULD YOU TAKE THIS TRADE?
{'─'*90}
├─ IF Price confirms reversal (Close beyond {cpr_pivot:.0f})
├─ High Probability Window: ✓
├─ Trigger: {scenario.primary_trigger}
└─ ⚠️  CAUTION: This is a SCALP, NOT a swing trade

THE LEVELS
{'─'*90}
Current LTP:          {ltp:.0f}
Rejection Level:      {pdh:.0f} ← Price rejected here
Entry Zone:           {cpr_pivot:.0f}-{cpr_pivot+50:.0f} (Reversal confirmation)
Target (Scalp):       {target_1:.0f}
Stop Loss:            ₹{stop_loss:.0f} (Tight, fast exit if wrong)

EXECUTION PLAN (Quick Scalp)
{'─'*90}
Entry Strike:         {strike} {side}
Entry Price:          ₹{entry_price:.0f}-{entry_price+3:.0f}
Stop Loss:            ₹{stop_loss:.0f} (TIGHT - Fast exits only)
Risk Per Contract:    ₹{risk*100:.0f}

Target 1:             ₹{target_1:.0f} (Exit 100% | Profit: ₹{(target_1-entry_price)*100:.0f})
NO Target 2:          (Scalp only - Don't be greedy)

Risk:Reward Ratio:    1:{(target_1-entry_price)/risk:.2f}
Quantity:             1 lot (Reduced position)
Max Risk:             ₹{risk*100:.0f}
Max Profit:           ₹{(target_1-entry_price)*100:.0f}

ALERTS
{'─'*90}
"""
        for warning in confidence.warnings:
            output += f"⚠️  {warning}\n"
        
        output += f"""
ACTION
{'─'*90}
⚠️  SCALP ENTRY ONLY | Quick Exit | High Discipline Required

EXIT PLAN:
1️⃣  Hit Target @ ₹{target_1:.0f} → Exit 100% (Secure and leave)
2️⃣  NO holding for more profit (Scalp territory)
3️⃣  SL @ ₹{stop_loss:.0f} → Fast exit if wrong

Max Hold Time: 30 minutes
DO NOT HOLD OVERNIGHT
{'='*90}
"""
        return output
    
    def _format_wait(
        self,
        confidence: ConfidenceOutput,
        scenario: ScenarioOutput,
        confluence: ConfluenceScore,
        ltp: float
    ) -> str:
        """Format WAIT (<6) output"""
        
        output = f"""
{'='*90}
🚫 WAIT & WATCH [Confidence: {confidence.confidence_score:.1f}/10]
{'='*90}

MARKET STATUS
{'─'*90}
Scenario: {scenario.scenario.value} (No Trade)
├─ {confidence.primary_reason}
├─ Confluence: {confluence.overall_score:.1f}/10 ({confluence.quality_description})
└─ Decision: DO NOT TRADE

WHY NOT NOW?
{'─'*90}
"""
        
        for reason in confidence.secondary_reasons:
            output += f"├─ {reason}\n"
        
        output += f"""
NEXT TRIGGER
{'─'*90}
Wait for one of these setups:
"""
        
        for trigger in confidence.warnings[:3]:
            output += f"├─ {trigger}\n"
        
        output += f"""
ACTION
{'─'*90}
✅ STAY CASH | Preserve Capital | Wait for Better Setup

Next Review: When price action changes or new confluence develops
{'='*90}
"""
        return output
