"""
QUICK START: Test Dhan Integration
Run live data fetch and option chain parsing
"""

import sys
from pathlib import Path
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, format="<level>{level: <8}</level> | {message}", level="INFO")

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from integrations import DhanDataManager

def main():
    print("\n" + "="*80)
    print("DHAN LIVE DATA DEMO")
    print("="*80)
    
    try:
        # Initialize manager
        print("\n[1] Initializing Dhan Data Manager...")
        manager = DhanDataManager()
        
        # Fetch NIFTY candles
        print("\n[2] Fetching NIFTY 5-min candles (5 days)...")
        df_5m = manager.get_nifty_candles(interval=5, days=5)
        print(f"    OK: {len(df_5m)} candles")
        print("\n    Latest candles:")
        print(df_5m[['open', 'high', 'low', 'close', 'volume']].tail(3).to_string())
        
        # Fetch daily
        print("\n[3] Fetching NIFTY daily candles (365 days)...")
        df_daily = manager.get_nifty_daily(days=365)
        print(f"    OK: {len(df_daily)} daily candles")
        
        # Get nearest expiry
        print("\n[4] Fetching option expiry list...")
        expiry = manager.get_nearest_expiry()
        print(f"    OK: Nearest expiry = {expiry}")
        
        # Fetch option chain
        print(f"\n[5] Fetching NIFTY option chain ({expiry})...")
        chain = manager.get_nifty_option_chain(expiry)
        print(f"    OK: {len(chain)} strikes available")
        
        # Get spot price and find ATM
        current_spot = float(df_5m['close'].iloc[-1])
        print(f"\n[6] Current spot: {current_spot:.2f}")
        
        atm_call, atm_put = manager.get_atm_strikes(chain, current_spot=current_spot)
        
        if atm_call and atm_put:
            print(f"\n    ATM Call  Strike: {atm_call.strike:.0f}")
            print(f"      LTP: {atm_call.ltp:.2f} | Delta: {atm_call.delta:.3f} | IV: {atm_call.iv:.2f}")
            print(f"      Bid: {atm_call.bid_price:.2f} / Ask: {atm_call.ask_price:.2f}")
            
            print(f"\n    ATM Put   Strike: {atm_put.strike:.0f}")
            print(f"      LTP: {atm_put.ltp:.2f} | Delta: {atm_put.delta:.3f} | IV: {atm_put.iv:.2f}")
            print(f"      Bid: {atm_put.bid_price:.2f} / Ask: {atm_put.ask_price:.2f}")
        
        manager.close()
        
        print("\n" + "="*80)
        print("[SUCCESS] Dhan integration working!")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
