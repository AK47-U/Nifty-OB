"""
DHAN DATA MANAGER: High-level data abstraction
- Caches market data intelligently
- Returns ready-to-use DataFrames
- Handles instrument lookups and strikes
- Bridges Dhan API → orchestrator layers
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
    """
    
    def __init__(self, client: Optional[DhanAPIClient] = None, cache_dir: str = '.dhan_cache'):
        """
        Initialize data manager
        
        Args:
            client: DhanAPIClient instance (creates if None)
            cache_dir: Directory for persistent cache
        """
        self.client = client or DhanAPIClient()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory cache
        self._candle_cache: Dict[str, pd.DataFrame] = {}
        self._option_chain_cache: Dict[str, Dict] = {}
        
        logger.info(f"✓ DhanDataManager initialized | Cache: {self.cache_dir}")

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
        cache_key = f"nifty_{interval}m_{days}d"
        
        if cache_key in self._candle_cache:
            logger.debug(f"Using in-memory candle cache: {cache_key}")
            return self._candle_cache[cache_key]
        
        # NIFTY is an INDEX with segment IDX_I (not NSE_EQ which is EQUITY)
        nifty = {'security_id': '13', 'exchange': 'IDX_I', 'instrument': 'OPTIDX'}
        
        df = self.client.get_historical_candles(
            security_id=nifty['security_id'],
            exchange_segment=nifty['exchange'],
            instrument=nifty['instrument'],
            interval=interval,
            days=days
        )
        
        self._candle_cache[cache_key] = df
        return df
    
    def get_nifty_daily(self, days: int = 365) -> pd.DataFrame:
        """
        Fetch NIFTY daily candles
        
        Args:
            days: Lookback period
        
        Returns:
            DataFrame with daily OHLCV
        """
        cache_key = f"nifty_daily_{days}d"
        
        if cache_key in self._candle_cache:
            logger.debug(f"Using in-memory daily cache: {cache_key}")
            return self._candle_cache[cache_key]
        
        # NIFTY is an INDEX
        nifty = {'security_id': '13', 'exchange': 'IDX_I', 'instrument': 'OPTIDX'}
        
        df = self.client.get_daily_candles(
            security_id=nifty['security_id'],
            exchange_segment=nifty['exchange'],
            instrument=nifty['instrument'],
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
        cache_key = f"nifty_optionchain_{expiry}"
        
        if cache_key in self._option_chain_cache:
            logger.debug(f"Using in-memory option chain cache: {cache_key}")
            return self._option_chain_cache[cache_key]
        
        # For option chain API, use security ID 13 (not 99926000)
        raw_chain = self.client.get_option_chain(
            underlying_scrip=13,  # NIFTY
            underlying_seg='IDX_I',
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
        # For option chain, use security ID 13 (NIFTY) not 99926000
        expiries = self.client.get_expiry_list(
            underlying_scrip=13,  # NIFTY
            underlying_seg='IDX_I'
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
