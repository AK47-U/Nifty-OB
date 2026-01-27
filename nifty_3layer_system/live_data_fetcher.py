"""
MARKET DATA FETCHER
Fetches live data from Dhan API and builds TechnicalContext for analysis
"""

from typing import Optional
import pandas as pd
from datetime import datetime, timedelta
from intelligence import TechnicalContext
from dhan_api_client import DhanAPIClient
import ta  # Technical Analysis library


class LiveMarketDataFetcher:
    """Fetch and prepare live market data"""
    
    def __init__(self, dhan_client: DhanAPIClient):
        self.client = dhan_client
    
    def fetch_nifty_analysis_data(self, 
                                  security_id: str = "99926000",
                                  exchange_token: str = "99926000") -> Optional[TechnicalContext]:
        """
        Fetch all required data for NIFTY analysis
        
        Returns:
            TechnicalContext with live data or None
        """
        try:
            # Get current quote
            print("[DEBUG] Fetching live quote...")
            quote = self.client.get_quote(security_id, exchange_token)
            if not quote:
                print("[ERROR] Failed to fetch live quote")
                return None
            
            print(f"[DEBUG] Quote received: LTP={quote.ltp}")
            
            # Get historical data for indicators (last 200 candles for 5min)
            print("[DEBUG] Fetching historical data...")
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            from_date = (datetime.now() - timedelta(days=50)).strftime("%Y-%m-%d %H:%M:%S")
            
            candles = self.client.get_historical_data(
                security_id,
                exchange_token,
                from_date,
                to_date,
                interval="5minute"
            )
            
            if not candles:
                print("[ERROR] Failed to fetch historical data")
                return None
            
            print(f"[DEBUG] Got {len(candles)} candles")
        
        except Exception as e:
            print(f"[ERROR] Exception during fetch: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        # Build DataFrame
        df = pd.DataFrame(candles)
        
        # Calculate technical indicators
        indicators = self._calculate_indicators(df)
        
        # Get market depth
        depth = self.client.get_market_depth(security_id, exchange_token)
        
        # Get option chain for PCR
        from datetime import datetime
        today = datetime.now().date()
        next_thursday = today + timedelta(days=(3 - today.weekday()) % 7 or 7)
        expiry = next_thursday.strftime("%Y-%m-%d")
        
        option_chain = self.client.get_option_chain("NIFTY", expiry)
        pcr = self._calculate_pcr(option_chain) if option_chain else 1.0
        
        # Get OI changes
        call_oi_change, put_oi_change = self._calculate_oi_changes(option_chain) if option_chain else (0, 0)
        
        # Build TechnicalContext
        context = TechnicalContext(
            # Price data
            ltp=quote.ltp,
            pdh=quote.pdh,
            pdl=quote.pdl,
            
            # CPR (Camarilla)
            cpr_pivot=self._calculate_cpr_pivot(quote.pdh, quote.pdl, quote.close),
            cpr_tc=self._calculate_cpr_tc(quote.pdh, quote.pdl),
            cpr_bc=self._calculate_cpr_bc(quote.pdh, quote.pdl),
            cpr_width=quote.pdh - quote.pdl,
            
            # EMAs
            ema_5=indicators.get('ema_5', quote.ltp),
            ema_12=indicators.get('ema_12', quote.ltp),
            ema_20=indicators.get('ema_20', quote.ltp),
            ema_50=indicators.get('ema_50', quote.ltp),
            ema_100=indicators.get('ema_100', quote.ltp),
            ema_200=indicators.get('ema_200', quote.ltp),
            
            # Momentum
            rsi=indicators.get('rsi', 50),
            macd_histogram=indicators.get('macd_histogram', 0),
            macd_signal=indicators.get('macd_signal', 0),
            macd_line=indicators.get('macd', 0),
            
            # Volume
            volume=quote.volume,
            volume_20ma=indicators.get('volume_20ma', quote.volume),
            
            # Volatility
            atr=indicators.get('atr', 0),
            vix=self._fetch_vix(),  # Separate VIX fetch
            
            # Time
            current_hour=datetime.now().hour,
            current_minute=datetime.now().minute,
            
            # Options
            pcr=pcr,
            call_oi_change=call_oi_change,
            put_oi_change=put_oi_change,
            bid_ask_spread=quote.ask_price - quote.bid_price if quote.ask_price > 0 else 1.0
        )
        
        return context
    
    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate technical indicators from OHLCV data"""
        if df.empty:
            return {}
        
        indicators = {}
        
        try:
            # EMAs
            indicators['ema_5'] = ta.trend.ema_indicator(df['close'], window=5).iloc[-1] if len(df) >= 5 else df['close'].iloc[-1]
            indicators['ema_12'] = ta.trend.ema_indicator(df['close'], window=12).iloc[-1] if len(df) >= 12 else df['close'].iloc[-1]
            indicators['ema_20'] = ta.trend.ema_indicator(df['close'], window=20).iloc[-1] if len(df) >= 20 else df['close'].iloc[-1]
            indicators['ema_50'] = ta.trend.ema_indicator(df['close'], window=50).iloc[-1] if len(df) >= 50 else df['close'].iloc[-1]
            indicators['ema_100'] = ta.trend.ema_indicator(df['close'], window=100).iloc[-1] if len(df) >= 100 else df['close'].iloc[-1]
            indicators['ema_200'] = ta.trend.ema_indicator(df['close'], window=200).iloc[-1] if len(df) >= 200 else df['close'].iloc[-1]
            
            # RSI
            indicators['rsi'] = ta.momentum.rsi(df['close'], window=14).iloc[-1] if len(df) >= 14 else 50
            
            # MACD
            macd = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            indicators['macd'] = macd.macd().iloc[-1] if len(macd.macd()) > 0 else 0
            indicators['macd_signal'] = macd.macd_signal().iloc[-1] if len(macd.macd_signal()) > 0 else 0
            indicators['macd_histogram'] = macd.macd_diff().iloc[-1] if len(macd.macd_diff()) > 0 else 0
            
            # ATR
            indicators['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14).iloc[-1] if len(df) >= 14 else 0
            
            # Volume MA
            indicators['volume_20ma'] = ta.trend.sma_indicator(df['volume'], window=20).iloc[-1] if len(df) >= 20 else df['volume'].iloc[-1]
            
        except Exception as e:
            print(f"[WARNING] Indicator calculation error: {str(e)}")
        
        return indicators
    
    def _calculate_cpr_pivot(self, pdh: float, pdl: float, close: float) -> float:
        """Calculate Camarilla Pivot"""
        return (pdh + pdl + close) / 3
    
    def _calculate_cpr_tc(self, pdh: float, pdl: float) -> float:
        """Calculate CPR Top Center"""
        return (pdh + pdl) / 2 + (pdh - pdl) / 4
    
    def _calculate_cpr_bc(self, pdh: float, pdl: float) -> float:
        """Calculate CPR Bottom Center"""
        return (pdh + pdl) / 2 - (pdh - pdl) / 4
    
    def _calculate_pcr(self, option_chain: dict) -> float:
        """Calculate Put-Call Ratio from option chain"""
        try:
            calls_oi = sum(opt.get('oi', 0) for opt in option_chain.get('calls', []))
            puts_oi = sum(opt.get('oi', 0) for opt in option_chain.get('puts', []))
            
            if calls_oi == 0:
                return 1.0
            return puts_oi / calls_oi
        except:
            return 1.0
    
    def _calculate_oi_changes(self, option_chain: dict) -> tuple:
        """Calculate OI changes from option chain"""
        try:
            call_change = sum(opt.get('oi_change', 0) for opt in option_chain.get('calls', []))
            put_change = sum(opt.get('oi_change', 0) for opt in option_chain.get('puts', []))
            return call_change, put_change
        except:
            return 0, 0
    
    def _fetch_vix(self) -> float:
        """Fetch VIX value (placeholder)"""
        # In real implementation, fetch from Dhan API or external source
        return 14.0
