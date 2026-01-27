"""
COPILOT DEMO: Full Intelligence System Test
Demonstrates:
- Scenario Classification (5 scenarios)
- Confluence Scoring (1-10)
- Confidence Calculation (8+, 6-7, <6)
- Sniper Output Formatting
"""

import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, format="<level>{level: <8}</level> | {message}", level="INFO")

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from intelligence import (
    ScenarioClassifier,
    ConfluenceScorer,
    ConfidenceCalculator,
    CopilotFormatter,
    TechnicalContext
)


def demo_high_conviction_trend():
    """Demo: SNIPER setup - High conviction bullish trend"""
    print("\n" + "="*90)
    print("DEMO 1: HIGH CONVICTION BULLISH TREND (SNIPER)")
    print("="*90)
    
    # === LIVE MARKET DATA (Example) ===
    ltp = 25310.0
    pdh = 25385.0
    pdl = 25200.0
    
    # CPR calculation
    pivot = (pdh + pdl + 25300) / 3
    tc = (pdh + pdl) / 2 + pivot / 2
    bc = (pdh + pdl) / 2 - pivot / 2
    
    # EMAs (all 6) - showing bullish alignment
    ema_5 = 25320.0
    ema_12 = 25315.0
    ema_20 = 25310.0
    ema_50 = 25290.0
    ema_100 = 25270.0
    ema_200 = 25240.0
    
    # Momentum
    rsi = 68.0  # Strong, not exhausted
    macd_histogram = 45.0  # Rising
    macd_line = 120.0
    
    # Volume & Volatility
    volume = 2500000.0
    volume_20ma = 1800000.0
    atr = 85.0
    vix = 12.5
    
    # Option flow
    pcr = 1.28  # Bullish
    call_oi_change = -15000  # Call unwinding
    put_oi_change = 25000  # Put addition
    bid_ask_spread = 2.0  # Tight spreads
    
    # ===== CLASSIFY SCENARIO =====
    context = TechnicalContext(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc, cpr_width=tc-bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        macd_signal=100.0,
        volume=volume, volume_20ma=volume_20ma, atr=atr, vix=vix,
        current_hour=10, current_minute=30,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread
    )
    
    classifier = ScenarioClassifier()
    scenario = classifier.classify(context)
    
    print(f"\n[SCENARIO CLASSIFICATION]")
    print(f"Scenario: {scenario}")
    print(f"Primary Trigger: {scenario.primary_trigger}")
    print(f"Market Bias: {scenario.market_bias}")
    
    # ===== CALCULATE CONFLUENCE =====
    scorer = ConfluenceScorer(monthly_levels=[25300, 25350, 25250])
    
    confluence = scorer.score(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        volume=volume, volume_20ma=volume_20ma,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread,
        trend_bias="BULLISH",
        in_high_prob_window=True,
        in_eod_window=False
    )
    
    print(f"\n[CONFLUENCE ANALYSIS]")
    print(f"Confluence Score: {confluence}")
    print(f"Breakdown:")
    for key, value in confluence.score_breakdown.items():
        print(f"  {key}: {value:.2f}")
    
    # ===== CALCULATE CONFIDENCE =====
    calc = ConfidenceCalculator()
    confidence = calc.calculate(scenario, confluence)
    
    print(f"\n[CONFIDENCE CALCULATION]")
    print(f"Confidence Level: {confidence.confidence_level}")
    print(f"Confidence Score: {confidence.confidence_score:.1f}/10")
    print(f"Trade Decision: {confidence.trade_decision}")
    print(f"Position Type: {confidence.position_type}")
    print(f"Holding Period: {confidence.holding_period}")
    
    # ===== FORMAT COPILOT OUTPUT =====
    formatter = CopilotFormatter()
    
    # Calculate support/resistance
    r1 = pivot + (pdh - pdl) * 0.33
    r2 = pivot + (pdh - pdl) * 0.66
    s1 = pivot - (pdh - pdl) * 0.33
    s2 = pivot - (pdh - pdl) * 0.66
    
    copilot_output = formatter.format_sniper_output(
        confidence=confidence,
        scenario=scenario,
        confluence=confluence,
        ltp=ltp, pdh=pdh, pdl=pdl, cpr_pivot=pivot,
        r1=r1, r2=r2, s1=s1, s2=s2,
        atm_strike=25300.0, atm_delta=0.52,
        atm_ce_ltp=118.0, atm_pe_ltp=115.0,
        atm_iv=0.22,
        atr=atr,
        capital=15000, risk_pct=1.0
    )
    
    print(copilot_output)


