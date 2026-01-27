#!/usr/bin/env python3
"""Test Dhan API connection"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from dhan_api_client import create_dhan_client

print("[TEST] Testing Dhan API connection...")

ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

print(f"[TEST] ACCESS_TOKEN exists: {bool(ACCESS_TOKEN)}")
print(f"[TEST] CLIENT_ID: {CLIENT_ID}")

if not (ACCESS_TOKEN and CLIENT_ID):
    print("[ERROR] Credentials missing in .env")
    sys.exit(1)

try:
    print("[TEST] Creating Dhan client...")
    client = create_dhan_client(ACCESS_TOKEN, CLIENT_ID)
    
    print("[TEST] Attempting to fetch quote...")
    quote = client.get_quote("99926000", "99926000")
    
    if quote:
        print(f"[SUCCESS] Quote received!")
        print(f"  LTP: {quote.ltp}")
        print(f"  Bid: {quote.bid_price} x {quote.bid_qty}")
        print(f"  Ask: {quote.ask_price} x {quote.ask_qty}")
    else:
        print("[ERROR] Quote returned None")
        
except Exception as e:
    print(f"[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
