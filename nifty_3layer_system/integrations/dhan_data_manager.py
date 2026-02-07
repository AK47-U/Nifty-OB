"""
DHAN DATA MANAGER: High-level data abstraction
- Caches market data intelligently
- Returns ready-to-use DataFrames
- Handles instrument lookups and strikes
- Bridges Dhan API → orchestrator layers
- Multi-instrument support (NIFTY, SENSEX, BANKNIFTY, etc.)
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import pickle
from pathlib import Path

from .dhan_client import DhanAPIClient, NIFTY_INSTRUMENTS


@dataclass
class OptionStrike:
    """Option strike data with Greeks"""
    strike: float
    ltp: float
    delta: float
    gamma: float
    vega: float
    theta: float
    iv: float
    oi: int
    volume: int
    bid_price: float
    bid_qty: int
    ask_price: float
    ask_qty: int
    side: str  # 'CE' or 'PE'


class DhanDataManager:
    """
    High-level manager for Dhan market data
    - Fetches and caches candles
    - Fetches and caches option chains
    - Returns structured data for layers
    - Supports multiple instruments (NIFTY, SENSEX, BANKNIFTY)
    """
    
    def __init__(self, client: Optional[DhanAPIClient] = None, cache_dir: str = '.dhan_cache',
                 instrument_config: Optional[Dict] = None):
        """
        Initialize data manager
        
        Args:
            client: DhanAPIClient instance (creates if None)
            cache_dir: Directory for persistent cache
            instrument_config: Instrument configuration dict with security_id, exchange_segment, etc.
        """
        self.client = client or DhanAPIClient()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Instrument configuration
        self.instrument_config = instrument_config or {
            'security_id': '13',
            'exchange_segment': 'IDX_I',
            'instrument_type': 'OPTIDX',
            'name': 'NIFTY'
        }
        
        # In-memory cache
        self._candle_cache: Dict[str, pd.DataFrame] = {}
        self._option_chain_cache: Dict[str, Dict] = {}
        
        logger.info(f"✓ DhanDataManager initialized | Instrument: {self.instrument_config['name']} | Cache: {self.cache_dir}")

    @staticmethod
    def _normalize_iv(raw_iv: Optional[float]) -> float:
        """Normalize IV to decimal (0.01-3.0) to avoid absurd API values."""
        try:
            iv = float(raw_iv)
        except (TypeError, ValueError):
            return 0.0

        original = iv

        if iv <= 0:
            return 0.0
        if iv > 1000:  # e.g., 2051 -> treat as basis points
            iv /= 10000
        elif iv > 100:  # e.g., 205 -> treat as percentage
            iv /= 100
        elif iv > 3:  # e.g., 20 -> treat as percentage
            iv /= 100

        iv = max(0.01, min(iv, 3.0))  # clamp to 1%-300%

        if iv != original:
            logger.debug(f"Normalized IV from {original} to {iv}")

        return iv
    
    def get_nifty_candles(
        self,
        interval: int = 5,
        days: int = 5
    ) -> pd.DataFrame:
        """
        Fetch NIFTY 50 candles
        
        Args:
            interval: 1, 5, 15, 25, 60 (minutes)
            days: Lookback period
        
        Returns:
            DataFrame with OHLCV
        """
        instrument_name = self.instrument_config.get('name', 'NIFTY').lower()
        cache_key = f"{instrument_name}_{interval}m_{days}d"
        
        if cache_key in self._candle_cache:
            logger.debug(f"Using in-memory candle cache: {cache_key}")
            return self._candle_cache[cache_key]
        
        # Use instrument config parameters
        df = self.client.get_historical_candles(
            security_id=self.instrument_config['security_id'],
            exchange_segment=self.instrument_config['exchange_segment'],
            instrument=self.instrument_config['instrument_type'],
            interval=interval,
            days=days
        )
        
        self._candle_cache[cache_key] = df
        return df
    
    def get_daily_candles(self, days: int = 365) -> pd.DataFrame:
        """
        Fetch daily candles for configured instrument
        
        Args:
            days: Lookback period
        
        Returns:
            DataFrame with daily OHLCV
        """
        instrument_name = self.instrument_config.get('name', 'NIFTY').lower()
        cache_key = f"{instrument_name}_daily_{days}d"
        
        if cache_key in self._candle_cache:
            logger.debug(f"Using in-memory daily cache: {cache_key}")
            return self._candle_cache[cache_key]
        
        # Use instrument config
        df = self.client.get_daily_candles(
            security_id=self.instrument_config['security_id'],
            exchange_segment=self.instrument_config['exchange_segment'],
            instrument=self.instrument_config['instrument_type'],
            days=days
        )
        
        self._candle_cache[cache_key] = df
        return df
    
    def get_nifty_option_chain(self, expiry: str) -> Dict[str, Dict]:
        """
        Fetch NIFTY option chain, structured by strike
        
        Args:
            expiry: Date in YYYY-MM-DD format
        
        Returns:
            Dict[strike, Dict[side, OptionStrike]]
        """
        instrument_name = self.instrument_config.get('name', 'NIFTY').lower()
        cache_key = f"{instrument_name}_optionchain_{expiry}"
        
        if cache_key in self._option_chain_cache:
            logger.debug(f"Using in-memory option chain cache: {cache_key}")
            return self._option_chain_cache[cache_key]
        
        # Use instrument config for option chain
        raw_chain = self.client.get_option_chain(
            underlying_scrip=int(self.instrument_config['security_id']),
            underlying_seg=self.instrument_config['exchange_segment'],
            expiry=expiry
        )
        
        # Parse and structure option chain
        structured_chain = self._parse_option_chain(raw_chain)
        self._option_chain_cache[cache_key] = structured_chain
        
        return structured_chain
    
    def _parse_option_chain(self, raw_chain: Dict) -> Dict[str, Dict]:
        """
        Parse raw option chain response into structured format
        
        Returns:
            Dict[strike, Dict['CE'/'PE', OptionStrike]]
        """
        structured = {}
        
        try:
            oc_data = raw_chain.get('data', {}).get('oc', {})
            
            for strike_str, strike_data in oc_data.items():
                strike = float(strike_str)
                structured[strike] = {}
                
                # Parse CE
                if 'ce' in strike_data:
                    ce = strike_data['ce']
                    structured[strike]['CE'] = OptionStrike(
                        strike=strike,
                        ltp=ce.get('last_price', 0),
                        delta=ce.get('greeks', {}).get('delta', 0),
                        gamma=ce.get('greeks', {}).get('gamma', 0),
                        vega=ce.get('greeks', {}).get('vega', 0),
                        theta=ce.get('greeks', {}).get('theta', 0),
                        iv=self._normalize_iv(ce.get('implied_volatility', 0)),
                        oi=ce.get('oi', 0),
                        volume=ce.get('volume', 0),
                        bid_price=ce.get('top_bid_price', 0),
                        bid_qty=ce.get('top_bid_quantity', 0),
                        ask_price=ce.get('top_ask_price', 0),
                        ask_qty=ce.get('top_ask_quantity', 0),
                        side='CE'
                    )
                
                # Parse PE
                if 'pe' in strike_data:
                    pe = strike_data['pe']
                    structured[strike]['PE'] = OptionStrike(
                        strike=strike,
                        ltp=pe.get('last_price', 0),
                        delta=pe.get('greeks', {}).get('delta', 0),
                        gamma=pe.get('greeks', {}).get('gamma', 0),
                        vega=pe.get('greeks', {}).get('vega', 0),
                        theta=pe.get('greeks', {}).get('theta', 0),
                        iv=self._normalize_iv(pe.get('implied_volatility', 0)),
                        oi=pe.get('oi', 0),
                        volume=pe.get('volume', 0),
                        bid_price=pe.get('top_bid_price', 0),
                        bid_qty=pe.get('top_bid_quantity', 0),
                        ask_price=pe.get('top_ask_price', 0),
                        ask_qty=pe.get('top_ask_quantity', 0),
                        side='PE'
                    )
            
            logger.info(f"✓ Parsed option chain: {len(structured)} strikes")
            return structured
        
        except Exception as e:
            logger.error(f"Failed to parse option chain: {e}")
            raise
    
    def get_nearest_expiry(self) -> str:
        """
        Get nearest option expiry (typically weekly Thursday or monthly)
        
        Returns:
            Expiry date in YYYY-MM-DD format
        """
        # Use instrument config for expiry list
        expiries = self.client.get_expiry_list(
            underlying_scrip=int(self.instrument_config['security_id']),
            underlying_seg=self.instrument_config['exchange_segment']
        )
        
        if not expiries:
            raise ValueError("No expiries available")
        
        today = datetime.now().date()
        future_expiries = [e for e in expiries if datetime.strptime(e, '%Y-%m-%d').date() > today]
        
        if not future_expiries:
            raise ValueError("No future expiries available")
        
        nearest = future_expiries[0]
        logger.info(f"Nearest expiry: {nearest}")
        return nearest
    
    def get_current_weekly_expiry(self) -> str:
        """
        Get CURRENT WEEK's Thursday expiry (weekly options)
        
        Logic:
        - If today is Mon-Wed: Get THIS Thursday
        - If today is Thu-Sun: Get NEXT Thursday (this week's expired or expires today)
        
        Returns:
            Expiry date in YYYY-MM-DD format
        """
        today = datetime.now().date()
        weekday = today.weekday()  # 0=Mon, 3=Thu, 6=Sun
        
        # Calculate days until Thursday
        if weekday < 3:  # Mon(0), Tue(1), Wed(2) → Get THIS Thursday
            days_to_thursday = 3 - weekday
        elif weekday == 3:  # Thursday → Check if still valid, else get next
            days_to_thursday = 0  # Try this Thursday first
        else:  # Fri(4), Sat(5), Sun(6) → Get NEXT Thursday
            days_to_thursday = 3 - weekday + 7  # e.g., if Fri: 3-4+7=6 days
        
        current_weekly = today + timedelta(days=days_to_thursday)
        
        # Get available expiries and find matching weekly Thursday
        expiries = self.client.get_expiry_list(
            underlying_scrip=int(self.instrument_config['security_id']),
            underlying_seg=self.instrument_config['exchange_segment']
        )
        
        if not expiries:
            raise ValueError("No expiries available")
        
        # Convert to dates for comparison
        expiry_dates = [datetime.strptime(e, '%Y-%m-%d').date() for e in expiries]
        
        # Check if current weekly Thursday is available
        if current_weekly in expiry_dates:
            result = current_weekly.strftime('%Y-%m-%d')
            logger.info(f"Current weekly expiry: {result} ({current_weekly.strftime('%A')})")
            return result
        
        # If not available, get next available expiry after today
        future_expiries = [e for e in expiry_dates if e > today]
        if future_expiries:
            nearest = min(future_expiries)
            result = nearest.strftime('%Y-%m-%d')
            logger.info(f"Current weekly {current_weekly} not available. Using nearest: {result}")
            return result
        
        raise ValueError("No future expiries available for current week")
    
    def find_strike_by_delta(
        self,
        option_chain: Dict[str, Dict],
        target_delta: float,
        side: str = 'CE'
    ) -> Optional[OptionStrike]:
        """
        Find strike closest to target delta
        
        Args:
            option_chain: Option chain from get_nifty_option_chain
            target_delta: Target delta (e.g., 0.5 for ATM)
            side: 'CE' or 'PE'
        
        Returns:
            OptionStrike closest to target delta, or None
        """
        closest_strike = None
        closest_delta_diff = float('inf')
        
        for strike, sides in option_chain.items():
            if side not in sides:
                continue
            
            option = sides[side]
            delta_diff = abs(option.delta - target_delta)
            
            if delta_diff < closest_delta_diff:
                closest_delta_diff = delta_diff
                closest_strike = option
        
        if closest_strike:
            logger.info(f"Found {side} strike {closest_strike.strike} with delta {closest_strike.delta:.3f}")
        
        return closest_strike
    
    def get_atm_strikes(
        self,
        option_chain: Dict[str, Dict],
        current_spot: float,
        tolerance: float = 100
    ) -> Tuple[Optional[OptionStrike], Optional[OptionStrike]]:
        """
        Get ATM Call and Put
        
        Args:
            option_chain: Option chain from get_nifty_option_chain
            current_spot: Current spot price of underlying
            tolerance: Price range tolerance
        
        Returns:
            Tuple of (ATM Call, ATM Put) OptionStrikes
        """
        atm_call = None
        atm_put = None
        
        min_diff = float('inf')
        
        for strike, sides in option_chain.items():
            diff = abs(strike - current_spot)
            
            if diff < min_diff:
                min_diff = diff
                if 'CE' in sides:
                    atm_call = sides['CE']
                if 'PE' in sides:
                    atm_put = sides['PE']
            
            if diff > tolerance:
                break
        
        logger.info(f"ATM strikes: CE {atm_call.strike if atm_call else None}, "
                   f"PE {atm_put.strike if atm_put else None}")
        
        return atm_call, atm_put
    
    def clear_cache(self):
        """Clear all caches"""
        self._candle_cache.clear()
        self._option_chain_cache.clear()
        self.client.clear_cache()
        logger.info("✓ All caches cleared")
    
    def close(self):
        """Close connections and cleanup"""
        self.client.close()
        logger.info("✓ DhanDataManager closed")
