"""
DHAN API CLIENT: Enterprise-Grade Market Data Integration
- Handles authentication, rate limiting, retries, and error handling
- Production-ready HTTP pooling and connection management
- Comprehensive logging and validation
"""

import os
import time
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from functools import wraps
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables
load_dotenv()


@dataclass
class DhanConfig:
    """Configuration dataclass for Dhan API"""
    client_id: str
    api_key: str
    api_secret: str
    access_token: str
    base_url: str = "https://api.dhan.co/v2"
    ws_url: str = "wss://api-feed.dhan.co?version=2"
    token_expiry: Optional[datetime] = None
    
    @staticmethod
    def from_env() -> 'DhanConfig':
        """Load config from environment variables"""
        required_vars = ['DHAN_CLIENT_ID', 'DHAN_API_KEY', 'DHAN_API_SECRET', 'DHAN_ACCESS_TOKEN']
        missing = [v for v in required_vars if not os.getenv(v)]
        
        if missing:
            raise ValueError(f"Missing environment variables: {missing}. Check .env file.")
        
        # Parse token expiry if available
        token_expiry = None
        if os.getenv('DHAN_TOKEN_EXPIRY'):
            try:
                token_expiry = datetime.fromisoformat(os.getenv('DHAN_TOKEN_EXPIRY'))
            except:
                pass
        
        return DhanConfig(
            client_id=os.getenv('DHAN_CLIENT_ID'),
            api_key=os.getenv('DHAN_API_KEY'),
            api_secret=os.getenv('DHAN_API_SECRET'),
            access_token=os.getenv('DHAN_ACCESS_TOKEN'),
            base_url=os.getenv('DHAN_BASE_URL', 'https://api.dhan.co/v2'),
            ws_url=os.getenv('DHAN_WS_URL', 'wss://api-feed.dhan.co?version=2'),
            token_expiry=token_expiry
        )
    
    def update_env_file(self, new_token: str, expiry: datetime):
        """Update .env file with new token and expiry"""
        env_path = Path.cwd() / '.env'
        if not env_path.exists():
            logger.warning(f".env file not found at {env_path}")
            return
        
        try:
            # Read current .env content
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update token and expiry
            updated = False
            expiry_updated = False
            new_lines = []
            
            for line in lines:
                if line.startswith('DHAN_ACCESS_TOKEN='):
                    new_lines.append(f'DHAN_ACCESS_TOKEN={new_token}\n')
                    updated = True
                elif line.startswith('DHAN_TOKEN_EXPIRY='):
                    new_lines.append(f'DHAN_TOKEN_EXPIRY={expiry.isoformat()}\n')
                    expiry_updated = True
                else:
                    new_lines.append(line)
            
            # Add if not exists
            if not updated:
                new_lines.append(f'DHAN_ACCESS_TOKEN={new_token}\n')
            if not expiry_updated:
                new_lines.append(f'DHAN_TOKEN_EXPIRY={expiry.isoformat()}\n')
            
            # Write back
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            # Update current config
            self.access_token = new_token
            self.token_expiry = expiry
            os.environ['DHAN_ACCESS_TOKEN'] = new_token
            os.environ['DHAN_TOKEN_EXPIRY'] = expiry.isoformat()
            
            logger.info(f"✅ Token updated in .env file. New expiry: {expiry}")
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")


class RateLimiter:
    """Token bucket rate limiter for API calls"""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    def wait(self):
        """Block until rate limit allows next call"""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limit: sleeping {sleep_time:.3f}s")
            time.sleep(sleep_time)
        self.last_call = time.time()


