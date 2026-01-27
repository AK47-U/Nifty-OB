"""
DHAN API INTEGRATION
Fetches live market data from Dhan API
"""

import requests
from typing import Dict, Optional
from dataclasses import dataclass
import json


@dataclass
class DhanQuoteData:
    """Live market data from Dhan"""
    symbol: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int
    bid_price: float
    bid_qty: int
    ask_price: float
    ask_qty: int
    pdh: float
    pdl: float
    timestamp: str


class DhanAPIClient:
    """Dhan API client for live data"""
    
    def __init__(self, access_token: str, client_id: str):
        self.access_token = access_token
        self.client_id = client_id
        self.base_url = "https://api.dhan.co/v2"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_quote(self, security_id: str, exchange_token: str) -> Optional[DhanQuoteData]:
        """
        Get live quote for a security
        
        Args:
            security_id: Dhan security ID (e.g., "NIFTY" = 99926000)
            exchange_token: Exchange token (e.g., "99926000" for NIFTY)
        
        Returns:
            DhanQuoteData or None if error
        """
        try:
            endpoint = f"{self.base_url}/quotes/"
            params = {
                "mode": "LTP",
                "securityId": security_id,
                "exchangeTokens": exchange_token
            }
            
            print(f"[DEBUG] Calling Dhan API: {endpoint}")
            print(f"[DEBUG] Params: {params}")
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Response body: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data:
                    quote = data['data'][0] if isinstance(data['data'], list) else data['data']
                    return DhanQuoteData(
                        symbol=quote.get('symbol', 'NIFTY'),
                        ltp=quote.get('ltp', 0),
                        open=quote.get('open', 0),
                        high=quote.get('high', 0),
                        low=quote.get('low', 0),
                        close=quote.get('close', 0),
                        volume=quote.get('volume', 0),
                        oi=quote.get('oi', 0),
                        bid_price=quote.get('bidPrice', 0),
                        bid_qty=quote.get('bidQty', 0),
                        ask_price=quote.get('askPrice', 0),
                        ask_qty=quote.get('askQty', 0),
                        pdh=quote.get('prevDayHigh', 0),
                        pdl=quote.get('prevDayLow', 0),
                        timestamp=quote.get('timestamp', '')
                    )
            else:
                print(f"[ERROR] API returned status {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Dhan API error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def get_historical_data(self, 
                           security_id: str,
                           exchange_token: str,
                           from_date: str,
                           to_date: str,
                           interval: str = "5minute") -> Optional[list]:
        """
        Get historical OHLCV data
        
        Args:
            security_id: Dhan security ID
            exchange_token: Exchange token
            from_date: From date (YYYY-MM-DD HH:MM:SS)
            to_date: To date (YYYY-MM-DD HH:MM:SS)
            interval: "1minute", "5minute", "15minute", "1hour", "1day"
        
        Returns:
            List of OHLCV candles
        """
        try:
            endpoint = f"{self.base_url}/historical/"
            params = {
                "securityId": security_id,
                "exchangeToken": exchange_token,
                "from": from_date,
                "to": to_date,
                "interval": interval
            }
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
        except Exception as e:
            print(f"[ERROR] Historical data error: {str(e)}")
        
        return None
    
    def get_option_chain(self,
                        underlying: str,
                        expiry_date: str) -> Optional[Dict]:
        """
        Get option chain data
        
        Args:
            underlying: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            expiry_date: Expiry date (YYYY-MM-DD)
        
        Returns:
            Option chain data
        """
        try:
            endpoint = f"{self.base_url}/optionchain/"
            params = {
                "underlying": underlying,
                "expiryDate": expiry_date
            }
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Option chain error: {str(e)}")
        
        return None
    
    def get_market_depth(self, security_id: str, exchange_token: str) -> Optional[Dict]:
        """
        Get market depth (bid-ask levels)
        
        Args:
            security_id: Dhan security ID
            exchange_token: Exchange token
        
        Returns:
            Market depth data
        """
        try:
            endpoint = f"{self.base_url}/marketdepth/"
            params = {
                "securityId": security_id,
                "exchangeToken": exchange_token
            }
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    return data['data']
        except Exception as e:
            print(f"[ERROR] Market depth error: {str(e)}")
        
        return None


# Dhan API Configuration
DHAN_CONFIG = {
    "access_token": "YOUR_DHAN_ACCESS_TOKEN",  # Replace with actual token
    "client_id": "YOUR_CLIENT_ID",              # Replace with actual client ID
    
    # NIFTY 50 Index
    "NIFTY": {
        "security_id": "99926000",
        "exchange_token": "99926000"
    },
    
    # NIFTY Options
    "NIFTY_OPTIONS": {
        "underlying": "NIFTY"
    }
}


def create_dhan_client(access_token: str, client_id: str) -> DhanAPIClient:
    """Create Dhan API client"""
    return DhanAPIClient(access_token, client_id)
