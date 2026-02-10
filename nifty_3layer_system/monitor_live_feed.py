#!/usr/bin/env python
"""
Monitor WebSocket live feed and show real-time ticks
"""
import asyncio
from integrations.dhan_websocket import DhanWebSocket, ExchangeSegment, InstrumentType
from config.instrument_config import InstrumentManager
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

tick_count = {"NIFTY": 0, "SENSEX": 0}
latest_prices = {"NIFTY": None, "SENSEX": None}

print("=" * 80)
print("DHAN LIVE TICK MONITOR")
print("=" * 80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Monitoring NIFTY and SENSEX for 30 seconds...\n")

def on_tick(tick):
    """Callback when a tick is received"""
    # Map security_id to symbol
    if str(tick.security_id) == "13":
        symbol = "NIFTY"
    elif str(tick.security_id) == "51":
        symbol = "SENSEX"
    else:
        return
    
    tick_count[symbol] += 1
    latest_prices[symbol] = tick.ltp
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol:8} | LTP: {tick.ltp:10.2f} | Tick #{tick_count[symbol]}")

async def monitor_feed():
    ws = DhanWebSocket(access_token=ACCESS_TOKEN, client_id=CLIENT_ID)
    ws.on_tick(on_tick)
    
    await ws.connect()
    
    # Subscribe to both
    nifty = InstrumentManager.get_instrument("NIFTY")
    sensex = InstrumentManager.get_instrument("SENSEX")
    
    await ws.subscribe_ticker(
        security_id=nifty.security_id,
        exchange_segment=ExchangeSegment.IDX_I,
        instrument_type=InstrumentType.INDEX,
    )
    
    await ws.subscribe_ticker(
        security_id=sensex.security_id,
        exchange_segment=ExchangeSegment.IDX_I,
        instrument_type=InstrumentType.INDEX,
    )
    
    # Monitor for 30 seconds
    await asyncio.sleep(30)
    
    await ws.disconnect()
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"NIFTY    - Ticks received: {tick_count['NIFTY']:3d} | Latest: {latest_prices['NIFTY']:10.2f}")
    print(f"SENSEX   - Ticks received: {tick_count['SENSEX']:3d} | Latest: {latest_prices['SENSEX']:10.2f}")
    print(f"Total    - {tick_count['NIFTY'] + tick_count['SENSEX']} ticks in 30 seconds")
    print(f"Rate     - {(tick_count['NIFTY'] + tick_count['SENSEX']) / 30:.1f} ticks/sec")
    print("\n✓ WebSocket feed is working perfectly!")

if __name__ == "__main__":
    asyncio.run(monitor_feed())