def demo_trap_scalp():
    """Demo: CAUTIONARY setup - Trap reversal scalp"""
    print("\n" + "="*90)
    print("DEMO 2: TRAP REVERSAL SCALP (CAUTIONARY)")
    print("="*90)
    
    # === MARKET DATA: Price rejected at PDH ===
    ltp = 25380.0  # Just below PDH
    pdh = 25385.0
    pdl = 25200.0
    
    pivot = (pdh + pdl + 25300) / 3
    tc = (pdh + pdl) / 2 + pivot / 2
    bc = (pdh + pdl) / 2 - pivot / 2
    
    # EMAs - showing mixed signals
    ema_5 = 25375.0
    ema_12 = 25370.0
    ema_20 = 25360.0  # Price getting exhausted
    ema_50 = 25300.0
    ema_100 = 25280.0
    ema_200 = 25250.0
    
    # Momentum - divergence
    rsi = 72.0  # Exhaustion zone
    macd_histogram = 10.0  # Flattening
    macd_line = 130.0
    
    volume = 1500000.0
    volume_20ma = 1800000.0
    atr = 80.0
    vix = 13.0
    
    pcr = 1.0  # Neutral
    call_oi_change = 45000  # Heavy call writing
    put_oi_change = -8000  # Put selling
    bid_ask_spread = 3.0
    
    context = TechnicalContext(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc, cpr_width=tc-bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        macd_signal=125.0,
        volume=volume, volume_20ma=volume_20ma, atr=atr, vix=vix,
        current_hour=14, current_minute=45,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread
    )
    
    classifier = ScenarioClassifier()
    scenario = classifier.classify(context)
    
    print(f"\n[SCENARIO CLASSIFICATION]")
    print(f"Scenario: {scenario}")
    print(f"Divergence: RSI={scenario.divergence.rsi_bearish_div}, MACD={scenario.divergence.macd_bearish_div}")
    
    scorer = ConfluenceScorer(monthly_levels=[25300, 25350, 25250])
    confluence = scorer.score(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        volume=volume, volume_20ma=volume_20ma,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread,
        rsi_divergence_strength=0.7,
        macd_divergence_strength=0.6,
        trend_bias="BEARISH",
        in_high_prob_window=True,
        in_eod_window=True
    )
    
    print(f"\n[CONFLUENCE ANALYSIS]")
    print(f"Confluence Score: {confluence}")
    
    calc = ConfidenceCalculator()
    confidence = calc.calculate(scenario, confluence)
    
    print(f"\n[CONFIDENCE CALCULATION]")
    print(f"Confidence Level: {confidence.confidence_level}")
    print(f"Confidence Score: {confidence.confidence_score:.1f}/10")
    print(f"Trade Decision: {confidence.trade_decision}")
    print(f"Position Type: {confidence.position_type}")
    
    formatter = CopilotFormatter()
    
    r1 = pivot + (pdh - pdl) * 0.33
    s1 = pivot - (pdh - pdl) * 0.33
    s2 = pivot - (pdh - pdl) * 0.66
    
    copilot_output = formatter.format_sniper_output(
        confidence=confidence, scenario=scenario, confluence=confluence,
        ltp=ltp, pdh=pdh, pdl=pdl, cpr_pivot=pivot,
        r1=r1, r2=pdh, s1=s1, s2=s2,
        atm_strike=25350.0, atm_delta=-0.48,
        atm_ce_ltp=90.0, atm_pe_ltp=105.0,
        atm_iv=0.25,
        atr=atr, capital=15000, risk_pct=1.0
    )
    
    print(copilot_output)


