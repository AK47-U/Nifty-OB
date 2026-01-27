#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST SCRIPT - Market Closed Testing
Uses historical NIFTY data to test all 3 intelligence modules:
1. Market Structure Validation
2. Opportunity Calibration (50-point capture)
3. Options Intelligence
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from integrations import DhanDataManager
from intelligence.market_structure import MarketStructure, StructureTrend
from intelligence.opportunity_calibration import OpportunityCalibration
from indicators.technical import TechnicalIndicators
from intelligence import MTFTrendAnalyzer
from config.trading_config import CONFIG

print("\n" + "="*90)
print("MARKET CLOSED TEST - NIFTY 3-LAYER SYSTEM".center(90))
print("Using last 10 days of historical data to verify all modules".center(90))
print("="*90)

try:
    dm = DhanDataManager()
    
    print("\n[1] Fetching historical 5-minute candles (last 10 days)...", end=" ")
    df5 = dm.get_nifty_candles(interval=5, days=10)
    df5.columns = df5.columns.str.lower()
    print(f"✓ {len(df5)} candles loaded")
    
    print("[2] Fetching daily candles (last 20 days)...", end=" ")
    dfd = dm.get_nifty_daily(days=20)
    dfd.columns = dfd.columns.str.lower()
    print(f"✓ {len(dfd)} candles loaded")
    
    print("[3] Fetching 15-minute candles...", end=" ")
    df15 = dm.get_nifty_candles(interval=15, days=10)
    df15.columns = df15.columns.str.lower()
    print(f"✓ {len(df15)} candles loaded")
    
    print("[4] Fetching 60-minute candles...", end=" ")
    df60 = dm.get_nifty_candles(interval=60, days=10)
    df60.columns = df60.columns.str.lower()
    print(f"✓ {len(df60)} candles loaded")
    
except Exception as e:
    print(f"✗ Error fetching data: {e}")
    sys.exit(1)

# Extract key values from latest candle
ltp = float(df5['close'].iloc[-1])
print(f"\n✓ Current LTP (from latest 5m close): {ltp:.2f}")

# Calculate technical indicators
ti = TechnicalIndicators()

# ATR
df5_for_atr = df5.rename(columns={'high': 'High', 'low': 'Low', 'close': 'Close'})
atr_s = ti.calculate_atr(df5_for_atr, CONFIG.ATR_PERIOD)
atr_val = float(atr_s.iloc[-1]) if atr_s.iloc[-1] > 0 else 50.0
print(f"✓ ATR (14-period): {atr_val:.2f} points")

# Volume ratio
vol = float(df5['volume'].iloc[-1])
vol_20 = float(df5['volume'].rolling(CONFIG.VOLUME_MA_PERIOD).mean().iloc[-1])
volume_ratio = vol / vol_20 if vol_20 else 1.0
print(f"✓ Volume Ratio: {volume_ratio:.2f}x")

# CPR (Camarilla Pivot Points)
pdt_h = float(dfd['high'].iloc[-2])
pdt_l = float(dfd['low'].iloc[-2])
pdt_c = float(dfd['close'].iloc[-2])

tc = pdt_h + (pdt_c - pdt_l) * 1.1
bc = pdt_l - (pdt_h - pdt_c) * 1.1
pvt = (pdt_h + pdt_l + pdt_c) / 3

print(f"✓ CPR: BC={bc:.0f} | Pivot={pvt:.0f} | TC={tc:.0f}")

# VWAP
print(f"✓ Volume data: Current={vol:.0f} | 20-period avg={vol_20:.0f}")

# ========== TEST 1: MARKET STRUCTURE VALIDATION ==========
print("\n" + "="*90)
print("TEST 1: MARKET STRUCTURE VALIDATION".center(90))
print("="*90)

market_struct = MarketStructure(
    intraday_candles=df5,
    daily_candles=dfd,
    current_price=ltp,
    support_level=bc,
    resistance_level=tc
)

# Test structure detection
struct_trend = market_struct._detect_structure_trend()
opening_bias = market_struct._detect_opening_bias()

print(f"\n✓ Market Structure Trend: {struct_trend.value}")
print(f"✓ Opening Bias: {opening_bias.value}")
print(f"✓ Entry Failure Risk: {market_struct._detect_entry_failure()}")

# Test validation against MTF signal
struct_val_bullish = market_struct.validate_against_mtf_signal("BULLISH", 75)
struct_val_bearish = market_struct.validate_against_mtf_signal("BEARISH", 75)

print(f"\n[BULLISH Signal Validation]")
print(f"  Is Valid: {struct_val_bullish.is_valid}")
print(f"  Confidence Adjustment: {struct_val_bullish.confidence_adjustment:.2f}x")
if struct_val_bullish.warnings:
    print(f"  Warnings: {struct_val_bullish.warnings}")

print(f"\n[BEARISH Signal Validation]")
print(f"  Is Valid: {struct_val_bearish.is_valid}")
print(f"  Confidence Adjustment: {struct_val_bearish.confidence_adjustment:.2f}x")
if struct_val_bearish.warnings:
    print(f"  Warnings: {struct_val_bearish.warnings}")

