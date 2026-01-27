import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def calculate_rsi_wilder(close_prices, period=14):
    """Calculate RSI using Wilder's smoothing method"""
    delta = close_prices.diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    
    # Calculate initial averages using simple mean
    avg_gain = gains.rolling(window=period, min_periods=period).mean()
    avg_loss = losses.rolling(window=period, min_periods=period).mean()
    
    # Apply Wilder's smoothing for subsequent values
    for i in range(period, len(gains)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period-1) + gains.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period-1) + losses.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def test_technical_indicators():
    """Test technical indicators with current SENSEX data"""
    print("📊 Testing Technical Indicators with Real Data")
    print("=" * 50)
    
    # Get current SENSEX data
    ticker = yf.Ticker('^BSESN')
    data = ticker.history(period='5d', interval='5m')
    
    if data.empty:
        print("❌ No data available")
        return
    
    current_price = data['Close'].iloc[-1]
    print(f"💰 Current SENSEX Price: ₹{current_price:,.2f}")
    print(f"📈 Data Points Available: {len(data)}")
    
    # Calculate RSI
    rsi = calculate_rsi_wilder(data['Close'])
    current_rsi = rsi.iloc[-1]
    print(f"📊 RSI (14): {current_rsi:.2f}")
    
    # RSI status
    if current_rsi > 70:
        rsi_status = "🔴 Overbought"
    elif current_rsi < 30:
        rsi_status = "🟢 Oversold"
    else:
        rsi_status = "🟡 Neutral"
    print(f"   Status: {rsi_status}")
    
    # Calculate EMAs
    ema_5 = data['Close'].ewm(span=5, adjust=False).mean().iloc[-1]
    ema_10 = data['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
    ema_20 = data['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
    ema_50 = data['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    
    print(f"\n📈 EMA Values:")
    print(f"   EMA 5:  ₹{ema_5:,.2f}")
    print(f"   EMA 10: ₹{ema_10:,.2f}")
    print(f"   EMA 20: ₹{ema_20:,.2f}")
    print(f"   EMA 50: ₹{ema_50:,.2f}")
    
    # EMA alignment check
    emas = [ema_5, ema_10, ema_20, ema_50]
    bullish_alignment = all(emas[i] >= emas[i+1] for i in range(len(emas)-1))
    bearish_alignment = all(emas[i] <= emas[i+1] for i in range(len(emas)-1))
    
    if bullish_alignment:
        alignment_status = "🟢 Bullish Alignment"
    elif bearish_alignment:
        alignment_status = "🔴 Bearish Alignment"
    else:
        alignment_status = "🟡 Mixed Alignment"
    
    print(f"   Alignment: {alignment_status}")
    
    # Compare price with EMAs
    print(f"\n💹 Price vs EMAs:")
    print(f"   Price: ₹{current_price:,.2f}")
    print(f"   Above EMA 5:  {'✅' if current_price > ema_5 else '❌'}")
    print(f"   Above EMA 20: {'✅' if current_price > ema_20 else '❌'}")
    print(f"   Above EMA 50: {'✅' if current_price > ema_50 else '❌'}")
    
    # Calculate MACD
    ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_histogram = histogram.iloc[-1]
    
    print(f"\n📈 MACD Analysis:")
    print(f"   MACD Line: {current_macd:.2f}")
    print(f"   Signal Line: {current_signal:.2f}")
    print(f"   Histogram: {current_histogram:.2f}")
    
    if current_macd > current_signal:
        macd_status = "🟢 Bullish"
    else:
        macd_status = "🔴 Bearish"
    print(f"   Status: {macd_status}")
    
    # Calculate VWAP
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    volume_price = typical_price * data['Volume']
    cumulative_volume_price = volume_price.cumsum()
    cumulative_volume = data['Volume'].cumsum()
    vwap = cumulative_volume_price / cumulative_volume
    current_vwap = vwap.iloc[-1]
    
    print(f"\n💧 VWAP Analysis:")
    print(f"   VWAP: ₹{current_vwap:,.2f}")
    print(f"   Price vs VWAP: {'🟢 Above' if current_price > current_vwap else '🔴 Below'}")
    
    print("\n" + "=" * 50)
    print("✅ Technical analysis completed!")
    print(f"\nCompare with your chart:")
    print(f"Chart RSI: 72.27 | Our RSI: {current_rsi:.2f}")
    
    return {
        'price': current_price,
        'rsi': current_rsi,
        'ema_5': ema_5,
        'ema_20': ema_20,
        'ema_50': ema_50,
        'macd': current_macd,
        'vwap': current_vwap,
        'alignment': alignment_status
    }

if __name__ == "__main__":
    test_technical_indicators()