def demo_choppy_wait():
    """Demo: WAIT signal - Choppy, no trade"""
    print("\n" + "="*90)
    print("DEMO 3: CHOPPY MARKET - WAIT (NO TRADE)")
    print("="*90)
    
    ltp = 25300.0
    pdh = 25385.0
    pdl = 25200.0
    
    pivot = (pdh + pdl + 25300) / 3
    tc = pivot + 60
    bc = pivot - 60
    
    # EMAs - no alignment
    ema_5 = 25310.0
    ema_12 = 25295.0
    ema_20 = 25315.0
    ema_50 = 25300.0
    ema_100 = 25290.0
    ema_200 = 25280.0
    
    # Momentum - flat
    rsi = 52.0  # Choppy zone
    macd_histogram = 2.0  # Near zero
    macd_line = 115.0
    
    volume = 800000.0  # Low
    volume_20ma = 1600000.0
    atr = 50.0
    vix = 11.0
    
    pcr = 0.95  # Neutral
    call_oi_change = 5000
    put_oi_change = -3000
    bid_ask_spread = 1.5
    
    context = TechnicalContext(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc, cpr_width=tc-bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        macd_signal=113.0,
        volume=volume, volume_20ma=volume_20ma, atr=atr, vix=vix,
        current_hour=12, current_minute=30,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread
    )
    
    classifier = ScenarioClassifier()
    scenario = classifier.classify(context)
    
    print(f"\n[SCENARIO CLASSIFICATION]")
    print(f"Scenario: {scenario}")
    
    scorer = ConfluenceScorer()
    confluence = scorer.score(
        ltp=ltp, cpr_pivot=pivot, cpr_tc=tc, cpr_bc=bc,
        pdh=pdh, pdl=pdl,
        ema_5=ema_5, ema_12=ema_12, ema_20=ema_20,
        ema_50=ema_50, ema_100=ema_100, ema_200=ema_200,
        rsi=rsi, macd_histogram=macd_histogram, macd_line=macd_line,
        volume=volume, volume_20ma=volume_20ma,
        pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
        bid_ask_spread=bid_ask_spread,
        trend_bias="NEUTRAL"
    )
    
    print(f"\n[CONFLUENCE ANALYSIS]")
    print(f"Confluence Score: {confluence}")
    
    calc = ConfidenceCalculator()
    confidence = calc.calculate(scenario, confluence)
    
    print(f"\n[CONFIDENCE CALCULATION]")
    print(f"Confidence Level: {confidence.confidence_level}")
    print(f"Confidence Score: {confidence.confidence_score:.1f}/10")
    print(f"Decision: {confidence.trade_decision}")
    
    formatter = CopilotFormatter()
    copilot_output = formatter.format_sniper_output(
        confidence=confidence, scenario=scenario, confluence=confluence,
        ltp=ltp, pdh=pdh, pdl=pdl, cpr_pivot=pivot,
        r1=pdh, r2=pdh+85, s1=pivot, s2=pdl,
        atm_strike=25300.0, atm_delta=0.0,
        atm_ce_ltp=100.0, atm_pe_ltp=98.0,
        atm_iv=0.20,
        atr=atr, capital=15000, risk_pct=1.0
    )
    
    print(copilot_output)


if __name__ == "__main__":
    print("\n" + "█"*90)
    print("  NIFTY SNIPER COPILOT: AI TRADING INTELLIGENCE SYSTEM")
    print("█"*90)
    
    demo_high_conviction_trend()
    demo_trap_scalp()
    demo_choppy_wait()
    
    print("\n" + "█"*90)
    print("[SUCCESS] Sniper Copilot System Operational!")
    print("█"*90 + "\n")
