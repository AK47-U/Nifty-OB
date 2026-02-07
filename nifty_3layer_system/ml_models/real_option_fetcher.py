"""
Real-Time Option Chain Fetcher - Get actual option prices and premiums
Fetches real option data from Dhan API for NIFTY options
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger
from integrations.dhan_client import DhanAPIClient
import requests
import json


class RealTimeOptionFetcher:
    """Fetch real option prices from Dhan API"""
    
    def __init__(self):
        self.client = DhanAPIClient()
        self.nifty_security_id = "13"
        self.nifty_lot_size = 65  # CORRECT lot size for NIFTY
        
        # NIFTY option security ID mapping (approximate - need to fetch from API)
        # Format: {strike: security_id} for current week expiry
        self.option_security_ids = {}
    
    def get_atm_strike(self, spot_price: float, strike_gap: int = 50) -> int:
        """Get ATM strike from spot price"""
        return round(spot_price / strike_gap) * strike_gap

    def _parse_expiry(self, expiry_str: str) -> Optional[datetime]:
        """Parse expiry string into datetime (best-effort)."""
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d%b%y", "%d%b%Y"):
            try:
                return datetime.strptime(expiry_str, fmt)
            except ValueError:
                continue
        return None

    def _get_next_expiry(self) -> Optional[str]:
        """Get next available expiry from Dhan option chain expiry list."""
        try:
            expiries = self.client.get_expiry_list(
                underlying_scrip=int(self.nifty_security_id),
                underlying_seg="IDX_I"
            )
            if not expiries:
                return None

            today = datetime.now().date()
            parsed = []
            for exp in expiries:
                dt = self._parse_expiry(exp)
                if dt is None:
                    continue
                parsed.append((dt.date(), exp))

            if not parsed:
                return None

            future = [p for p in parsed if p[0] >= today]
            if future:
                return sorted(future, key=lambda x: x[0])[0][1]

            return sorted(parsed, key=lambda x: x[0])[0][1]
        except Exception as e:
            logger.warning(f"Failed to fetch expiry list: {str(e)}")
            return None
    
    def fetch_option_quote(self, strike: int, option_type: str = 'PE') -> Optional[Dict]:
        """
        Fetch REAL option quote from Dhan API - Current Weekly Expiry
        
        Args:
            strike: Strike price (25800)
            option_type: 'CE' or 'PE'
        
        Returns:
            Dict with premium, volume, OI, bid, ask
        """
        try:
            expiry_str = self._get_next_expiry()
            if not expiry_str:
                logger.warning("No expiry available from Dhan option chain")
                return None

            logger.info(f"📅 Weekly Expiry: {expiry_str} | Strike: {strike}{option_type}")

            raw_chain = self.client.get_option_chain(
                underlying_scrip=int(self.nifty_security_id),
                underlying_seg="IDX_I",
                expiry=expiry_str
            )

            oc_data = raw_chain.get('data', {}).get('oc', {})
            if not oc_data:
                logger.warning("Empty option chain received from Dhan")
                return None

            side_key = 'ce' if option_type == 'CE' else 'pe'

            # Prefer exact strike, but ensure side data exists
            strike_key = str(int(strike))
            strike_data = oc_data.get(strike_key, {})
            if not strike_data or side_key not in strike_data:
                # pick nearest strike that has requested side data
                available = []
                for k, v in oc_data.items():
                    if side_key in v:
                        try:
                            available.append((float(k), k))
                        except ValueError:
                            continue
                if not available:
                    logger.warning(f"No {option_type} data available in option chain")
                    return None
                nearest = min(available, key=lambda x: abs(x[0] - strike))
                strike_key = nearest[1]
                strike_data = oc_data.get(strike_key, {})

            side = strike_data.get(side_key, {})
            if not side:
                logger.warning(f"No {option_type} data for strike {strike_key}")
                return None

            premium = side.get('last_price', 0)
            volume = int(side.get('volume', 0))
            oi = int(side.get('oi', 0))
            bid = side.get('top_bid_price', 0)
            ask = side.get('top_ask_price', 0)

            logger.info(f"✅ Got Real Premium: ₹{premium:.2f} from Dhan API")

            return {
                'strike': int(float(strike_key)),
                'option_type': option_type,
                'expiry': expiry_str,
                'premium': round(float(premium), 2),
                'bid': round(float(bid), 2),
                'ask': round(float(ask), 2),
                'volume': volume,
                'oi': oi,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        except Exception as e:
            logger.error(f"Error fetching option quote: {str(e)}")
            return None
    
    def fetch_option_chain_real(self, spot_price: float, direction: str) -> Dict:
        """
        Fetch real option chain for current weekly expiry (direction: BUY/SELL)
        Returns best liquid strike recommendation with ACTUAL premiums from Dhan API
        """
        atm = self.get_atm_strike(spot_price)
        
        logger.info(f"\n📊 Fetching Real Option Chain (Weekly Expiry)")
        logger.info(f"Spot Price: {spot_price:.2f} | ATM Strike: {atm}")
        
        # For SELL signal: Get ATM PE
        if direction == 'SELL':
            option_type = 'PE'
            strike = atm
        else:  # BUY signal: Get ATM CE
            option_type = 'CE'
            strike = atm
        
        # Fetch REAL quote from Dhan API
        logger.info(f"🔄 Fetching {strike}{option_type} from Dhan API...")
        quote = self.fetch_option_quote(strike, option_type)
        
        if not quote:
            logger.error(f"❌ Failed to fetch {strike}{option_type} from Dhan API")
            logger.warning("No real option data available - trading not recommended")
            return {}
        
        logger.info(f"\n✅ Real Option Data (From Dhan API):")
        logger.info(f"Strike: {strike} {option_type} | Expiry: {quote.get('expiry', 'N/A')}")
        logger.info(f"Premium (Entry): ₹{quote['premium']}")
        logger.info(f"Bid-Ask: ₹{quote['bid']} - ₹{quote['ask']}")
        logger.info(f"Volume: {quote['volume']:,}")
        logger.info(f"OI: {quote['oi']:,}")
        
        return quote
    
    def calculate_option_levels(self, quote: Dict, direction: str) -> Dict:
        """
        Calculate entry, target, SL in PREMIUM POINTS (rupees), not percentage
        
        Args:
            quote: Real option quote with premium
            direction: 'BUY' or 'SELL'
        
        Returns:
            Dict with entry, target, SL in rupees
        """
        entry_premium = quote['premium']
        
        # Fixed premium-point targets (not percentage!)
        # For scalping, typical targets are +5, +10, +20 rupees
        target_premium = entry_premium + 20  # +20 rupees profit
        sl_premium = entry_premium - 15      # -15 rupees loss
        
        # Ensure SL doesn't go negative
        sl_premium = max(sl_premium, 0.5)
        
        # Calculate rupees
        lot_size = self.nifty_lot_size  # 65
        
        profit_rupees = (target_premium - entry_premium) * lot_size
        loss_rupees = (entry_premium - sl_premium) * lot_size
        
        return {
            'strike': quote['strike'],
            'option_type': quote['option_type'],
            'direction': direction,
            'entry_premium': round(entry_premium, 2),
            'target_premium': round(target_premium, 2),
            'sl_premium': round(sl_premium, 2),
            'profit_points': round(target_premium - entry_premium, 2),
            'loss_points': round(entry_premium - sl_premium, 2),
            'lot_size': lot_size,
            'profit_rupees': round(profit_rupees, 2),
            'loss_rupees': round(loss_rupees, 2),
            'risk_reward': round(profit_rupees / loss_rupees, 2) if loss_rupees > 0 else 0,
            'volume': quote['volume'],
            'oi': quote['oi'],
            'bid_ask_spread': quote['ask'] - quote['bid']
        }
    
    def format_option_setup(self, setup: Dict) -> str:
        """Format option setup for display"""
        
        output = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    REAL-TIME OPTION TRADING SETUP                         ║
╚═══════════════════════════════════════════════════════════════════════════╝

🎯 STRIKE & DIRECTION:
   Strike:                 {setup['strike']} {setup['option_type']}
   Direction:              {setup['direction']}
   Liquidity:              Volume {setup['volume']:,} | OI {setup['oi']:,}
   Bid-Ask Spread:         ₹{setup['bid_ask_spread']:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 PREMIUM LEVELS (in Rupees):

   📥 ENTRY PREMIUM:       ₹{setup['entry_premium']:.2f}
   ✅ TARGET PREMIUM:      ₹{setup['target_premium']:.2f} (Profit: +₹{setup['profit_points']:.2f} per contract)
   🛑 STOP LOSS PREMIUM:   ₹{setup['sl_premium']:.2f} (Loss: -₹{setup['loss_points']:.2f} per contract)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💼 P&L CALCULATION (Lot = {setup['lot_size']} contracts):

   Total Capital Required: ₹{setup['entry_premium'] * setup['lot_size']:,.2f}
   Profit Target:          +₹{setup['profit_rupees']:,.2f}  ({setup['profit_points']:.2f} × {setup['lot_size']})
   Stop Loss:              -₹{setup['loss_rupees']:,.2f}  ({setup['loss_points']:.2f} × {setup['lot_size']})
   Risk:Reward Ratio:      1:{setup['risk_reward']:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 EXECUTION STRATEGY:
   1️⃣  BUY {setup['lot_size']} {setup['strike']}{setup['option_type']} @ ₹{setup['entry_premium']:.2f}
   2️⃣  SET TARGET @ ₹{setup['target_premium']:.2f} (Auto-exit for +₹{setup['profit_rupees']:,.2f})
   3️⃣  SET SL @ ₹{setup['sl_premium']:.2f} (Auto-exit for -₹{setup['loss_rupees']:,.2f})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return output


def main():
    """Test real option fetcher"""
    fetcher = RealTimeOptionFetcher()
    
    # Test with actual spot price
    spot = 25814.10
    direction = "SELL"
    
    logger.info(f"Testing Real Option Chain Fetcher")
    logger.info(f"Spot: {spot} | Direction: {direction}")
    
    # Fetch real option quote
    quote = fetcher.fetch_option_chain_real(spot, direction)
    
    if quote:
        # Calculate levels
        setup = fetcher.calculate_option_levels(quote, direction)
        print(fetcher.format_option_setup(setup))
    else:
        logger.error("Failed to fetch option data")


if __name__ == "__main__":
    main()
