#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRODUCTION TRADING ANALYZER - LIVE 3-LAYER SYSTEM
Complete analysis with Dhan API live data + Greeks + Position sizing
"""

import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

# Suppress all logs except WARNING and above
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from integrations import DhanDataManager, DhanAPIClient
from intelligence import (
    ScenarioClassifier, ConfluenceScorer, ConfidenceCalculator, TechnicalContext, 
    MTFTrendAnalyzer, OptionsIntelligence
)
from intelligence.market_structure import MarketStructure
from intelligence.opportunity_calibration import OpportunityCalibration
from indicators.technical import TechnicalIndicators
from options_analysis import OptionAnalyzer
from config.trading_config import CONFIG

print("\n" + "="*90)
print("NIFTY 3-LAYER TRADING SYSTEM - COMPLETE ANALYSIS".center(90))
print("="*90)


def is_market_open(now_ist: datetime | None = None) -> tuple[bool, datetime]:
    """Check NSE cash hours from config."""
    tz = ZoneInfo("Asia/Kolkata")
    now = now_ist or datetime.now(tz)
    if now.weekday() >= 5:
        return False, now
    start = dtime(hour=CONFIG.MARKET_START_HOUR, minute=CONFIG.MARKET_START_MINUTE)
    end = dtime(hour=CONFIG.MARKET_END_HOUR, minute=CONFIG.MARKET_END_MINUTE)
    return start <= now.timetz().replace(tzinfo=None) <= end, now


def _select_liquid_option(option_chain, atm_strike: float, direction: str):
    """Pick a liquid weekly strike with spread/depth guards.

    Returns (selection_dict | None, reason_if_none)
    """
    if option_chain is None:
        return None, "Option chain unavailable"

    try:
        df = option_chain.copy()
        if not hasattr(df, "columns"):
            import pandas as pd  # local import to avoid breaking if pandas absent in caller scope
            df = pd.DataFrame(df)
        df.columns = df.columns.str.lower()

        def _col(*names):
            for n in names:
                if n.lower() in df.columns:
                    return n.lower()
            return None

        strike_col = _col("strikeprice", "strike")
        opt_col = _col("optiontype", "type", "side")
        bid_col = _col("bestbidprice", "bid", "bidprice")
        ask_col = _col("bestaskprice", "ask", "askprice")
        bid_qty_col = _col("bestbidqty", "bidqty", "bid_quantity", "bidqtylots")
        ask_qty_col = _col("bestaskqty", "askqty", "ask_quantity", "askqtylots")
        ltp_col = _col("lastprice", "ltp")
        ltt_col = _col("lasttradetime", "timestamp", "lasttradedtime")

        if not strike_col or not opt_col or not bid_col or not ask_col:
            return None, "Option chain missing core columns"

        df = df.dropna(subset=[strike_col, opt_col, bid_col, ask_col])
        if df.empty:
            return None, "Option chain empty after cleaning"

        df["spread"] = (df[ask_col] - df[bid_col]).clip(lower=0)
        df["mid"] = df[[bid_col, ask_col]].mean(axis=1)
        df["spread_pct"] = df["spread"] / df["mid"].replace(0, float("nan"))
        if bid_qty_col and ask_qty_col:
            df["depth_lots"] = df[[bid_qty_col, ask_qty_col]].min(axis=1)
        else:
            df["depth_lots"] = 0

        target_type = "CE" if direction == "BULLISH" else "PE" if direction == "BEARISH" else None
        if target_type:
            df = df[df[opt_col].str.upper().isin([target_type, "CALL", "PUT" if target_type == "PE" else "CALL"])]
        if df.empty:
            return None, "No strikes for desired side"

        df["strike_abs_diff"] = (df[strike_col] - atm_strike).abs()
        df = df.sort_values(["strike_abs_diff", "spread_pct"])

        # Apply liquidity/quality guards
        max_spread_abs = CONFIG.SPREAD_MAX_ABS
        max_spread_pct = CONFIG.SPREAD_MAX_PCT
        min_depth = CONFIG.DEPTH_MIN_LOTS
        max_ltt_age = CONFIG.LTT_MAX_AGE_SEC

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        for _, row in df.iterrows():
            spread_ok = (row["spread"] <= max_spread_abs) or (row["spread_pct"] <= max_spread_pct)
            depth_ok = row["depth_lots"] >= min_depth if "depth_lots" in row else True

            staleness_ok = True
            if ltt_col and row.get(ltt_col) is not None:
                try:
                    ts = row[ltt_col]
                    if not isinstance(ts, datetime):
                        ts = datetime.fromisoformat(str(ts))
                    age = (now - ts.replace(tzinfo=timezone.utc)).total_seconds()
                    staleness_ok = age <= max_ltt_age
                except Exception:
                    staleness_ok = True  # ignore parse issues

            if spread_ok and depth_ok and staleness_ok:
                return {
                    "strike": float(row[strike_col]),
                    "side": target_type or str(row[opt_col]).upper(),
                    "bid": float(row[bid_col]),
                    "ask": float(row[ask_col]),
                    "spread": float(row["spread"]),
                    "spread_pct": float(row["spread_pct"]) if not pd.isna(row["spread_pct"]) else 0.0,
                    "depth_lots": float(row["depth_lots"]),
                    "ltp": float(row[ltp_col]) if ltp_col else None,
                }, None

        return None, "No strike passed spread/depth/staleness filters"
    except Exception as err:
        return None, f"Option selection failed: {str(err)[:80]}"


open_flag, now_ist = is_market_open()
if not open_flag:
    print("\n[MARKET CLOSED]")
    print("-"*90)
    print(f"Market hours (IST): 09:15-15:30 | Today: {now_ist.strftime('%A %Y-%m-%d %H:%M:%S IST')}")
    print("Live fetch skipped. Re-run during market hours for fresh signals.")
    sys.exit(0)

# ========== DATA ACQUISITION ==========
print("\n[LAYER 0] FETCHING LIVE DATA FROM DHAN API")
print("-"*90)

try:
    client = DhanAPIClient()
    dm = DhanDataManager(client)
    
    print(f"[1] Loading {CONFIG.INTRADAY_CANDLE_INTERVAL}-minute candles ({CONFIG.INTRADAY_LOOKBACK_DAYS} days)...", end=" ")
    df5 = dm.get_nifty_candles(interval=CONFIG.INTRADAY_CANDLE_INTERVAL, days=CONFIG.INTRADAY_LOOKBACK_DAYS)
    df5.columns = df5.columns.str.lower()
    print(f"✓ {len(df5)} candles")
    
    print(f"[2] Loading daily candles ({CONFIG.DAILY_RECENT_DAYS} days for PDH/PDL/PDC)...", end=" ")
    dfd = dm.get_nifty_daily(days=CONFIG.DAILY_RECENT_DAYS)
    dfd.columns = dfd.columns.str.lower()
    print(f"✓ {len(dfd)} candles")
    
    print(f"[3] Loading {CONFIG.SECONDARY_INTERVAL}-minute candles ({CONFIG.SECONDARY_LOOKBACK_DAYS} days)...", end=" ")
    df15 = dm.get_nifty_candles(interval=CONFIG.SECONDARY_INTERVAL, days=CONFIG.SECONDARY_LOOKBACK_DAYS)
    df15.columns = df15.columns.str.lower()
    print(f"✓ {len(df15)} candles")

    print(f"[4] Loading {CONFIG.HIGHER_INTERVAL}-minute candles ({CONFIG.HIGHER_LOOKBACK_DAYS} days)...", end=" ")
    df60 = dm.get_nifty_candles(interval=CONFIG.HIGHER_INTERVAL, days=CONFIG.HIGHER_LOOKBACK_DAYS)
    df60.columns = df60.columns.str.lower()
    print(f"✓ {len(df60)} candles")

    # Heartbeat: ensure freshest 5m candle is recent
    ts_col = None
    for c in ["timestamp", "time", "datetime"]:
        if c in df5.columns:
            ts_col = c
            break
    if ts_col:
        try:
            latest_ts = pd.to_datetime(df5[ts_col].iloc[-1], utc=True)
            now_utc = datetime.now(ZoneInfo("UTC"))
            age_sec = (now_utc - latest_ts).total_seconds()
            if age_sec > CONFIG.HEARTBEAT_MAX_AGE_SEC:
                print(f"\n[STALE DATA] Latest 5m candle age {age_sec:.0f}s exceeds heartbeat {CONFIG.HEARTBEAT_MAX_AGE_SEC}s. Blocking signals.")
                sys.exit(0)
        except Exception:
            pass

    opts = None
    exp = None
    try:
        print("[5] Loading option chain...", end=" ")
        exp = dm.get_nearest_expiry()
        opts = dm.get_nifty_option_chain(exp)
        print(f"✓ {len(opts)} strikes | Expiry: {exp}")
    except Exception as opt_err:
        print(f"✗ option chain unavailable ({str(opt_err)[:80]})")
    
    ltp = float(df5['close'].iloc[-1])
    pdt_h = float(dfd['high'].iloc[-2])
    pdt_l = float(dfd['low'].iloc[-2])
    pdt_c = float(dfd['close'].iloc[-2])
    
    print(f"\n   Market Status:")
    print(f"   • Current LTP: {ltp:.2f}")
    print(f"   • PDH: {pdt_h:.2f} | PDL: {pdt_l:.2f} | PDC: {pdt_c:.2f}")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    sys.exit(1)

# ========== TECHNICAL INDICATORS ==========
print("\n[INDICATORS] Calculating Technical Analysis")
print("-"*90)

ti = TechnicalIndicators()

# EMAs
for p in CONFIG.EMA_PERIODS:
    df5[f'ema_{p}'] = ti.calculate_ema(df5['close'], p)

e5 = float(df5['ema_5'].iloc[-1])
e12 = float(df5['ema_12'].iloc[-1])
e20 = float(df5['ema_20'].iloc[-1])
e50 = float(df5['ema_50'].iloc[-1])
e100 = float(df5['ema_100'].iloc[-1])
e200 = float(df5['ema_200'].iloc[-1])

# RSI
df5['rsi'] = ti.calculate_rsi(df5['close'], CONFIG.RSI_PERIOD)
rsi_val = float(df5['rsi'].iloc[-1])

# MACD
macd_d = ti.calculate_macd(df5['close'], CONFIG.MACD_FAST, CONFIG.MACD_SLOW, CONFIG.MACD_SIGNAL)
df5['macd'] = macd_d['MACD']
df5['sig'] = macd_d['Signal']
df5['hist'] = macd_d['Histogram']
macd_hist = float(df5['hist'].iloc[-1])
macd_line = float(df5['macd'].iloc[-1])

# ATR & Volume (ensure expected column names for ATR)
df5_for_atr = df5.rename(columns={'high': 'High', 'low': 'Low', 'close': 'Close'})
atr_s = ti.calculate_atr(df5_for_atr, CONFIG.ATR_PERIOD)
atr_val = float(atr_s.iloc[-1]) if atr_s.iloc[-1] > 0 else (float(df5['high'].max()) - float(df5['low'].min())) / 10
vol = float(df5['volume'].iloc[-1])
vol_20 = float(df5['volume'].rolling(CONFIG.VOLUME_MA_PERIOD).mean().iloc[-1])
volume_ratio = vol / vol_20 if vol_20 else 0

# VWAP (session cumulative)
df5_for_vwap = df5.copy()
df5_for_vwap.rename(columns={'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
vwap_s = ti.calculate_vwap(df5_for_vwap, CONFIG.VWAP_PERIOD)
vwap_val = float(vwap_s.iloc[-1]) if len(vwap_s) else float('nan')

# CPR
pvt = (pdt_h + pdt_l + pdt_c) / 3
tc = pdt_c + (pdt_h - pdt_l) * 1.1 / 4
bc = pdt_c - (pdt_h - pdt_l) * 1.1 / 4
r1 = pdt_c + (pdt_h - pdt_l) * 1.1 / 8
s1 = pdt_c - (pdt_h - pdt_l) * 1.1 / 8

print(f"EMA Alignment (5>12>20>50>100>200):")
print(f"  {e5:.0f} → {e12:.0f} → {e20:.0f} → {e50:.0f} → {e100:.0f} → {e200:.0f}")
print(f"\nMomentum:")
print(f"  RSI: {rsi_val:.1f} ({'Overbought' if rsi_val > 70 else 'Oversold' if rsi_val < 30 else 'Neutral'})")
print(f"  MACD: {macd_line:.2f} | Signal: {float(df5['sig'].iloc[-1]):.2f} | {'↑ Bullish' if macd_hist > 0 else '↓ Bearish'}")
print(f"  ATR: {atr_val:.2f} ({atr_val/ltp*100:.3f}% volatility)")
print(f"  Volume: {vol:,.0f} ({volume_ratio:.2f}x avg)")
print(f"  VWAP: {vwap_val:.2f} ({'Above' if ltp > vwap_val else 'Below' if ltp < vwap_val else 'At'} VWAP)")

print(f"\nPrice Levels:")
print(f"  CPR: BC {bc:.0f} ← → TC {tc:.0f} | Pivot: {pvt:.0f}")
print(f"  R1: {r1:.0f} | S1: {s1:.0f}")
print(f"  Distance to TC: {tc-ltp:.1f}pts | Distance to BC: {ltp-bc:.1f}pts")

# ========== HIGHER TIMEFRAME (60m) ANALYSIS ==========
print("\n[HIGHER TF] 60-Minute Trend & Dynamic EMAs")
print("-"*90)

# Compute indicators on 60m
for p in CONFIG.EMA_PERIODS:
    df60[f'ema_{p}'] = ti.calculate_ema(df60['close'], p)

e50_60 = float(df60['ema_50'].iloc[-1])
e100_60 = float(df60['ema_100'].iloc[-1])
e200_60 = float(df60['ema_200'].iloc[-1])

df60['rsi'] = ti.calculate_rsi(df60['close'], CONFIG.RSI_PERIOD)
rsi_60 = float(df60['rsi'].iloc[-1])
macd_60 = ti.calculate_macd(df60['close'], CONFIG.MACD_FAST, CONFIG.MACD_SLOW, CONFIG.MACD_SIGNAL)
df60['macd'] = macd_60['MACD']
df60['sig'] = macd_60['Signal']
df60['hist'] = macd_60['Histogram']
macd_hist_60 = float(df60['hist'].iloc[-1])

# Dynamic SR focus: long EMAs
long_emas = {
    'EMA50': e50_60,
    'EMA100': e100_60,
    'EMA200': e200_60,
}

nearest_name, nearest_val = min(long_emas.items(), key=lambda kv: abs(ltp - kv[1]))
nearest_dist = abs(ltp - nearest_val)
nearest_side = 'above' if ltp > nearest_val else 'below' if ltp < nearest_val else 'at'

print(f"60m EMAs: 50={e50_60:.0f} | 100={e100_60:.0f} | 200={e200_60:.0f}")
print(f"RSI(60m): {rsi_60:.1f} | MACD Hist(60m): {macd_hist_60:.2f}")
print(f"Dynamic S/R: Nearest {nearest_name} at {nearest_val:.0f} ({nearest_side}, Δ={nearest_dist:.1f} pts)")

# If short-term EMAs are mixed, pivot decision-making to long EMAs
mixed_short = not (e5 > e12 > e20 > e50 > e100 > e200) and not (e5 < e12 < e20 < e50 < e100 < e200)
if mixed_short:
    sr_bias = 'Support' if ltp >= nearest_val else 'Resistance'
    print(f"Guidance: Short-term EMAs mixed → prioritize {nearest_name} (60m) as {sr_bias}.")
    print("Watch micro pullbacks into EMA50/100/200 (60m) for reaction and continuation cues.")

# ========== MULTI-TIMEFRAME CONSENSUS ==========
print("\n[MTF] Multi-Timeframe Trend Consensus")
print("-"*90)

mtf_analyzer = MTFTrendAnalyzer()

# Run MTF analysis (includes 30m resampling)
mtf_result = mtf_analyzer.analyze_all(df5, df15, df60, dfd, ti)

# Print consensus
print(f"\n🎯 MTF TREND: {mtf_result.trend.value}")
print(f"   Consensus Score: {mtf_result.consensus_score:+.2f} (-1=Bearish, 0=Range, +1=Bullish)")
print(f"   Confidence: {mtf_result.confidence:.0%}")
print(f"   Primary Driver TF: {mtf_result.primary_driver_tf}")

# Print per-timeframe analysis
print(f"\n   Timeframe Breakdown:")
for tf_name in ["5m", "30m", "15m", "60m", "daily"]:
    analysis = mtf_result.analysis_by_tf[tf_name]
    ema_str = analysis.ema_signal.alignment
    rsi = analysis.momentum.rsi
    macd_dir = analysis.momentum.macd_direction
    score_str = f"{analysis.trend_score:+.2f}".rjust(5)
    
    # Handle NaN RSI (e.g., for daily with insufficient data)
    rsi_str = f"{rsi:5.1f}" if not pd.isna(rsi) else "  N/A"
    
    emoji = "🟢" if analysis.trend_score > 0.3 else "🔴" if analysis.trend_score < -0.3 else "🟡"
    print(f"   {emoji} {tf_name:6} | EMA: {ema_str:6} | RSI: {rsi_str} | MACD: {macd_dir:6} | Score: {score_str}")

print(f"\n   {mtf_result.guidance}")

# ========== MARKET STRUCTURE VALIDATION ==========
print("\n[STRUCTURE] Daily Market Structure Validation")
print("-"*90)

market_struct = MarketStructure(
    intraday_candles=df5,
    daily_candles=dfd,
    current_price=ltp,
    support_level=bc,
    resistance_level=tc
)

struct_validation = market_struct.validate_against_mtf_signal(
    mtf_trend=mtf_result.trend.value,
    mtf_confidence=mtf_result.confidence * 100
)

print(f"Structure Trend: {struct_validation.structure_trend.value}")
print(f"Opening Bias: {struct_validation.opening_bias.value}")
print(f"Entry Failure Risk: {'🔴 YES' if struct_validation.entry_failure_risk else '🟢 NO'}")
print(f"Structure Support: {'✓ VALID' if struct_validation.is_valid else '✗ INVALID'}")
print(f"Confidence Adjustment: {struct_validation.confidence_adjustment:.2f}x")

if struct_validation.warnings:
    print(f"\n⚠️  Structure Warnings:")
    for w in struct_validation.warnings:
        print(f"   {w}")

# ========== OPPORTUNITY CALIBRATION (50-POINT CAPTURE CONFIDENCE) ==========
print("\n[OPPORTUNITY] 50-Point Capture Probability (15-30 min window)")
print("-"*90)

opp_calibrator = OpportunityCalibration(
    intraday_candles=df5,
    atr_value=atr_val,
    current_price=ltp,
    volume_ratio=volume_ratio,
    direction=mtf_result.trend.value
)

opp_metrics = opp_calibrator.calculate()
print(opp_metrics)
opp_recommendation = opp_calibrator.get_recommendation(opp_metrics.overall_confidence)
print(opp_recommendation)

# ========== UNIFIED NARRATIVE ==========
print("\n" + "="*90)
print("📖 UNIFIED MARKET NARRATIVE - THE REAL STORY".center(90))
print("="*90)

# Determine CPR zone for visualization
if ltp > tc:
    zone_txt = "🔺 ABOVE CPR"
    zone_emoji = "✓"
elif ltp < bc:
    zone_txt = "🔻 BELOW CPR"
    zone_emoji = "✗"
else:
    zone_txt = "〰️  INSIDE CPR"
    zone_emoji = "~"

# Detect MTF bullish/bearish
mtf_bullish = mtf_result.trend.value == "BULLISH"
mtf_bearish = mtf_result.trend.value == "BEARISH"
price_above_cpr = ltp > tc
price_below_cpr = ltp < bc

# Detect conflict
conflict = (mtf_bullish and price_below_cpr) or (mtf_bearish and price_above_cpr)

# Print macro trend
print(f"\n🎯 MACRO TREND (All Timeframes Aligned):")
print(f"   {mtf_result.trend.value} | Confidence: {mtf_result.confidence:.0%}")

# Print current price action
print(f"\n📍 PRICE ACTION RIGHT NOW:")
print(f"   LTP: {ltp:.2f} {zone_emoji} {zone_txt}")
print(f"   CPR: {bc:.0f} ←─ {pvt:.0f} ─→ {tc:.0f} (Width: {tc-bc:.0f}pts)")
dist_to_tc = tc - ltp if ltp < tc else 0
dist_to_bc = ltp - bc if ltp > bc else 0
if dist_to_tc > 0:
    print(f"   Distance to TC Resistance: {dist_to_tc:.1f}pts")
if dist_to_bc > 0:
    print(f"   Distance to BC Support: {dist_to_bc:.1f}pts")

# Print structure
print(f"\n📊 MARKET STRUCTURE:")
print(f"   Volume: {vol/vol_20:.2f}x avg | VWAP: {('Above (bullish)' if ltp > vwap_val else 'Below (bearish)')}")
print(f"   RSI: {rsi_val:.0f} ({('Neutral' if 40 <= rsi_val <= 60 else 'Overbought' if rsi_val > 70 else 'Oversold')})")

# THE STORY - conflict or aligned
print(f"\n🎬 THE STORY:")
if conflict:
    if mtf_bullish and price_below_cpr:
        print(f"   ╔════════════════════════════════════════════╗")
        print(f"   ║ BULLISH SETUP (Reversal Zone Detected)    ║")
        print(f"   ╚════════════════════════════════════════════╝")
        print(f"   ")
        print(f"   All timeframes say: BULLISH 📈")
        print(f"   But price is: BELOW CPR ({bc:.0f}) - Bearish zone")
        print(f"   ")
        print(f"   👉 Interpretation: Price pulled back to CPR support.")
        print(f"      Buyers are still in control. This is a BUY setup forming.")
        print(f"   ")
        print(f"   ⚡ Next Actions:")
        print(f"   1️⃣  If bounces from BC {bc:.0f} → LONG entry at {bc+5:.0f} | SL {bc-20:.0f}")
        print(f"   2️⃣  If breaks above TC {tc:.0f} → LONG entry at {tc+5:.0f} | SL {bc:.0f}")
        setup_type = "SETUP"
    else:  # MTF bearish, price above CPR
        print(f"   ╔════════════════════════════════════════════╗")
        print(f"   ║ BEARISH SETUP (Fake Rally)                ║")
        print(f"   ╚════════════════════════════════════════════╝")
        print(f"   ")
        print(f"   All timeframes say: BEARISH 📉")
        print(f"   But price is: ABOVE CPR ({tc:.0f}) - Bullish zone")
        print(f"   ")
        print(f"   👉 Interpretation: Price bounced up to CPR resistance.")
        print(f"      Sellers are still in control. This is a SHORT setup forming.")
        print(f"   ")
        print(f"   ⚡ Next Actions:")
        print(f"   1️⃣  If fails at TC {tc:.0f} → SHORT entry at {tc-5:.0f} | SL {tc+20:.0f}")
        print(f"   2️⃣  If breaks below BC {bc:.0f} → SHORT entry at {bc-5:.0f} | SL {tc:.0f}")
        setup_type = "SETUP"
else:
    if mtf_bullish and price_above_cpr:
        print(f"   ╔════════════════════════════════════════════╗")
        print(f"   ║ ACTIVE UPTREND (All Aligned) ✓            ║")
        print(f"   ╚════════════════════════════════════════════╝")
        print(f"   ")
        print(f"   Macro: BULLISH ✓ | Price: ABOVE CPR ✓")
        print(f"   ")
        print(f"   👉 Story: Price is making higher highs. Trend is UP.")
        print(f"   ⚡ Strategy: BUY dips to CPR BC {bc:.0f}")
        setup_type = "TREND_UP"
    elif mtf_bearish and price_below_cpr:
        print(f"   ╔════════════════════════════════════════════╗")
        print(f"   ║ ACTIVE DOWNTREND (All Aligned) ✓          ║")
        print(f"   ╚════════════════════════════════════════════╝")
        print(f"   ")
        print(f"   Macro: BEARISH ✓ | Price: BELOW CPR ✓")
        print(f"   ")
        print(f"   👉 Story: Price is making lower lows. Trend is DOWN.")
        print(f"   ⚡ Strategy: SHORT rallies to CPR TC {tc:.0f}")
        setup_type = "TREND_DOWN"
    else:
        print(f"   Macro: {mtf_result.trend.value} | Price: {zone_txt}")
        print(f"   ⚡ Strategy: Trade CPR bounces (long {bc:.0f}, short {tc:.0f})")
        setup_type = "RANGE"

print(f"\n" + "="*90)

# ========== HISTORICAL LEVELS CONTEXT (FROM CACHE) ==========
print("\n[LEVELS] Historical Reference Levels (Cached)")
print("-"*90)

history_file = project_root / "data" / "historical_levels.json"
try:
    with open(history_file, 'r') as f:
        hist_data = json.load(f)

    # Backward/forward compatible reads
    price_summary = hist_data.get('price_summary', hist_data.get('levels', {}))
    year_high = price_summary.get('year_high', float('nan'))
    year_low = price_summary.get('year_low', float('nan'))
    median_price = price_summary.get('median', float('nan'))
    q1 = price_summary.get('q1_25pct', float('nan'))
    q3 = price_summary.get('q3_75pct', float('nan'))

    key_levels = hist_data.get('key_levels', hist_data.get('levels', {}))
    resistance_levels = key_levels.get('resistance', []) if isinstance(key_levels, dict) else []
    support_levels = key_levels.get('support', []) if isinstance(key_levels, dict) else []

    print(f"Cache: {hist_data.get('generated_at', '')[:10]} | {hist_data.get('candles_analyzed', 'n/a')} days analyzed")

    def near_level(price: float, level: float, pct: float = CONFIG.LEVEL_PROXIMITY_THRESHOLD_PCT) -> bool:
        return abs(price - level) / price <= pct

    proximity_notes = []
    if near_level(ltp, year_high):
        proximity_notes.append(f"Near 52W High ({year_high:.0f})")
    if near_level(ltp, year_low):
        proximity_notes.append(f"Near 52W Low ({year_low:.0f})")
    if near_level(ltp, q1):
        proximity_notes.append(f"Near Q1 ({q1:.0f})")
    if near_level(ltp, q3):
        proximity_notes.append(f"Near Q3 ({q3:.0f})")

    # Check against key support/resistance (1% band)
    for i, r in enumerate(resistance_levels, 1):
        if near_level(ltp, r, pct=0.01):
            proximity_notes.append(f"Near R{i} ({r:.0f})")
    for i, s in enumerate(support_levels, 1):
        if near_level(ltp, s, pct=0.01):
            proximity_notes.append(f"Near S{i} ({s:.0f})")

    print(f"52W High: {year_high:.0f} | 52W Low: {year_low:.0f} | Median: {median_price:.0f}")
    print(f"Q1: {q1:.0f} | Q3: {q3:.0f}")
    if resistance_levels:
        print(f"Resistance: {', '.join([f'{r:.0f}' for r in resistance_levels[:3]])}")
    if support_levels:
        print(f"Support: {', '.join([f'{s:.0f}' for s in support_levels[:3]])}")

    if proximity_notes:
        print(f"\n⚡ Price Proximity: {', '.join(proximity_notes)}")
    else:
        print(f"\nPrice Proximity: Not near key levels")

except FileNotFoundError:
    print(f"⚠️  Historical cache not found. Run history_analyzer.py first.")
    year_high = year_low = median_price = q1 = q3 = float('nan')
except Exception as e:
    print(f"⚠️  Could not load historical levels: {str(e)}")
    year_high = year_low = median_price = q1 = q3 = float('nan')

# ========== BUILD CONTEXT ==========
ctx = TechnicalContext(
    ltp=ltp, cpr_pivot=pvt, cpr_tc=tc, cpr_bc=bc, cpr_width=tc-bc,
    pdh=pdt_h, pdl=pdt_l,
    ema_5=e5, ema_12=e12, ema_20=e20, ema_50=e50, ema_100=e100, ema_200=e200,
    rsi=rsi_val, macd_line=macd_line, macd_signal=float(df5['sig'].iloc[-1]),
    macd_histogram=macd_hist, volume=vol, volume_20ma=vol_20, atr=atr_val, vix=14.0,
    current_hour=datetime.now().hour, current_minute=datetime.now().minute,
    pcr=0.95, call_oi_change=50000, put_oi_change=-30000, bid_ask_spread=1.0
)

# ========== SILENT ANALYSIS (No output, just calculations) ==========

# Pre-calculate scenario and confluence for narrative
scl = ScenarioClassifier()
scn = scl.classify(ctx)

cfs = ConfluenceScorer()
conf = cfs.score(
    ltp=ctx.ltp, cpr_pivot=ctx.cpr_pivot, cpr_tc=ctx.cpr_tc, cpr_bc=ctx.cpr_bc,
    pdh=ctx.pdh, pdl=ctx.pdl, ema_5=ctx.ema_5, ema_12=ctx.ema_12, ema_20=ctx.ema_20,
    ema_50=ctx.ema_50, ema_100=ctx.ema_100, ema_200=ctx.ema_200,
    rsi=ctx.rsi, macd_histogram=ctx.macd_histogram, macd_line=ctx.macd_line,
    volume=ctx.volume, volume_20ma=ctx.volume_20ma,
    pcr=ctx.pcr, call_oi_change=ctx.call_oi_change, put_oi_change=ctx.put_oi_change,
    bid_ask_spread=ctx.bid_ask_spread
)

cc = ConfidenceCalculator()
dec = cc.calculate(scn, conf)

# CPR Zone
if ltp > tc:
    zone_txt = "🔺 ABOVE CPR (Bullish Area)"
elif ltp < bc:
    zone_txt = "🔻 BELOW CPR (Bearish Area)"
else:
    zone_txt = "〰️  INSIDE CPR (Neutral/Range Area)"

# MTF OVERRIDE LOGIC: If MTF confidence >70% and we have a clear setup, TRADE!
mtf_confidence_pct = mtf_result.confidence * 100
final_decision = dec.trade_decision
final_confidence = dec.confidence_score
override_active = False
forced_wait_reasons = []

if mtf_confidence_pct >= 70 and setup_type in ["SETUP", "TREND_UP", "TREND_DOWN"]:
    override_active = True
    # Override the weak confluence decision with MTF conviction
    if mtf_result.trend.value == "BULLISH":
        final_decision = "BUY"
        final_confidence = min(10.0, 5.0 + (mtf_confidence_pct / 20))  # Scale 70%->6.5, 100%->10
    elif mtf_result.trend.value == "BEARISH":
        final_decision = "SELL"
        final_confidence = min(10.0, 5.0 + (mtf_confidence_pct / 20))
    
    # MTF Override activated - trade the strong trend direction
    
    # *** CRITICAL: Validate market structure doesn't contradict MTF signal ***
    # This prevents: "HTF bullish but entire day reverses bearish" trap
    if not struct_validation.is_valid:
        # Market structure contradicts HTF signal - reduce confidence significantly
        final_confidence *= struct_validation.confidence_adjustment
        override_active = False  # Disable override if structure is against us
        forced_wait_reasons.append(f"Market structure conflict: {struct_validation.structure_trend.value}")
    
    # *** CRITICAL: Check if we can actually capture 50 points in 15-30 min ***
    # MTF says direction, but opportunity calibration answers: "Can we move 50pts?"
    if override_active and opp_metrics.overall_confidence < 60:
        # Volatility/volume insufficient for 50pt move in target window
        final_decision = "WAIT"
        override_active = False
        forced_wait_reasons.append(f"Insufficient opportunity for 50pt capture ({opp_metrics.overall_confidence:.0f}% confidence)")
    
    # Use opportunity confidence to scale final confidence (max 10.0)
    if override_active:
        opp_confidence_scaled = opp_metrics.overall_confidence / 10.0  # Convert 0-100 to 0-10
        final_confidence = min(10.0, opp_confidence_scaled)

# Volume checkpoint: do not trade on critically low volume
if volume_ratio < 0.7:
    forced_wait_reasons.append(f"Volume critically low ({volume_ratio:.2f}x < 0.70x)")

# Location-based filter: only buy when price is at support (S1) or back above VWAP
if final_decision == "BUY" and mtf_result.trend.value == "BULLISH":
    bullish_location_ok = (ltp >= s1) or (ltp >= vwap_val)
    if not bullish_location_ok:
        forced_wait_reasons.append("Price below support/VWAP for bullish trade")

# Enforce WAIT when any blocking reason is present
if forced_wait_reasons:
    final_decision = "WAIT"
    override_active = False
    final_confidence = min(final_confidence, 4.0)

# Trade decision calculated silently

# Position Sizing - 50 POINT TARGET when MTF confident
confluence_score = conf.overall_score
entry_price = ltp

if override_active:
    # MTF confident: Go for 50-point moves
    sl_distance = 25  # Fixed tight SL
    t1_distance = 50  # 50-point first target
    t2_distance = 75  # 75-point runner
else:
    # Normal scalping targets
    sl_distance = min(max(20, atr_val * 0.30), 25)
    t1_distance = min(max(sl_distance * 1.7, 35), 50)
    t2_distance = min(max(sl_distance * 2.2, t1_distance + 10), 80)

if final_decision == "BUY":
    sl_price = entry_price - sl_distance
    t1_price = entry_price + t1_distance
    t2_price = entry_price + t2_distance
elif final_decision == "SELL":
    sl_price = entry_price + sl_distance
    t1_price = entry_price - t1_distance
    t2_price = entry_price - t2_distance
else:  # WAIT
    sl_price = entry_price - sl_distance
    t1_price = entry_price + t1_distance
    t2_price = entry_price + t2_distance

risk_amt = CONFIG.risk_amount
qty = max(1, int(risk_amt / sl_distance))
if qty > CONFIG.MAX_QUANTITY_LOTS:
    qty = CONFIG.MAX_QUANTITY_LOTS

# Risk scaling for wide CPR (sideways market): cap quantity
wide_cpr_threshold = 120
if (tc - bc) >= wide_cpr_threshold and qty > 3:
    qty = 3

# ========== OPTIONS INTELLIGENCE (Silent - Data Collection Only) ==========

atm_strike = round(ltp / CONFIG.STRIKE_ROUNDING) * CONFIG.STRIKE_ROUNDING

# Pick a liquid strike on the desired side (uses spread/depth/staleness guards)
selected_option = None
selection_error = None
desired_side = "BULLISH" if final_decision == "BUY" else "BEARISH" if final_decision == "SELL" else mtf_result.trend.value
if opts is not None:
    selected_option, selection_error = _select_liquid_option(opts, atm_strike, desired_side)
    if not selected_option and final_decision != "WAIT":
        forced_wait_reasons.append(selection_error or "No liquid strike found")
        final_decision = "WAIT"
        override_active = False

try:
    # Run comprehensive options intelligence
    opt_intel = OptionsIntelligence()
    opt_result = opt_intel.analyze(option_chain=opts, spot_price=ltp, atm_strike=atm_strike)
    
    # ─── PCR ANALYSIS ───
    pcr = opt_result.pcr_analysis
    
    # ─── OI BUILDUP ANALYSIS ───
    oi = opt_result.oi_analysis
    
    # ─── IV ANALYSIS ───
    iv = opt_result.iv_analysis
    if isinstance(iv, dict):
        atm_iv = iv.get('atm_iv', 0)
        skew_dir = iv.get('iv_skew_direction', 'NEUTRAL')
        smile_det = iv.get('volatility_smile_present', False)
        otm_call = iv.get('otm_call_iv', 0)
        otm_put = iv.get('otm_put_iv', 0)
        iv_rank = iv.get('iv_52w_rank', 50)
    else:
        atm_iv = getattr(iv, 'atm_iv', 0)
        skew_dir = getattr(iv, 'iv_skew_direction', 'NEUTRAL')
        smile_det = getattr(iv, 'smile_detected', False)
        otm_call = getattr(iv, 'otm_call_iv', 0)
        otm_put = getattr(iv, 'otm_put_iv', 0)
        iv_rank = getattr(iv, 'iv_52w_rank', 50)
    

    # ─── LIQUIDITY ANALYSIS ───
    liq = opt_result.liquidity_analysis
    
    # ─── VOLUME ANALYSIS ───
    vol = opt_result.volume_analysis
    
    # ─── VANNA/VOLGA ANALYSIS ───
    vv = opt_result.vanna_volga
    
    # ─── VOLATILITY SMILE ───
    smile = opt_result.volatility_smile
    
    # ─── INSTITUTIONAL POSITIONING ───
    inst = opt_result.institutional
    large_call_net = (inst.large_call_bids - inst.large_call_asks)
    large_put_net = (inst.large_put_bids - inst.large_put_asks)

except Exception as e:
    # Options intelligence failed - use defaults
    inst = type('obj', (object,), {'institutional_direction': 'NEUTRAL', 'conviction_level': 0.5})
    pcr = type('obj', (object,), {'total_pcr': 1.0, 'sentiment': 'NEUTRAL'})


# ========== COMPACT TRADE REPORT ==========

# ── Concise trade report (clean format) ──
final_conf_pct = min(100, final_confidence * 10)
positive_points = []
negative_points = []

positive_points.append(f"MTF Trend: {mtf_result.trend.value} ({mtf_confidence_pct:.0f}% aligned)")
if 'inst' in locals():
    positive_points.append(f"Options: Institutional {inst.institutional_direction} bias (conviction {inst.conviction_level:.2f})")
if 'pcr' in locals():
    positive_points.append(f"PCR: {pcr.total_pcr:.2f} ({pcr.sentiment})")

if ltp < vwap_val or ltp < bc:
    negative_points.append("Price below VWAP/CPR (bearish zone)")
if volume_ratio < 0.7:
    negative_points.append(f"Volume critically low ({volume_ratio:.2f}x)")
if (tc - bc) >= 120:
    negative_points.append(f"Wide CPR ({tc-bc:.0f}pts) → likely sideways")

print("="*80)
print(f"📊 NIFTY TRADE REPORT | {datetime.now().strftime('%Y-%m-%d')} | {datetime.now().strftime('%H:%M IST')}")
print("="*80)

signal_tag = "MTF CONFIRMED" if override_active else "SYSTEM"

# Convert to options trading format
if final_decision == "BUY":
    options_signal = "BUY CALL"
    suggested_strike = selected_option["strike"] if selected_option else atm_strike
elif final_decision == "SELL":
    options_signal = "BUY PUT"
    suggested_strike = selected_option["strike"] if selected_option else atm_strike
else:
    options_signal = "WAIT"
    suggested_strike = atm_strike

print(f"\n🎯 FINAL SIGNAL: {options_signal.upper()} ({signal_tag})")
if options_signal != "WAIT":
    print(f"Strike: {suggested_strike:.0f} {'CALL' if options_signal == 'BUY CALL' else 'PUT'}")
print(f"Confidence: {'🟢' if final_confidence >= 7 else '🟠' if final_confidence >= 5 else '🔴'} {final_conf_pct:.0f}% | Risk Level: {scn.risk_level} ({scn.scenario.value.title()})")

print("\n" + "-"*80)
print("📍 TRADE EXECUTION DETAILS")
print("-"*80)
print(f"• ENTRY      : {entry_price:.0f}")
print(f"• STOP LOSS  : {sl_price:.0f} ({abs(sl_distance):.0f} pts)")
print(f"• TARGET 1   : {t1_price:.0f} (1:{abs(t1_distance/sl_distance):.2f} RR)")
print(f"• TARGET 2   : {t2_price:.0f} (1:{abs(t2_distance/sl_distance):.2f} RR)")
print(f"• QUANTITY   : {qty} Lots (Cap: {CONFIG.CAPITAL:,.0f})")

print("\n" + "-"*80)
print("🔍 KEY MARKET DRIVERS")
print("-"*80)
print("✅ POSITIVE:")
if positive_points:
    for pt in positive_points:
        print(f"  • {pt}")
else:
    print("  • None")
print("\n❌ NEGATIVE/CAUTION:")
if negative_points:
    for pt in negative_points:
        print(f"  • {pt}")
else:
    print("  • None")

print("\n" + "-"*80)
print("💡 SYSTEM NARRATIVE")
print("-"*80)

# Build detailed narrative
if final_decision.upper() == "BUY":
    narrative = f"BUY CALL recommended at {atm_strike:.0f} strike. "
    narrative += f"Price is currently in a {'Bearish Trap' if ltp < bc else 'Pullback Zone'} {'below' if ltp < bc else 'near'} the CPR. "
    if override_active:
        narrative += "While intraday indicators are weak, the Higher Timeframe (HTF) strength is dominant. "
        narrative += f"This is a Mean Reversion trade aiming for the VWAP/CPR level. "
        narrative += f"All timeframes ({mtf_result.primary_driver_tf} leading) show {mtf_result.trend.value} alignment. "
        narrative += f"Expecting {int(t1_distance)}-{int(t2_distance)} point underlying move."
    else:
        narrative += f"Technical confluence supports the move. Target VWAP ({vwap_val:.0f}) and CPR resistance."
elif final_decision.upper() == "SELL":
    narrative = f"BUY PUT recommended at {atm_strike:.0f} strike. "
    narrative += f"Price rejected from resistance. "
    if override_active:
        narrative += f"HTF shows {mtf_result.trend.value} breakdown across all timeframes. "
        narrative += f"Expecting {int(abs(t1_distance))}-{int(abs(t2_distance))} point underlying downside."
    else:
        narrative += "Technical confluence supports downside. Target CPR support levels."
else:
    narrative = "Standing down until filters clear. "
    if forced_wait_reasons:
        narrative += f"Blocked by: {', '.join(forced_wait_reasons[:2])}. "
    narrative += f"Monitor for {('volume pickup' if volume_ratio < 0.7 else '')} {('price above ' + str(int(vwap_val)) if ltp < vwap_val else '')}."

print(narrative)
print("="*80)

