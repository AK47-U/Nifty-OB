#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HISTORICAL LEVEL ANALYZER - MONTHLY RUN
Calculates and caches 52-week levels, support/resistance from 1-year data
Run this script once per month to update historical reference levels
"""

import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from integrations import DhanDataManager, DhanAPIClient
from config.trading_config import CONFIG

CACHE_FILE = project_root / "data" / "historical_levels.json"

print("\n" + "="*90)
print("HISTORICAL LEVEL ANALYZER - MONTHLY UPDATE".center(90))
print("="*90)

try:
    client = DhanAPIClient()
    dm = DhanDataManager(client)
    
    print(f"\n[1] Fetching {CONFIG.DAILY_LOOKBACK_DAYS} days of historical data...")
    dfd = dm.get_nifty_daily(days=CONFIG.DAILY_LOOKBACK_DAYS)
    dfd.columns = dfd.columns.str.lower()
    print(f"✓ Loaded {len(dfd)} daily candles")
    
    # Calculate key levels
    print("\n[2] Computing historical levels...")
    
    year_high = float(dfd['high'].max())
    year_low = float(dfd['low'].min())
    median_price = float(dfd['close'].median())
    mean_price = float(dfd['close'].mean())
    q1 = float(dfd['close'].quantile(0.25))
    q3 = float(dfd['close'].quantile(0.75))
    
    # Volatility metrics
    daily_returns = dfd['close'].pct_change()
    volatility = float(daily_returns.std() * (252 ** 0.5))  # Annualized
    
    # Detect key levels and their test history
    print("\n[3] Analyzing level tests and responses...")
    
    # Find all significant price levels (highs and lows)
    all_levels = []
    for i in range(5, len(dfd) - 5):
        window = dfd.iloc[i-5:i+6]
        current_high = dfd['high'].iloc[i]
        current_low = dfd['low'].iloc[i]
        
        if current_high == window['high'].max():
            all_levels.append({
                'level': float(current_high),
                'date': dfd.index[i],
                'type': 'resistance'
            })
        if current_low == window['low'].min():
            all_levels.append({
                'level': float(current_low),
                'date': dfd.index[i],
                'type': 'support'
            })
    
    # Group levels by proximity (within 100 points)
    level_groups = {}
    for level_info in all_levels:
        level = level_info['level']
        matched = False
        for existing_level in level_groups:
            if abs(existing_level - level) <= 100:
                level_groups[existing_level].append(level_info)
                matched = True
                break
        if not matched:
            level_groups[level] = [level_info]
    
    # Calculate level statistics
    level_profiles = {}
    for primary_level, tests in level_groups.items():
        if len(tests) < 2:
            continue  # Only include levels tested 2+ times
        
        test_count = len(tests)
        test_dates = [t['date'] for t in tests]
        test_types = [t['type'] for t in tests]
        
        # Analyze outcomes after each test
        outcomes = []
        for test_info in tests:
            test_date = test_info['date']
            test_idx = dfd.index.get_loc(test_date) if test_date in dfd.index else -1
            
            if test_idx >= 0 and test_idx < len(dfd) - 5:
                # Check next 5 candles for response
                next_5 = dfd.iloc[test_idx+1:test_idx+6]
                if len(next_5) > 0:
                    next_high = next_5['high'].max()
                    next_low = next_5['low'].min()
                    close_move = next_5['close'].iloc[-1] - dfd['close'].iloc[test_idx]
                    
                    # Classify outcome
                    if test_info['type'] == 'resistance':
                        if next_high > primary_level * 1.005:
                            outcome = 'BREAKOUT_UP'
                        elif next_low < primary_level * 0.995:
                            outcome = 'REJECTION_DOWN'
                        else:
                            outcome = 'CONSOLIDATION'
                    else:  # support
                        if next_low < primary_level * 0.995:
                            outcome = 'BREAKDOWN'
                        elif next_high > primary_level * 1.005:
                            outcome = 'BOUNCE_UP'
                        else:
                            outcome = 'CONSOLIDATION'
                    
                    outcomes.append({
                        'date': str(test_date),
                        'type': test_info['type'],
                        'outcome': outcome,
                        'close_move_pts': float(close_move),
                        'close_move_pct': float((close_move / primary_level) * 100)
                    })
        
        if outcomes:
            # Calculate success rate
            bullish_outcomes = sum(1 for o in outcomes if 'UP' in o['outcome'] or 'BREAKOUT' in o['outcome'])
            success_rate = (bullish_outcomes / len(outcomes)) * 100 if outcomes else 0
            
            level_profiles[float(primary_level)] = {
                'test_count': test_count,
                'first_tested': min([str(d) for d in test_dates]),
                'last_tested': max([str(d) for d in test_dates]),
                'test_history': outcomes[:5],  # Last 5 tests
                'success_rate': float(success_rate),
                'level_strength': 'STRONG' if success_rate >= 70 else 'MODERATE' if success_rate >= 40 else 'WEAK',
                'avg_response_pts': float(sum(o['close_move_pts'] for o in outcomes) / len(outcomes)),
                'test_types': list(set(test_types))
            }
    
    # Sort by test frequency
    level_profiles = dict(sorted(level_profiles.items(), 
                                key=lambda x: x[1]['test_count'], 
                                reverse=True))
    
    # Keep top 10 most tested levels
    top_levels = dict(list(level_profiles.items())[:10])
    
    # Separate into resistance and support
    resistance_levels = sorted([k for k in top_levels.keys() if 'resistance' in str(top_levels[k]['test_types'])], reverse=True)[:5]
    support_levels = sorted([k for k in top_levels.keys() if 'support' in str(top_levels[k]['test_types'])])[:5]
    
    # IV estimates from ATR (last 90 days)
    recent = dfd.tail(90)
    recent_atr = recent['high'] - recent['low']
    avg_atr = float(recent_atr.mean())
    iv_estimate = float((avg_atr / recent['close'].mean()) * (252 ** 0.5))
    
    # Additional statistics
    daily_close_changes = dfd['close'].pct_change().dropna()
    avg_daily_move = float(daily_close_changes.abs().mean() * 100)
    max_daily_gain = float(daily_close_changes.max() * 100)
    max_daily_loss = float(daily_close_changes.min() * 100)
    
    # Win rate across all tested levels
    total_tests = sum(p['test_count'] for p in top_levels.values())
    total_bullish = sum(len([o for o in p['test_history'] if 'UP' in o['outcome'] or 'BREAKOUT' in o['outcome']]) 
                       for p in top_levels.values())
    overall_win_rate = (total_bullish / total_tests * 100) if total_tests > 0 else 0
    
    # Price distribution
    price_std = float(dfd['close'].std())
    price_cv = float(price_std / dfd['close'].mean())  # Coefficient of variation
    
    historical_data = {
        "generated_at": datetime.now().isoformat(),
        "data_period_days": CONFIG.DAILY_LOOKBACK_DAYS,
        "candles_analyzed": len(dfd),
        "price_summary": {
            "current_close": float(dfd['close'].iloc[-1]),
            "year_high": year_high,
            "year_low": year_low,
            "year_range": year_high - year_low,
            "year_range_pct": ((year_high - year_low) / year_low) * 100,
            "median": median_price,
            "mean": mean_price,
            "std_dev": float(price_std),
            "coefficient_of_variation": float(price_cv)
        },
        "quartiles": {
            "q1_25pct": q1,
            "q2_median": median_price,
            "q3_75pct": q3,
            "q1_q3_range": q3 - q1
        },
        "key_levels": {
            "resistance": resistance_levels,
            "support": support_levels
        },
        "level_profiles": top_levels,
        "level_statistics": {
            "total_distinct_levels": len(top_levels),
            "total_level_tests": total_tests,
            "overall_success_rate": float(overall_win_rate),
            "avg_tests_per_level": float(total_tests / len(top_levels)) if top_levels else 0,
            "strongest_level": max(top_levels.items(), key=lambda x: x[1]['success_rate'])[0] if top_levels else None,
            "most_tested_level": max(top_levels.items(), key=lambda x: x[1]['test_count'])[0] if top_levels else None
        },
        "volatility": {
            "annualized_volatility": float(volatility),
            "annualized_volatility_pct": float(volatility * 100),
            "daily_avg_move_pct": float(avg_daily_move),
            "max_single_day_gain_pct": float(max_daily_gain),
            "max_single_day_loss_pct": float(max_daily_loss),
            "atr_90day_avg": float(avg_atr)
        },
        "iv_metrics": {
            "iv_estimate": float(iv_estimate),
            "iv_estimate_pct": float(iv_estimate * 100),
            "iv_52w_high_estimate": CONFIG.IV_52W_HIGH_ESTIMATE * 100,
            "iv_52w_low_estimate": CONFIG.IV_52W_LOW_ESTIMATE * 100,
            "iv_current_rank": "MEDIUM"  # Can be calculated based on recent vs 52W
        },
        "recent_metrics": {
            "last_90_days_high": float(dfd.tail(90)['high'].max()),
            "last_90_days_low": float(dfd.tail(90)['low'].min()),
            "last_30_days_high": float(dfd.tail(30)['high'].max()),
            "last_30_days_low": float(dfd.tail(30)['low'].min()),
            "last_10_days_avg_volume": float(dfd.tail(10)['volume'].mean())
        }
    }
    
    print(f"\n[3] Saving to {CACHE_FILE.name}...")
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(historical_data, f, indent=2)
    
    print("\n" + "="*90)
    print("HISTORICAL LEVELS SUMMARY".center(90))
    print("="*90)
    print(f"\nPrice Summary ({CONFIG.DAILY_LOOKBACK_DAYS} days):")
    print(f"  52W High: {year_high:,.0f}")
    print(f"  52W Low:  {year_low:,.0f}")
    print(f"  Range: {year_high - year_low:.0f} points ({((year_high - year_low) / year_low) * 100:.1f}%)")
    
    print(f"\nPrice Quartiles:")
    print(f"  Q1 (25%): {q1:,.0f}")
    print(f"  Median:   {median_price:,.0f}")
    print(f"  Q3 (75%): {q3:,.0f}")
    print(f"  Mean:     {mean_price:,.0f}")
    print(f"  Std Dev:  {price_std:.0f} | CV: {price_cv:.2%}")
    
    print(f"\nVolatility Metrics:")
    print(f"  Annualized Vol: {volatility:.2%}")
    print(f"  Daily Avg Move: {avg_daily_move:.2f}%")
    print(f"  Max Daily Gain: {max_daily_gain:.2f}%")
    print(f"  Max Daily Loss: {max_daily_loss:.2f}%")
    print(f"  Avg ATR (90d): {avg_atr:.0f} points")
    
    print(f"\nIV Metrics:")
    print(f"  IV Estimate: {iv_estimate:.2%}")
    print(f"  52W Est. Range: {CONFIG.IV_52W_LOW_ESTIMATE:.2%} - {CONFIG.IV_52W_HIGH_ESTIMATE:.2%}")
    
    print(f"\nLevel Testing Summary:")
    print(f"  Total Distinct Levels: {len(top_levels)}")
    print(f"  Total Tests Across Levels: {total_tests}")
    print(f"  Overall Success Rate: {overall_win_rate:.0f}%")
    print(f"  Avg Tests per Level: {total_tests / len(top_levels):.1f}" if top_levels else "  No levels")
    
    print(f"\nKey Resistance Levels:")
    for i, r in enumerate(resistance_levels, 1):
        profile = top_levels.get(r, {})
        test_cnt = profile.get('test_count', 0)
        strength = profile.get('level_strength', 'N/A')
        success = profile.get('success_rate', 0)
        print(f"  R{i}: {r:,.0f} | Tested {test_cnt}x | {strength} ({success:.0f}% success)")
    
    print(f"\nKey Support Levels:")
    for i, s in enumerate(support_levels, 1):
        profile = top_levels.get(s, {})
        test_cnt = profile.get('test_count', 0)
        strength = profile.get('level_strength', 'N/A')
        success = profile.get('success_rate', 0)
        print(f"  S{i}: {s:,.0f} | Tested {test_cnt}x | {strength} ({success:.0f}% success)")
    
    print(f"\nMost Tested Levels (Top 5):")
    for i, (level, profile) in enumerate(list(top_levels.items())[:5], 1):
        print(f"  {i}. {level:,.0f}: Tested {profile['test_count']}x | {profile['level_strength']} | Avg Response: {profile['avg_response_pts']:.0f}pts")
    
    print("\n" + "="*90)
    print(f"✅ Historical levels cached successfully")
    print(f"📅 Next update recommended: {(datetime.now().replace(day=1).replace(month=datetime.now().month % 12 + 1)).strftime('%Y-%m-%d')}")
    print("="*90 + "\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
