#!/usr/bin/env python
"""Test WebSocket connection with correct URL format"""
import asyncio
from integrations.dhan_websocket import DhanWebSocket, ExchangeSegment, InstrumentType
from config.instrument_config import InstrumentManager
from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

print("=" * 80)
print("DHAN WEBSOCKET CONNECTION TEST (WITH CORRECT URL FORMAT)")
print("=" * 80)
print(f"Access Token: {ACCESS_TOKEN[:20] if ACCESS_TOKEN else 'NOT SET'}...")
print(f"Client ID: {CLIENT_ID if CLIENT_ID else 'NOT SET'}")

# Get NIFTY instrument
nifty = InstrumentManager.get_instrument("NIFTY")
print(f"\nNIFTY Instrument:")
print(f"  Security ID: {nifty.security_id}")
print(f"  Exchange Segment: {nifty.exchange_segment}")
print(f"  Instrument Type: {nifty.instrument_type}")

# Try to connect
ws = DhanWebSocket(access_token=ACCESS_TOKEN, client_id=CLIENT_ID)

async def test_connection():
    print("\n" + "=" * 80)
    print("Attempting WebSocket connection...")
    print("=" * 80)
    
    try:
        await ws.connect()
        print("✓ Connection established!")
        
        # Try to subscribe to NIFTY ticker
        print("\nSubscribing to NIFTY ticker...")
        await ws.subscribe_ticker(
            security_id=nifty.security_id,
            exchange_segment=ExchangeSegment.IDX_I,
            instrument_type=InstrumentType.INDEX,
        )
        print("✓ Subscription sent!")
        
        # Wait for some data
        print("\nWaiting for market data (10 seconds)...")
        await asyncio.sleep(10)
        
        await ws.disconnect()
        print("✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

print()
asyncio.run(test_connection())
