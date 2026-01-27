"""
ORCHESTRATOR: 3-Layer Trading System Coordinator
Coordinates Layer 1 → Layer 2 → Layer 3 execution flow

Data Flow:
1. Layer 1: Detect proximity to level (WHERE)
2. Layer 2: Validate technical confluence (WHEN)
3. Layer 3: Select strike & execute (WHAT)

Data Integration: Now powered by Dhan API (from integrations.dhan_data_manager)
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict
from loguru import logger

from layers.level_engine import LevelContextEngine
from layers.signal_engine import SignalMomentumEngine
from layers.execution_engine import ExecutionGreeksEngine, ExecutionSetup
from integrations import DhanDataManager, DhanAPIClient


class TradingOrchestrator:
    """
    Main orchestrator that coordinates all 3 layers
    Only pushes signal to next layer if previous layer validates
    Powered by Dhan API for live data
    """
    
    def __init__(self, symbol: str = 'NIFTY', capital: float = 15000.0, use_dhan: bool = True):
        """
        Initialize the complete 3-layer system
        
        Args:
            symbol: Trading symbol (NIFTY, SENSEX)
            capital: Trading capital in rupees
            use_dhan: Use Dhan API for live data (True) or yfinance fallback (False)
        """
        self.symbol = symbol
        self.use_dhan = use_dhan
        
        # Initialize layers
        self.layer1 = LevelContextEngine(symbol, proximity_distance=25.0)
        self.layer2 = SignalMomentumEngine()
        self.layer3 = ExecutionGreeksEngine(capital)
        
        # Initialize Dhan data manager if enabled
        self.data_manager: Optional[DhanDataManager] = None
        if use_dhan:
            try:
                client = DhanAPIClient()
                self.data_manager = DhanDataManager(client)
                logger.info("✓ Dhan API integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Dhan: {e}. Falling back to yfinance")
                self.use_dhan = False
        
        self.last_setup: Optional[ExecutionSetup] = None
        
        logger.info(f"✓ Orchestrator initialized: {symbol} | Capital: ₹{capital} | Data: {'Dhan' if self.use_dhan else 'yfinance'}")
    
    def load_levels(self, csv_path: str) -> bool:
        """Load historical levels from CSV"""
        return self.layer1.load_historical_levels(csv_path)
    
    def fetch_dhan_market_data(self, interval_5m: int = 5, interval_15m: int = 15, days: int = 5) -> Dict:
        """
        Fetch live market data from Dhan API
        
        Returns:
            Dict with intraday_5m, intraday_15m, daily DataFrames and current LTP
        """
        if not self.use_dhan or self.data_manager is None:
            raise RuntimeError("Dhan integration not enabled")
        
        logger.info("Fetching live data from Dhan API...")
        
        try:
            # Fetch candles
            intraday_5m = self.data_manager.get_nifty_candles(interval=interval_5m, days=days)
            intraday_15m = self.data_manager.get_nifty_candles(interval=interval_15m, days=days)
            daily = self.data_manager.get_nifty_daily(days=365)
            
            # Get current LTP (latest close)
            ltp = float(intraday_5m['close'].iloc[-1])
            
            # Get previous day data
            if len(daily) > 1:
                pdt_row = daily.iloc[-2]
            else:
                pdt_row = daily.iloc[-1]
            
            # Calculate ATR (14-period)
            daily['tr'] = (
                daily[['high']].values - daily[['low']].values
            ).max(axis=1)
            atr = float(daily['tr'].rolling(14).mean().iloc[-1])
            
            logger.info(f"✓ Dhan data loaded | LTP: {ltp:.2f} | ATR: {atr:.0f}")
            
            return {
                'intraday_5m': intraday_5m,
                'intraday_15m': intraday_15m,
                'daily': daily,
                'ltp': ltp,
                'pdt_high': float(pdt_row['high']),
                'pdt_low': float(pdt_row['low']),
                'pdt_close': float(pdt_row['close']),
                'atr': atr
            }
        
        except Exception as e:
            logger.error(f"Failed to fetch Dhan data: {e}")
            raise
    
    def fetch_dhan_option_chain(self, expiry: Optional[str] = None) -> Dict:
        """
        Fetch NIFTY option chain from Dhan API
        
        Args:
            expiry: Expiry date in YYYY-MM-DD format (uses nearest if None)
        
        Returns:
            Dict with parsed option chain
        """
        if not self.use_dhan or self.data_manager is None:
            raise RuntimeError("Dhan integration not enabled")
        
        logger.info("Fetching option chain from Dhan API...")
        
        try:
            if expiry is None:
                expiry = self.data_manager.get_nearest_expiry()
            
            option_chain = self.data_manager.get_nifty_option_chain(expiry)
            logger.info(f"✓ Option chain loaded | Expiry: {expiry} | Strikes: {len(option_chain)}")
            
            return {
                'chain': option_chain,
                'expiry': expiry,
                'timestamp': datetime.now()
            }
        
        except Exception as e:
            logger.error(f"Failed to fetch option chain: {e}")
            raise
    
    def process_market(
        self,
        ltp: float,
        intraday_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        pdt_high: float,
        pdt_low: float,
        pdt_close: float,
        atr: float,
        option_chain: Optional[pd.DataFrame] = None
    ) -> Optional[ExecutionSetup]:
        """
        Complete market processing through all 3 layers
        
        Args:
            ltp: Current Last Traded Price
            intraday_df: 5-min OHLCV data
            trend_df: 15-min OHLCV data
            pdt_high/low/close: Previous day OHLC
            atr: Current ATR value
            option_chain: Option chain DataFrame (optional for testing)
        
        Returns:
            ExecutionSetup if trade is triggered, None otherwise
        """
        
        print("\n" + "="*90)
        print(f"3-LAYER TRADING SYSTEM | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*90)
        
        # ============ LAYER 1: Level Context ============
        print("\n[LAYER 1] WHERE - Proximity to Levels")
        print("-"*90)
        
        # Calculate CPR
        self.layer1.calculate_cpr(pdt_high, pdt_low, pdt_close)
        
        # Check proximity
        context = self.layer1.get_level_context(ltp)
        
        print(f"Current LTP: {ltp:.2f}")
        print(f"CPR Zone: {context['cpr_zone']}")
        print(f"Proximity Alert: {context['proximity']['in_proximity']}")
        
        if not context['proximity']['in_proximity']:
            print("✗ NO PROXIMITY TO ANY LEVEL - Skip Layer 2 & 3")
            return None
        
        print(f"✓ Proximity Detected! Nearest: {context['proximity']['nearest_level']}")
        print(f"  Distance: {context['proximity']['distance_to_nearest']:.1f}pts")
        print(f"  Zone Type: {context['proximity']['zone_type']}")
        
        # Determine signal direction based on zone proximity
        if context['proximity']['zone_type'] == 'resistance':
            direction = 'bearish'
            signal_type = 'PUT'
        else:
            direction = 'bullish'
            signal_type = 'CALL'
        
        print(f"✓ Suggested Direction: {direction.upper()} ({signal_type})")
        
        # ============ LAYER 2: Signal & Momentum ============
        print("\n[LAYER 2] WHEN - Technical Confluence")
        print("-"*90)
        
        confluence = self.layer2.validate_signal(intraday_df, trend_df, direction)
        
        print(f"\nConfluence Validation for {signal_type}:")
        print(f"  EMA Alignment:    {confluence.ema_aligned:5} (5 > 12 > 20 for CALL)")
        print(f"  VWAP Alignment:   {confluence.vwap_aligned:5} (Price > VWAP for CALL)")
        print(f"  RSI Momentum:     {confluence.rsi_valid:5} (> 60 for CALL, < 40 for PUT)")
        print(f"  MACD Histogram:   {confluence.macd_valid:5} (Positive & rising for CALL)")
        print(f"  MTF Alignment:    {confluence.mtf_aligned:5} (5m & 15m trend aligned)")
        
        print(f"\nConfluence Score: {confluence.confluence_score:.2f}/1.0")
        print(f"Signal Strength: {confluence.signal_strength.upper()}")
        
        if not confluence.ready_to_trade:
            print("✗ SIGNAL NOT READY - Confluence too weak!")
            return None
        
        print(f"✓ SIGNAL READY - Proceeding to execution!")
        
        # ============ LAYER 3: Execution & Greeks ============
        print("\n[LAYER 3] WHAT - Strike Selection & Risk")
        print("-"*90)
        
        # Mock option chain if not provided
        if option_chain is None:
            print("✗ Option chain not provided - creating mock for demo")
            option_chain = self._create_mock_option_chain(ltp, signal_type)
        
        # Select best strike
        best_strike = self.layer3.select_best_strike(option_chain, signal_type)
        
        if best_strike is None:
            print("✗ Could not select strike - aborting trade")
            return None
        
        print(f"\n✓ Strike Selected: {best_strike['strike']:.0f}")
        print(f"  Delta: {best_strike['delta']:.2f}")
        print(f"  IV: {best_strike['iv']:.2f}")
        print(f"  Bid/Ask: {best_strike['bid']:.0f}/{best_strike['ask']:.0f}")
        print(f"  Volume/OI: {best_strike['volume']}/{best_strike['oi']}")
        
        # Calculate execution setup
        setup = self.layer3.calculate_execution_setup(
            signal_type=signal_type,
            entry_price=ltp,
            atr=atr,
            best_strike=best_strike,
            cpr_levels=self.layer1.cpr_levels,
            r_levels={
                'r1': self.layer1.cpr_levels['r1'],
                'r2': self.layer1.cpr_levels['r2'],
                'r3': self.layer1.cpr_levels['r3'],
                'r4': self.layer1.cpr_levels['r4']
            },
            s_levels={
                's1': self.layer1.cpr_levels['s1'],
                's2': self.layer1.cpr_levels['s2'],
                's3': self.layer1.cpr_levels['s3'],
                's4': self.layer1.cpr_levels['s4']
            }
        )
        
        # Check risk limits
        limits = self.layer3.check_risk_limits()
        
        print(f"\n✓ Execution Setup Ready:")
        print(f"  Contract: {setup.contract_type} @ Strike {setup.strike:.0f}")
        print(f"  Entry: {setup.entry_price:.2f}")
        print(f"  SL: {setup.stop_loss:.2f} ({setup.risk_points:.1f}pts risk)")
        print(f"  T1: {setup.target_1:.2f} | T2: {setup.target_2:.2f} | T3: {setup.target_3:.2f}")
        print(f"  R:R (T1): 1:{setup.risk_reward_1:.2f}")
        print(f"  Quantity: {setup.quantity} lots")
        print(f"  Max Risk: ₹{setup.max_loss:.0f} | Max Profit: ₹{setup.max_profit:.0f}")
        
        print(f"\nRisk Management:")
        print(f"  Daily Loss Limit: ₹{limits['daily_loss_limit']:.0f}")
        print(f"  Current Daily PnL: ₹{limits['current_daily_pnl']:.0f}")
        print(f"  Trades Today: {limits['trades_today']}/{limits['max_trades_allowed']}")
        print(f"  Can Trade: {limits['can_trade']}")
        
        if not limits['can_trade']:
            print("✗ Risk limits exceeded - trade rejected!")
            return None
        
        # ============ READY TO TRADE ============
        print("\n" + "="*90)
        print("✓✓✓ ALL LAYERS VALIDATED - READY TO EXECUTE ✓✓✓")
        print("="*90)
        
        setup.status = 'active'
        setup.entry_time = datetime.now()
        self.last_setup = setup
        
        return setup
    
    def _create_mock_option_chain(self, ltp: float, signal_type: str) -> pd.DataFrame:
        """Create mock option chain for testing"""
        contract_type = 'CE' if signal_type == 'CALL' else 'PE'
        
        strikes = [ltp - 100, ltp - 50, ltp, ltp + 50, ltp + 100]
        data = []
        
        for i, strike in enumerate(strikes):
            data.append({
                'strike': strike,
                'type': contract_type,
                'delta': 0.3 + (i * 0.1),
                'iv': 0.25 + (i * 0.01),
                'bid': 100 - (i * 15),
                'ask': 110 - (i * 15),
                'volume': 2000 - (i * 300),
                'oi': 50000 - (i * 5000)
            })
        
        return pd.DataFrame(data)


# Test
if __name__ == "__main__":
    import yfinance as yf
    
    orchestrator = TradingOrchestrator('NIFTY', capital=15000.0)
    
    # Load historical levels
    print("Loading historical levels...")
    orchestrator.load_levels('data/levels_NIFTY.csv')
    
    # Fetch market data
    print("Fetching market data...")
    intraday = yf.download('^NSEI', period='5d', interval='5m', progress=False)
    trend = yf.download('^NSEI', period='5d', interval='15m', progress=False)
    daily = yf.download('^NSEI', period='1y', interval='1d', progress=False)
    
    ltp = float(intraday['Close'].iloc[-1])
    atr = float(intraday['Close'].pct_change().rolling(14).std().iloc[-1] * ltp * 100)  # Rough ATR
    
    pdt_high = float(daily['High'].iloc[-1])
    pdt_low = float(daily['Low'].iloc[-1])
    pdt_close = float(daily['Close'].iloc[-1])
    
    print(f"\nMarket Data:")
    print(f"  LTP: {ltp:.2f}")
    print(f"  ATR: {atr:.0f}")
    print(f"  Prev Day: {pdt_low:.2f} - {pdt_high:.2f} (C: {pdt_close:.2f})")
    
    # Run orchestrator
    setup = orchestrator.process_market(
        ltp=ltp,
        intraday_df=intraday,
        trend_df=trend,
        pdt_high=pdt_high,
        pdt_low=pdt_low,
        pdt_close=pdt_close,
        atr=atr
    )
    
    if setup:
        print(f"\n✓ TRADE SETUP GENERATED")
        print(f"  Ready to send order to broker!")
    else:
        print(f"\n✗ NO TRADE GENERATED")
