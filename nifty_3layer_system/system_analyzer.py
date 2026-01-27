#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRODUCTION SYSTEM ANALYZER
Analyzes CURRENT market data through all 4 layers
+ Advanced options & market depth analysis
Returns: ONE decision (BUY/SELL/WAIT) with position sizing
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Fix Unicode encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env
load_dotenv(project_root / ".env")

from intelligence import (
    ScenarioClassifier,
    ConfluenceScorer,
    ConfidenceCalculator,
    TechnicalContext
)
from risk_management import PositionSizer
from options_analysis import OptionAnalyzer, BlackScholesCalculator
from market_depth_analyzer import MarketDepthAnalyzer

# ==============================================================================
# GET CURRENT MARKET DATA
# ==============================================================================
print("\n" + "="*90)
print("NIFTY TRADING SYSTEM - REAL-TIME ANALYSIS".center(90))
print("="*90)

# Initialize modules
scenario_clf = ScenarioClassifier()
conf_scorer = ConfluenceScorer()
conf_calc = ConfidenceCalculator()
pos_sizer = PositionSizer(capital=15000)

# FETCH CURRENT MARKET DATA FROM DHAN API
print("\n[INFO] Fetching LIVE market data from Dhan API...")

current_ctx = None

try:
    from integrations import DhanDataManager
    from intelligence import TechnicalContext
    import pandas as pd
    from datetime import datetime
    import ta
    
    print("[DEBUG] Initializing DhanDataManager...")
    manager = DhanDataManager()
    
    # Fetch 5-min candles (200 candles = ~33 hours)
    print("[DEBUG] Fetching NIFTY candles...")
    df = manager.get_nifty_candles(interval=5, days=10)
    
    if df is not None and len(df) > 0:
        print(f"[SUCCESS] ✓ Got {len(df)} candles from Dhan API")
        
        # Get latest values
        latest = df.iloc[-1]
        ltp = float(latest['close'])
        
        # Calculate indicators
        df['EMA5'] = ta.trend.ema_indicator(df['close'], window=5)
        df['EMA12'] = ta.trend.ema_indicator(df['close'], window=12)
        df['EMA20'] = ta.trend.ema_indicator(df['close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50, fillna=True)
        df['EMA100'] = ta.trend.ema_indicator(df['close'], window=100, fillna=True)
        df['EMA200'] = ta.trend.ema_indicator(df['close'], window=200, fillna=True)
        df['RSI'] = ta.momentum.rsi(df['close'], window=14, fillna=True)
        macd = ta.trend.MACD(df['close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14, fillna=True)
        df['Vol_MA'] = ta.volume.volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'], fillna=True)
        
        # Get latest daily data
        df_daily = manager.get_nifty_daily(days=365)
        daily_high = df_daily['high'].max()
        daily_low = df_daily['low'].min()
        
        # Create TechnicalContext
        current_ctx = TechnicalContext(
            ltp=ltp,
            cpr_pivot=(daily_high + daily_low) / 2,
            cpr_tc=daily_high,
            cpr_bc=daily_low,
            cpr_width=daily_high - daily_low,
            pdh=df_daily.iloc[-2]['high'] if len(df_daily) > 1 else daily_high,
            pdl=df_daily.iloc[-2]['low'] if len(df_daily) > 1 else daily_low,
            ema_5=float(df['EMA5'].iloc[-1]),
            ema_12=float(df['EMA12'].iloc[-1]),
            ema_20=float(df['EMA20'].iloc[-1]),
            ema_50=float(df['EMA50'].iloc[-1]),
            ema_100=float(df['EMA100'].iloc[-1]),
            ema_200=float(df['EMA200'].iloc[-1]),
            rsi=float(df['RSI'].iloc[-1]),
            macd_histogram=float(df['MACD_Hist'].iloc[-1]),
            macd_signal=float(df['MACD_Signal'].iloc[-1]),
            macd_line=float(df['MACD'].iloc[-1]),
            volume=float(df['volume'].iloc[-1]),
            volume_20ma=float(df['Vol_MA'].iloc[-1]),
            atr=float(df['ATR'].iloc[-1]),
            vix=18.0,  # TODO: Fetch from Dhan
            current_hour=datetime.now().hour,
            current_minute=datetime.now().minute,
            pcr=0.95,  # TODO: Calculate from option chain
            call_oi_change=0,  # TODO: Get from option chain
            put_oi_change=0,  # TODO: Get from option chain
            bid_ask_spread=1.0  # TODO: Get from live quote
        )
    else:
        print("[WARNING] No candles received from Dhan")
        
except Exception as e:
    print(f"[ERROR] Dhan API error: {str(e)}")
    import traceback
    traceback.print_exc()

# Fallback to demo data
if current_ctx is None:
    print("[INFO] Using DEMO market data...")
    current_ctx = TechnicalContext(
        ltp=25310.0, cpr_pivot=25295.0, cpr_tc=25315.0, cpr_bc=25275.0, cpr_width=40.0,
        pdh=25385.0, pdl=25200.0,
        ema_5=25320.0, ema_12=25315.0, ema_20=25310.0,
        ema_50=25305.0, ema_100=25300.0, ema_200=25290.0,
        rsi=65.0, macd_histogram=25.0, macd_signal=10.0, macd_line=35.0,
        volume=1500000, volume_20ma=1400000, atr=45.0, vix=14.0,
        current_hour=14, current_minute=30,
        pcr=0.95, call_oi_change=50000, put_oi_change=-30000, bid_ask_spread=1.0
    )

# ==============================================================================
# LAYER 1: WHERE ARE WE?
# ==============================================================================
print("\n" + "-"*90)
print("ANALYZING...".center(90))
print("-"*90)

scen = scenario_clf.classify(current_ctx)
print(f"\n[LAYER 1] Market Scenario: {scen.scenario}")
print(f"           Risk Level: {scen.risk_level}")

# ==============================================================================
# LAYER 2: SIGNAL STRENGTH?
# ==============================================================================
conf = conf_scorer.score(
    ltp=current_ctx.ltp, cpr_pivot=current_ctx.cpr_pivot, cpr_tc=current_ctx.cpr_tc, 
    cpr_bc=current_ctx.cpr_bc, pdh=current_ctx.pdh, pdl=current_ctx.pdl,
    ema_5=current_ctx.ema_5, ema_12=current_ctx.ema_12, ema_20=current_ctx.ema_20,
    ema_50=current_ctx.ema_50, ema_100=current_ctx.ema_100, ema_200=current_ctx.ema_200,
    rsi=current_ctx.rsi, macd_histogram=current_ctx.macd_histogram, 
    macd_line=current_ctx.macd_line,
    volume=current_ctx.volume, volume_20ma=current_ctx.volume_20ma,
    pcr=current_ctx.pcr, call_oi_change=current_ctx.call_oi_change, 
    put_oi_change=current_ctx.put_oi_change, bid_ask_spread=current_ctx.bid_ask_spread
)
print(f"[LAYER 2] Confluence Score: {conf.overall_score:.1f}/10 ({conf.quality_description})")

# ==============================================================================
# LAYER 3: WHAT TO DO?
# ==============================================================================
decision = conf_calc.calculate(scen, conf)
print(f"[LAYER 3] Signal Type: {decision.confidence_level}")
print(f"           Confidence: {decision.confidence_score:.1f}/10")
print(f"           Action: {decision.trade_decision}")

# ==============================================================================
# BONUS: OPTIONS & MARKET DEPTH ANALYSIS
# ==============================================================================

print(f"\n[OPTIONS ANALYSIS]")

# Calculate Greeks for ATM Call
opt_analyzer = OptionAnalyzer(spot_price=current_ctx.ltp)
atm_call_greeks = opt_analyzer.calculate_greeks(
    strike=25310.0,  # ATM
    days_to_expiry=4,
    iv=0.22,  # 22% IV
    option_type="CALL"
)

atm_put_greeks = opt_analyzer.calculate_greeks(
    strike=25310.0,
    days_to_expiry=4,
    iv=0.22,
    option_type="PUT"
)

print(f"  ATM Call Greeks (Strike 25310):")
print(f"    Delta: {atm_call_greeks.delta:.3f} | Gamma: {atm_call_greeks.gamma:.4f}")
print(f"    Theta: {atm_call_greeks.theta:.4f}/day | Vega: {atm_call_greeks.vega:.2f}")
print(f"    IV: {atm_call_greeks.iv:.2f}%")

print(f"\n  ATM Put Greeks (Strike 25310):")
print(f"    Delta: {atm_put_greeks.delta:.3f} | Gamma: {atm_put_greeks.gamma:.4f}")
print(f"    Theta: {atm_put_greeks.theta:.4f}/day | Vega: {atm_put_greeks.vega:.2f}")

# IV Analysis
iv_analysis = opt_analyzer.analyze_iv_levels(
    current_iv=0.22,
    iv_high_52w=0.35,
    iv_low_52w=0.15
)
print(f"\n  IV Status: {iv_analysis['iv_status']} (Rank: {iv_analysis['iv_rank']:.0f}%)")
print(f"    Current: {iv_analysis['current_iv']:.2f}% | 52w Range: {iv_analysis['52w_low']:.2f}% - {iv_analysis['52w_high']:.2f}%")

# Skew Analysis
skew = opt_analyzer.analyze_skew(
    atm_iv=0.22,
    otm_call_iv=0.20,
    otm_put_iv=0.25
)
print(f"\n  Volatility Skew: {skew['direction_bias']} Bias")
print(f"    Put-Call Skew: {skew['put_call_skew']:.2f}% (Put IV higher = Bearish)")

# ==============================================================================
# LAYER 4: HOW MUCH TO TRADE?
# ==============================================================================
position = pos_sizer.calculate_position(
    confluence_score=conf.overall_score,
    entry_price=current_ctx.ltp,
    atm_ltp=current_ctx.ltp,
    atr=current_ctx.atr,
    trend_bias="BULLISH"
)

print(f"[LAYER 4] Position Sizing:")
print(f"   Entry Price: Rs.{position.entry:.0f}")
print(f"   Stop Loss: Rs.{position.stop_loss:.0f} ({position.risk_points:.0f} points)")
print(f"   Target 1: Rs.{position.target_1:.0f} (Profit: {position.reward_1_points:.0f} pts)")
print(f"   Target 2: Rs.{position.target_2:.0f} (Profit: {position.reward_2_points:.0f} pts)")
print(f"   Quantity: {position.quantity} lots")
print(f"   Max Risk: Rs.{position.risk_capital:.0f} ({position.risk_pct:.2f}% of capital)")

# ==============================================================================
# FINAL DECISION
# ==============================================================================
print("\n" + "="*90)
print("FINAL RECOMMENDATION".center(90))
print("="*90)

if decision.confidence_level == "SNIPER":
    action_emoji = "🟢 GO FOR IT"
elif decision.confidence_level == "CAUTIONARY":
    action_emoji = "🟡 BE CAREFUL"
else:
    action_emoji = "🔴 DO NOT TRADE"

print(f"\n{action_emoji}")
print(f"\nSignal: {decision.confidence_level} ({decision.confidence_score:.1f}/10)")
print(f"Entry: Rs.{position.entry:.0f} | SL: Rs.{position.stop_loss:.0f} | T1: Rs.{position.target_1:.0f}")
print(f"Quantity: {position.quantity} lots | Risk: Rs.{position.risk_capital:.0f}")
print(f"Reason: {decision.primary_reason}")

print("\n" + "="*90)
print("SYSTEM READY".center(90))
print("="*90 + "\n")
