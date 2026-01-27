"""
PROPER signal generator - only ONE strong signal at a time
PUT when price near RESISTANCE (wants to go DOWN)
CALL when price near SUPPORT (wants to go UP)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf

from indicators.technical import TechnicalIndicators
from config.settings import TradingConfig
from level_validator import LevelValidator

def get_proper_signal(symbol='^NSEI'):
    """Generate PROPER signal - only ONE based on price position"""
    
    config = TradingConfig()
    indicators = TechnicalIndicators()
    validator = LevelValidator('NIFTY' if 'NSEI' in symbol else 'SENSEX')
    
    # Fetch daily data
    data = yf.download(symbol, period='1y', interval='1d', progress=False)
    
    if len(data) < 50:
        print(f"Not enough data for {symbol}")
        return
    
    # Calculate indicators
    data['EMA5'] = indicators.calculate_ema(data['Close'], 5)
    data['EMA12'] = indicators.calculate_ema(data['Close'], 12)
    data['EMA20'] = indicators.calculate_ema(data['Close'], 20)
    data['RSI'] = indicators.calculate_rsi(data['Close'], 14)
    data['ATR'] = indicators.calculate_atr(data, 14)
    
    current_price = float(data['Close'].iloc[-1])
    atr = float(data['ATR'].iloc[-1])
    rsi = float(data['RSI'].iloc[-1])
    
    ema5 = float(data['EMA5'].iloc[-1])
    ema12 = float(data['EMA12'].iloc[-1])
    
    # Get historical levels
    support_zones = sorted(validator.support_zones, reverse=True)
    resistance_zones = sorted(validator.resistance_zones)
    
    # Find nearest support and resistance
    nearest_support = max([s for s in support_zones if s < current_price], default=support_zones[0] if support_zones else current_price - 500)
    nearest_resistance = min([r for r in resistance_zones if r > current_price], default=resistance_zones[0] if resistance_zones else current_price + 500)
    
    dist_to_support = current_price - nearest_support
    dist_to_resistance = nearest_resistance - current_price
    
    # Determine signal based on PRICE POSITION relative to support/resistance
    print("\n" + "="*90)
    print("PROPER SIGNAL GENERATION - ONE SIGNAL BASED ON PRICE POSITION")
    print("="*90)
    
    print(f"\nSymbol: NIFTY | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current Price: {current_price:.2f}")
    print(f"ATR: {atr:.0f}pts | RSI: {rsi:.0f}\n")
    
    print(f"Historical Levels:")
    print(f"  Nearest Support:    {nearest_support:.2f} ({dist_to_support:.0f}pts away)")
    print(f"  Nearest Resistance: {nearest_resistance:.2f} ({dist_to_resistance:.0f}pts away)\n")
    
    # Signal logic based on price position
    if dist_to_resistance < dist_to_support:
        # Price is NEAR RESISTANCE = Price wants to go DOWN = PUT signal
        signal_type = 'PUT'
        entry = current_price
        target_support = nearest_support
    else:
        # Price is NEAR SUPPORT = Price wants to go UP = CALL signal
        signal_type = 'CALL'
        entry = current_price
        target_support = nearest_resistance
    
    print(f"Signal Position: Price is {dist_to_support:.0f}pts from support, {dist_to_resistance:.0f}pts from resistance")
    
    if signal_type == 'PUT':
        print(f"→ SIGNAL: {signal_type} (Price closer to RESISTANCE - expects DOWNSIDE)\n")
        print("-"*90)
        print(f"{signal_type} SIGNAL (BEARISH) - BUY PUT OPTION")
        print("-"*90)
        
        sl = entry + (atr * 0.10)  # SL above entry (protection from upside)
        t1 = entry - (atr * 0.25)  # Target below entry (profit from downside)
        t2 = entry - (atr * 0.50)  # Larger profit from downside
        
        print(f"\n  Entry Price:      {entry:>12.2f}  (Current - Near resistance)")
        print(f"  Stop Loss:        {sl:>12.2f}  ({abs(sl-entry):.0f} points ABOVE entry)")
        print(f"  Target 1:         {t1:>12.2f}  ({abs(entry-t1):.0f} points profit - DOWNSIDE)")
        print(f"  Target 2:         {t2:>12.2f}  ({abs(entry-t2):.0f} points profit - DOWNSIDE)")
        
    else:  # CALL
        print(f"→ SIGNAL: {signal_type} (Price closer to SUPPORT - expects UPSIDE)\n")
        print("-"*90)
        print(f"{signal_type} SIGNAL (BULLISH) - BUY CALL OPTION")
        print("-"*90)
        
        sl = entry - (atr * 0.10)  # SL below entry (protection from downside)
        t1 = entry + (atr * 0.25)  # Target above entry (profit from upside)
        t2 = entry + (atr * 0.50)  # Larger profit from upside
        
        print(f"\n  Entry Price:      {entry:>12.2f}  (Current - Near support)")
        print(f"  Stop Loss:        {sl:>12.2f}  ({abs(entry-sl):.0f} points BELOW entry)")
        print(f"  Target 1:         {t1:>12.2f}  ({abs(t1-entry):.0f} points profit - UPSIDE)")
        print(f"  Target 2:         {t2:>12.2f}  ({abs(t2-entry):.0f} points profit - UPSIDE)")
    
    # Risk/Reward
    risk = abs(sl - entry)
    reward1 = abs(t1 - entry) if signal_type == 'PUT' else abs(t1 - entry)
    reward2 = abs(t2 - entry) if signal_type == 'PUT' else abs(t2 - entry)
    
    rr1 = reward1 / risk if risk > 0 else 0
    rr2 = reward2 / risk if risk > 0 else 0
    
    print(f"\n  Risk/Reward (T1):  1:{rr1:.2f}")
    print(f"  Risk/Reward (T2):  1:{rr2:.2f}")
    
    # Validation
    validation = validator.validate_signal(entry, sl, t1, t2, signal_type.lower())
    
    print(f"\n  Validation:")
    print(f"    ✓ Entry at historical level: {validation['entry']['valid']}", end="")
    if validation['entry']['level']:
        print(f" (Level: {validation['entry']['level']:.0f})")
    else:
        print()
    
    print(f"    ✓ Targets near historical zones: {validation['target1']['valid'] or validation['target2']['valid']}")
    
    if validation['overall_valid']:
        print(f"    ✓ SIGNAL IS EXECUTABLE - Backed by historical data")
    
    print("\n" + "="*90)
    print(f"ONLY THIS SIGNAL IS TRADEABLE: {signal_type}")
    print("DO NOT trade CALL if PUT is showing (they are mutually exclusive)")
    print("="*90 + "\n")


if __name__ == "__main__":
    get_proper_signal('^NSEI')