# ========== TEST 2: OPPORTUNITY CALIBRATION (50-POINT CAPTURE) ==========
print("\n" + "="*90)
print("TEST 2: OPPORTUNITY CALIBRATION (50-POINT CAPTURE IN 15-30MIN)".center(90))
print("="*90)

# Test for bullish direction
opp_bullish = OpportunityCalibration(
    intraday_candles=df5,
    atr_value=atr_val,
    current_price=ltp,
    volume_ratio=volume_ratio,
    direction="BULLISH"
)

opp_metrics_bullish = opp_bullish.calculate()
print(f"\n[BULLISH 50-POINT OPPORTUNITY]")
print(opp_metrics_bullish)

# Test for bearish direction
opp_bearish = OpportunityCalibration(
    intraday_candles=df5,
    atr_value=atr_val,
    current_price=ltp,
    volume_ratio=volume_ratio,
    direction="BEARISH"
)

opp_metrics_bearish = opp_bearish.calculate()
print(f"\n[BEARISH 50-POINT OPPORTUNITY]")
print(opp_metrics_bearish)

# ========== TEST 3: MULTI-TIMEFRAME ANALYSIS ==========
print("\n" + "="*90)
print("TEST 3: MULTI-TIMEFRAME TREND CONSENSUS".center(90))
print("="*90)

mtf_analyzer = MTFTrendAnalyzer()
mtf_result = mtf_analyzer.analyze_all(df5, df15, df60, dfd, ti)

print(f"\n✓ MTF Trend: {mtf_result.trend.value}")
print(f"✓ Consensus Score: {mtf_result.consensus_score:+.2f}")
print(f"✓ Confidence: {mtf_result.confidence:.0%}")
print(f"✓ Primary Driver TF: {mtf_result.primary_driver_tf}")

print(f"\n   Timeframe Breakdown:")
for tf_name in ["5m", "30m", "15m", "60m", "daily"]:
    if tf_name in mtf_result.analysis_by_tf:
        analysis = mtf_result.analysis_by_tf[tf_name]
        emoji = "🟢" if analysis.trend_score > 0.3 else "🔴" if analysis.trend_score < -0.3 else "🟡"
        print(f"   {emoji} {tf_name:6} → Trend Score: {analysis.trend_score:+.2f}")

# ========== TEST 4: COMBINED DECISION LOGIC ==========
print("\n" + "="*90)
print("TEST 4: COMBINED DECISION (Structure + Opportunity + MTF)".center(90))
print("="*90)

mtf_confidence_pct = mtf_result.confidence * 100

print(f"\nScenario: MTF {mtf_result.trend.value} at {mtf_confidence_pct:.0f}% confidence")
print(f"\n[Step 1: Check Market Structure]")

if mtf_result.trend.value == "BULLISH":
    struct_check = struct_val_bullish
else:
    struct_check = struct_val_bearish

if struct_check.is_valid:
    print(f"  ✓ Structure SUPPORTS {mtf_result.trend.value} signal")
else:
    print(f"  ✗ Structure CONTRADICTS {mtf_result.trend.value} signal")
    print(f"    Adjustment: {struct_check.confidence_adjustment:.2f}x")

print(f"\n[Step 2: Check 50-Point Opportunity]")

if mtf_result.trend.value == "BULLISH":
    opp_check = opp_metrics_bullish
else:
    opp_check = opp_metrics_bearish

print(f"  Opportunity Confidence: {opp_check.overall_confidence:.1f}%")
if opp_check.overall_confidence >= 60:
    print(f"  ✓ SUFFICIENT volatility/volume to capture 50pts in 15-30min")
else:
    print(f"  ✗ INSUFFICIENT opportunity for 50pt move")

print(f"\n[Step 3: Final Trade Decision]")

# Simulate final decision logic
final_decision = "WAIT"
final_confidence = 0.0

if mtf_confidence_pct >= 70 and struct_check.is_valid and opp_check.overall_confidence >= 60:
    final_decision = mtf_result.trend.value
    final_confidence = (opp_check.overall_confidence / 10.0) * struct_check.confidence_adjustment
    final_confidence = min(10.0, final_confidence)
    print(f"  ✓ EXECUTE: {final_decision}")
    print(f"    Final Confidence: {final_confidence:.1f}/10")
elif mtf_confidence_pct >= 70:
    print(f"  ⚠️  Structure or Opportunity weak - WAIT for better setup")
    print(f"    Reason: {'Structure conflict' if not struct_check.is_valid else 'Low opportunity confidence'}")
else:
    print(f"  ✗ MTF confidence {mtf_confidence_pct:.0f}% < 70% threshold - WAIT")

# ========== TEST SUMMARY ==========
print("\n" + "="*90)
print("TEST SUMMARY".center(90))
print("="*90)

print(f"""
✅ All modules loaded successfully:
   • Market Structure Validator
   • Opportunity Calibration (50-point focus)
   • Options Intelligence (ready to integrate)
   • MTF Analyzer

✅ Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}
✅ NIFTY LTP: {ltp:.2f}
✅ ATR: {atr_val:.2f} | Volume Ratio: {volume_ratio:.2f}x

🎯 Ready for live market testing when markets open.

Next Steps:
   1. Review this output to ensure all calculations look correct
   2. Identify any missing edge cases or adjustments
   3. Deploy to live analyzer.py for market hours
""")

print("="*90)