def rate_limited(limiter: RateLimiter):
    """Decorator for rate limiting API calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DhanAPIClient:
    """
    Enterprise-grade Dhan API client with:
    - Connection pooling & session management
    - Rate limiting (opt-in per endpoint)
    - Retry logic with exponential backoff
    - Comprehensive error handling
    - Request/response validation
    - Caching support (optional)
    """
    
    def __init__(self, config: Optional[DhanConfig] = None):
        """Initialize Dhan API client"""
        self.config = config or DhanConfig.from_env()
        self._session = self._create_session()
        
        # Rate limiters (3 sec for option chain, 1 sec default)
        self.option_chain_limiter = RateLimiter(calls_per_second=1/3)
        self.default_limiter = RateLimiter(calls_per_second=2)
        
        # Cache
        self._cache = {}
        self._cache_ttl = {}
        
        logger.info(f"✓ DhanAPIClient initialized | Client: {self.config.client_id}")
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with connection pooling and retry strategy"""
        session = requests.Session()
        
        # Retry strategy: exponential backoff for transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _headers(self) -> Dict[str, str]:
        """Build request headers"""
        return {
            'Content-Type': 'application/json',
            'access-token': self.config.access_token,
            'client-id': self.config.client_id
        }
    
    def _validate_response(self, response: requests.Response, retry_on_401: bool = True) -> Dict:
        """Validate and parse API response"""
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Handle 401 Unauthorized
            if response.status_code == 401:
                logger.error("⚠️ 401 Unauthorized - Access token expired!")
                logger.error("📋 To fix: Update DHAN_ACCESS_TOKEN in .env file")
                raise ValueError("Token expired - please update DHAN_ACCESS_TOKEN in .env and restart")
            
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {response.text}")
            raise ValueError(f"Invalid JSON response") from e

    def _get_cache(self, key: str) -> Optional[Dict]:
        """Get cached response if not expired"""
        if key in self._cache:
            if time.time() - self._cache_ttl[key] < 300:  # 5 min TTL
                logger.debug(f"Cache hit: {key}")
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_ttl[key]
        return None
    
    def _set_cache(self, key: str, value: Dict):
        """Set cache with TTL"""
        self._cache[key] = value
        self._cache_ttl[key] = time.time()
        logger.debug(f"Cache set: {key}")
    
    def get_historical_candles(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: int = 5,
        days: int = 5
    ) -> pd.DataFrame:
        """
        Fetch intraday candles (1m, 5m, 15m, 25m, 60m)
        
        Args:
            security_id: Exchange standard ID
            exchange_segment: e.g., 'NSE_EQ', 'NSE_FNO'
            instrument: e.g., 'EQUITY', 'OPTIDX'
            interval: 1, 5, 15, 25, 60 (minutes)
            days: Historical lookback (max 90)
        
        Returns:
            pd.DataFrame with OHLCV + timestamp
        """
        if interval not in [1, 5, 15, 25, 60]:
            raise ValueError(f"Invalid interval: {interval}. Must be one of [1, 5, 15, 25, 60]")
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "interval": interval,
            "oi": True,
            "fromDate": from_date.strftime("%Y-%m-%d %H:%M:%S"),
            "toDate": to_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        cache_key = f"candles_{security_id}_{interval}_{days}"
        cached = self._get_cache(cache_key)
        if cached:
            return pd.DataFrame(cached)
        
        logger.info(f"Fetching {interval}m candles | {security_id} | {days}d")
        
        # Auto-retry on token refresh
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self._session.post(
                    f"{self.config.base_url}/charts/intraday",
                    headers=self._headers(),
                    json=payload,
                    timeout=10
                )
                data = self._validate_response(response)
                
                # Convert to DataFrame
                df = pd.DataFrame({
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume'],
                    'timestamp': pd.to_datetime(data['timestamp'], unit='s'),
                    'oi': data.get('open_interest', [0] * len(data['timestamp']))
                })
            
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)
                
                self._set_cache(cache_key, df.to_dict(orient='list'))
                logger.info(f"✓ Fetched {len(df)} candles")
                
                return df
            
            except TokenRefreshedException:
                if attempt < max_retries - 1:
                    logger.info(f"Retrying request after token refresh (attempt {attempt + 2}/{max_retries})...")
                    continue
                else:
                    raise
            except Exception as e:
                logger.error(f"Failed to fetch candles: {e}")
                raise
    
    def get_daily_candles(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        days: int = 365
    ) -> pd.DataFrame:
        """
        Fetch daily candles (back to inception)
        
        Args:
            security_id: Exchange standard ID
            exchange_segment: e.g., 'NSE_EQ'
            instrument: e.g., 'EQUITY'
            days: Historical lookback
        
        Returns:
            pd.DataFrame with daily OHLCV
        """
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": 0,
            "oi": False,
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d")
        }
        
        cache_key = f"daily_candles_{security_id}_{days}"
        cached = self._get_cache(cache_key)
        if cached:
            return pd.DataFrame(cached)
        
        logger.info(f"Fetching daily candles | {security_id} | {days}d")
        
        try:
            response = self._session.post(
                f"{self.config.base_url}/charts/historical",
                headers=self._headers(),
                json=payload,
                timeout=10
            )
            data = self._validate_response(response)
            
            # Convert to DataFrame
            df = pd.DataFrame({
                'open': data['open'],
                'high': data['high'],
                'low': data['low'],
                'close': data['close'],
                'volume': data['volume'],
                'timestamp': pd.to_datetime(data['timestamp'], unit='s')
            })
            
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            self._set_cache(cache_key, df.to_dict(orient='list'))
            logger.info(f"✓ Fetched {len(df)} daily candles")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch daily candles: {e}")
            raise
    
    def get_option_chain(
        self,
        underlying_scrip: int,
        underlying_seg: str,
        expiry: str
    ) -> Dict:
        """
        Fetch option chain with Greeks, IV, OI, bid/ask
        
        Args:
            underlying_scrip: Security ID of underlying
            underlying_seg: e.g., 'IDX_I' for NIFTY
            expiry: Date in YYYY-MM-DD format
        
        Returns:
            Dict with strike-wise data including Greeks
        """
        payload = {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_seg,
            "Expiry": expiry
        }
        
        cache_key = f"optionchain_{underlying_scrip}_{expiry}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        logger.info(f"Fetching option chain | {underlying_scrip} | {expiry}")

        # Manual retry/backoff to survive transient 502 bursts from Dhan
        last_err = None
        for attempt in range(1, 4):
            try:
                self.option_chain_limiter.wait()  # Rate limit: 1 req per 3 sec

                response = self._session.post(
                    f"{self.config.base_url}/optionchain",
                    headers=self._headers(),
                    json=payload,
                    timeout=10
                )
                data = self._validate_response(response)

                self._set_cache(cache_key, data)
                logger.info(f"✓ Fetched option chain: {len(data.get('data', {}).get('oc', {}))} strikes")
                return data
            except Exception as e:
                last_err = e
                sleep_for = attempt  # 1s, 2s, 3s
                logger.warning(f"Option chain attempt {attempt} failed ({e}); retrying in {sleep_for}s...")
                time.sleep(sleep_for)

        logger.error(f"Failed to fetch option chain after retries: {last_err}")
        raise last_err
    
    def get_expiry_list(
        self,
        underlying_scrip: int,
        underlying_seg: str
    ) -> List[str]:
        """
        Fetch list of available option expiries
        
        Args:
            underlying_scrip: Security ID
            underlying_seg: e.g., 'IDX_I'
        
        Returns:
            List of expiry dates in YYYY-MM-DD format
        """
        payload = {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_seg
        }
        
        cache_key = f"expirylist_{underlying_scrip}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        logger.info(f"Fetching expiry list | {underlying_scrip}")
        
        try:
            response = self._session.post(
                f"{self.config.base_url}/optionchain/expirylist",
                headers=self._headers(),
                json=payload,
                timeout=10
            )
            data = self._validate_response(response)
            
            expiries = data.get('data', [])
            self._set_cache(cache_key, expiries)
            logger.info(f"✓ Fetched {len(expiries)} expiries")
            
            return expiries
        
        except Exception as e:
            logger.error(f"Failed to fetch expiry list: {e}")
            raise
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries (optionally by pattern)"""
        if pattern is None:
            self._cache.clear()
            self._cache_ttl.clear()
            logger.info("✓ Cache cleared")
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                del self._cache_ttl[key]
            logger.info(f"✓ Cleared {len(keys_to_delete)} cache entries matching '{pattern}'")
    
    def close(self):
        """Close HTTP session"""
        self._session.close()
        logger.info("✓ DhanAPIClient session closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TokenRefreshedException(Exception):
    """Raised when token is refreshed and request should be retried"""
    pass


# Instrument reference (commonly used)
NIFTY_INSTRUMENTS = {
    'NIFTY': {'security_id': '99926000', 'exchange': 'NSE_EQ', 'index': 'IDX_I'},
    'SENSEX': {'security_id': '12345', 'exchange': 'BSE_EQ', 'index': 'IDX_I'},
}
