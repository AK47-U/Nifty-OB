import yfinance as yf
import pandas as pd
import numpy as np
import talib
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_with_talib():
    """Test using TA-Lib library for standard calculations"""
    print("📊 Testing with TA-Lib (Standard Library)")
    print("=" * 50)
    
    try:
        # Get current SENSEX data - shorter timeframe for more recent analysis
        ticker = yf.Ticker('^BSESN')
        data = ticker.history(period='2d', interval='1m')  # 2 days of 1-minute data
        
        if data.empty:
            print("❌ No data available")
            return
        
        current_price = data['Close'].iloc[-1]
        print(f"💰 Current SENSEX Price: ₹{current_price:,.2f}")
        print(f"📈 Data Points: {len(data)} (1-minute bars)")
        
        # Calculate RSI using TA-Lib
        rsi = talib.RSI(data['Close'].values, timeperiod=14)
        current_rsi = rsi[-1] if not np.isnan(rsi[-1]) else None
        
        if current_rsi:
            print(f"📊 RSI (14): {current_rsi:.2f}")
            if current_rsi > 70:
                rsi_status = "🔴 Overbought"
            elif current_rsi < 30:
                rsi_status = "🟢 Oversold"
            else:
                rsi_status = "🟡 Neutral"
            print(f"   Status: {rsi_status}")
        
        # Calculate EMAs using TA-Lib
        ema_5 = talib.EMA(data['Close'].values, timeperiod=5)[-1]
        ema_10 = talib.EMA(data['Close'].values, timeperiod=10)[-1]
        ema_20 = talib.EMA(data['Close'].values, timeperiod=20)[-1]
        ema_50 = talib.EMA(data['Close'].values, timeperiod=50)[-1]
        
        print(f"\n📈 EMA Values (TA-Lib):")
        print(f"   EMA 5:  ₹{ema_5:,.2f}")
        print(f"   EMA 10: ₹{ema_10:,.2f}")
        print(f"   EMA 20: ₹{ema_20:,.2f}")
        print(f"   EMA 50: ₹{ema_50:,.2f}")
        
        # Calculate MACD using TA-Lib
        macd, macd_signal, macd_hist = talib.MACD(data['Close'].values)
        current_macd = macd[-1] if not np.isnan(macd[-1]) else None
        current_signal = macd_signal[-1] if not np.isnan(macd_signal[-1]) else None
        
        if current_macd and current_signal:
            print(f"\n📈 MACD (TA-Lib):")
            print(f"   MACD: {current_macd:.2f}")
            print(f"   Signal: {current_signal:.2f}")
            print(f"   Status: {'🟢 Bullish' if current_macd > current_signal else '🔴 Bearish'}")
        
        print(f"\n🎯 COMPARISON WITH CHART:")
        print(f"   Chart RSI: 72.27")
        print(f"   Our RSI:   {current_rsi:.2f}" if current_rsi else "   Our RSI:   N/A")
        print(f"   Chart Price: ₹84,653.99")
        print(f"   Our Price:   ₹{current_price:,.2f}")
        
        # The difference might be due to:
        print(f"\n💡 Possible reasons for differences:")
        print(f"   1. Different data sources (Chart vs Yahoo Finance)")
        print(f"   2. Different timeframes (Chart might use different interval)")
        print(f"   3. Real-time vs delayed data")
        print(f"   4. Different calculation methods")
        
    except ImportError:
        print("❌ TA-Lib not available. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "TA-Lib"])
        print("🔄 Please run the test again after TA-Lib installation.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_manual_calculation():
    """Test with manual RSI calculation matching TradingView formula"""
    print("\n📊 Testing Manual RSI (TradingView Method)")
    print("=" * 50)
    
    # Get data
    ticker = yf.Ticker('^BSESN')
    data = ticker.history(period='1d', interval='1m')  # Current day 1-minute data
    
    if data.empty:
        print("❌ No intraday data available")
        return
    
    close_prices = data['Close']
    current_price = close_prices.iloc[-1]
    
    # Manual RSI calculation (TradingView style)
    def calculate_rsi_tv_style(prices, period=14):
        delta = prices.diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Use RMA (Running Moving Average) - TradingView's method
        alpha = 1 / period
        avg_gain = gains.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = losses.ewm(alpha=alpha, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    rsi = calculate_rsi_tv_style(close_prices)
    current_rsi = rsi.iloc[-1]
    
    print(f"💰 Current Price: ₹{current_price:,.2f}")
    print(f"📊 RSI (TradingView Method): {current_rsi:.2f}")
    print(f"📈 Data Points: {len(data)}")
    
    if current_rsi > 70:
        status = "🔴 Overbought"
    elif current_rsi < 30:
        status = "🟢 Oversold" 
    else:
        status = "🟡 Neutral"
    print(f"   Status: {status}")

if __name__ == "__main__":
    test_with_talib()
    test_manual_calculation()
