import yfinance as yf
import pandas as pd
import numpy as np
import talib
import sys
import os

def test_multiple_timeframes():
    """Test RSI with multiple timeframes to match trading chart"""
    print("📊 Testing RSI with Multiple Timeframes")
    print("=" * 60)
    
    timeframes = [
        ('5d', '1h', 'Hourly'),
        ('1mo', '1d', 'Daily'),
        ('3mo', '1wk', 'Weekly'),
        ('2d', '5m', '5-Minute'),
        ('1d', '15m', '15-Minute'),
        ('1d', '30m', '30-Minute')
    ]
    
    ticker = yf.Ticker('^BSESN')
    
    print(f"🎯 Target Chart Values:")
    print(f"   RSI: 72.27")
    print(f"   Price: ₹84,653.99\n")
    
    for period, interval, name in timeframes:
        try:
            print(f"📈 {name} Data ({period}, {interval}):")
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                print(f"   ❌ No data available\n")
                continue
                
            current_price = data['Close'].iloc[-1]
            
            # Calculate RSI using TA-Lib
            rsi_values = talib.RSI(data['Close'].values, timeperiod=14)
            current_rsi = rsi_values[-1] if not np.isnan(rsi_values[-1]) else None
            
            if current_rsi:
                diff_from_target = abs(current_rsi - 72.27)
                match_quality = "🎯 EXCELLENT" if diff_from_target < 1 else "🟢 GOOD" if diff_from_target < 3 else "🟡 FAIR" if diff_from_target < 5 else "🔴 POOR"
                
                print(f"   Price: ₹{current_price:,.2f}")
                print(f"   RSI: {current_rsi:.2f} (Diff: {diff_from_target:.2f}) {match_quality}")
                print(f"   Data points: {len(data)}")
            else:
                print(f"   ❌ RSI calculation failed")
            
            print()
            
        except Exception as e:
            print(f"   ❌ Error: {e}\n")

def test_different_rsi_periods():
    """Test different RSI periods to see if chart uses non-standard period"""
    print("📊 Testing Different RSI Periods")
    print("=" * 50)
    
    ticker = yf.Ticker('^BSESN')
    data = ticker.history(period='1mo', interval='1d')  # Daily data
    
    if data.empty:
        print("❌ No data available")
        return
    
    current_price = data['Close'].iloc[-1]
    print(f"💰 Current Price: ₹{current_price:,.2f}")
    print(f"📈 Using Daily Data\n")
    
    # Test different RSI periods
    periods = [9, 10, 14, 21, 25]
    
    for period in periods:
        rsi_values = talib.RSI(data['Close'].values, timeperiod=period)
        current_rsi = rsi_values[-1] if not np.isnan(rsi_values[-1]) else None
        
        if current_rsi:
            diff_from_target = abs(current_rsi - 72.27)
            match_quality = "🎯 MATCH!" if diff_from_target < 0.5 else "🟢 CLOSE" if diff_from_target < 2 else "🟡 FAIR" if diff_from_target < 5 else "🔴 FAR"
            print(f"RSI({period:2d}): {current_rsi:6.2f} (Diff: {diff_from_target:5.2f}) {match_quality}")

def test_nse_alternative():
    """Test alternative ticker symbols for SENSEX"""
    print("\n📊 Testing Alternative SENSEX Symbols")
    print("=" * 50)
    
    symbols = ['^BSESN', 'SENSEX.BO', '^BSESN.BO']
    
    for symbol in symbols:
        try:
            print(f"🔍 Testing {symbol}:")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='5d', interval='1d')
            
            if data.empty:
                print(f"   ❌ No data available\n")
                continue
            
            current_price = data['Close'].iloc[-1]
            rsi_values = talib.RSI(data['Close'].values, timeperiod=14)
            current_rsi = rsi_values[-1] if not np.isnan(rsi_values[-1]) else None
            
            if current_rsi:
                diff = abs(current_rsi - 72.27)
                print(f"   Price: ₹{current_price:,.2f}")
                print(f"   RSI: {current_rsi:.2f} (Diff: {diff:.2f})")
                print(f"   Data points: {len(data)}")
            
            print()
            
        except Exception as e:
            print(f"   ❌ Error: {e}\n")

if __name__ == "__main__":
    test_multiple_timeframes()
    test_different_rsi_periods()
    test_nse_alternative()
