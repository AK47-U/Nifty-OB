"""
SLEEP & STRIKE ORCHESTRATOR
Real-time trading engine that ties all 3 layers together

Flow:
1. SLEEP MODE: Monitor price near key levels (Layer 1)
2. ALERT TRIGGERED: Price enters strike zone
3. SNIPER AUDIT: Run full intelligence system (Layer 2)
4. VERDICT: Output recommendation and execute (Layer 3)
5. CIRCUIT BREAKER: Stop after 3 signals (win or loss)
"""

import sys
import time
from pathlib import Path
from datetime import datetime, time as dt_time
from typing import Optional, Dict, List
from dataclasses import dataclass
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from layers import LevelContextEngine, SignalMomentumEngine, ExecutionEngine
from intelligence import (
    ScenarioClassifier, ConfluenceScorer, 
    ConfidenceCalculator, CopilotFormatter,
    TechnicalContext
)
from integrations import DhanDataManager
from indicators.technical import TechnicalIndicators


@dataclass
class TriggerEvent:
    """Price proximity trigger event"""
    timestamp: datetime
    ltp: float
    nearby_level: str
    level_price: float
    distance: float


class SleepAndStrike:
    """
    Real-time orchestrator that monitors price and triggers intelligence system
    """
    
    def __init__(
        self,
        symbol: str = 'NIFTY',
        use_dhan: bool = True,
        proximity_threshold: float = 20.0,
        capital: float = 15000.0,
        risk_pct: float = 1.0
    ):
        """
        Args:
            symbol: Trading symbol (NIFTY, BANKNIFTY)
            use_dhan: Use Dhan API for live data
            proximity_threshold: Distance to trigger alert (points)
            capital: Trading capital
            risk_pct: Risk per trade (%)
        """
        self.symbol = symbol
        self.capital = capital
        self.risk_pct = risk_pct
        
        # Layer 1: Level detection
        self.level_engine = LevelContextEngine(symbol, proximity_threshold)
        
        # Layer 2: Intelligence system
        self.scenario_classifier = ScenarioClassifier()
        self.confluence_scorer = ConfluenceScorer()
        self.confidence_calculator = ConfidenceCalculator()
        self.copilot_formatter = CopilotFormatter()
        
        # Layer 3: Execution
        self.execution_engine = ExecutionEngine(capital)
        
        # Data manager
        self.dhan_manager = DhanDataManager() if use_dhan else None
        self.indicators = TechnicalIndicators()
        
        # Trading state
        self.signals_today = 0
        self.max_signals = 3
        self.trading_active = True
        self.last_trigger_time = None
        self.cooldown_minutes = 15
        
        # Market hours (IST)
        self.market_open = dt_time(9, 15)
        self.lunch_start = dt_time(11, 0)
        self.lunch_end = dt_time(13, 30)
        self.power_hour = dt_time(14, 30)
        self.market_close = dt_time(15, 30)
        
        logger.info(f"Sleep & Strike initialized: {symbol} | Capital: ₹{capital} | Risk: {risk_pct}%")
    
    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        now = datetime.now().time()
        
        # Before market open or after close
        if now < self.market_open or now > self.market_close:
            return False
        
        # Lunch break (11:00 - 13:30)
        if self.lunch_start <= now < self.lunch_end:
            return False
        
        return True
    
    def is_high_probability_window(self) -> bool:
        """Check if in high-probability trading windows"""
        now = datetime.now().time()
        
        # Morning window: 9:15 - 11:00
        if self.market_open <= now < self.lunch_start:
            return True
        
        # Afternoon window: 13:30 - 15:15
        if self.lunch_end <= now < dt_time(15, 15):
            return True
        
        return False
    
    def is_power_hour(self) -> bool:
        """Check if in power hour (14:30 onwards)"""
        now = datetime.now().time()
        return now >= self.power_hour
    
    def load_market_levels(self, csv_path: str) -> bool:
        """Load historical levels from CSV"""
        return self.level_engine.load_historical_levels(csv_path)
    
    def fetch_live_market_data(self) -> Optional[Dict]:
        """
        Fetch live market data from Dhan API
        
        Returns:
            Dict with candles, LTP, ATR, PDH, PDL
        """
        if not self.dhan_manager:
            logger.error("Dhan manager not initialized")
            return None
        
        try:
            # Fetch 5-min candles (last 100)
            candles_5m = self.dhan_manager.get_nifty_candles(interval='5m', num_candles=100)
            
            # Fetch 15-min candles (last 50)
            candles_15m = self.dhan_manager.get_nifty_candles(interval='15m', num_candles=50)
            
            # Fetch daily candles (last 30 days)
            candles_daily = self.dhan_manager.get_nifty_daily(num_days=30)
            
            if candles_5m.empty or candles_daily.empty:
                logger.error("Failed to fetch market data")
                return None
            
            # Calculate indicators
            candles_5m = self.indicators.calculate_all(candles_5m)
            candles_15m = self.indicators.calculate_all(candles_15m)
            candles_daily = self.indicators.calculate_all(candles_daily)
            
            # Get latest values
            ltp = candles_5m['close'].iloc[-1]
            atr = candles_5m['atr'].iloc[-1]
            
            # Previous day values
            pdh = candles_daily['high'].iloc[-2]
            pdl = candles_daily['low'].iloc[-2]
            pdc = candles_daily['close'].iloc[-2]
            
            return {
                'candles_5m': candles_5m,
                'candles_15m': candles_15m,
                'candles_daily': candles_daily,
                'ltp': ltp,
                'atr': atr,
                'pdh': pdh,
                'pdl': pdl,
                'pdc': pdc
            }
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return None
    
    def build_technical_context(self, market_data: Dict) -> TechnicalContext:
        """
        Build TechnicalContext from market data
        
        Args:
            market_data: Dict from fetch_live_market_data()
        
        Returns:
            TechnicalContext for intelligence system
        """
        candles = market_data['candles_5m']
        ltp = market_data['ltp']
        pdh = market_data['pdh']
        pdl = market_data['pdl']
        pdc = market_data['pdc']
        
        # Calculate CPR
        pivot = (pdh + pdl + pdc) / 3
        tc = (pdh + pdl) / 2 + (pivot - (pdh + pdl) / 2)
        bc = (pdh + pdl) / 2 - (pivot - (pdh + pdl) / 2)
        
        # Latest indicators
        latest = candles.iloc[-1]
        
        # Time
        now = datetime.now()
        
        # Fetch option chain for PCR and OI
        option_data = self._get_option_flow_data()
        
        return TechnicalContext(
            ltp=ltp,
            cpr_pivot=pivot,
            cpr_tc=tc,
            cpr_bc=bc,
            cpr_width=tc - bc,
            pdh=pdh,
            pdl=pdl,
            ema_5=latest['ema_5'],
            ema_12=latest['ema_12'],
            ema_20=latest['ema_20'],
            ema_50=latest['ema_50'],
            ema_100=latest['ema_100'],
            ema_200=latest['ema_200'],
            rsi=latest['rsi'],
            macd_histogram=latest['macd_hist'],
            macd_line=latest['macd'],
            macd_signal=latest['macd_signal'],
            volume=latest['volume'],
            volume_20ma=candles['volume'].rolling(20).mean().iloc[-1],
            atr=market_data['atr'],
            vix=option_data.get('vix', 12.0),
            current_hour=now.hour,
            current_minute=now.minute,
            pcr=option_data.get('pcr', 1.0),
            call_oi_change=option_data.get('call_oi_change', 0),
            put_oi_change=option_data.get('put_oi_change', 0),
            bid_ask_spread=option_data.get('bid_ask_spread', 2.0)
        )
    
    def _get_option_flow_data(self) -> Dict:
        """
        Fetch option chain and calculate flow metrics
        
        Returns:
            Dict with PCR, OI changes, bid-ask spread
        """
        if not self.dhan_manager:
            return {'pcr': 1.0, 'call_oi_change': 0, 'put_oi_change': 0, 'bid_ask_spread': 2.0}
        
        try:
            # Get nearest expiry option chain
            expiry_list = self.dhan_manager.get_expiry_list()
            if not expiry_list:
                return {'pcr': 1.0, 'call_oi_change': 0, 'put_oi_change': 0, 'bid_ask_spread': 2.0}
            
            nearest_expiry = expiry_list[0]
            option_chain = self.dhan_manager.get_nifty_option_chain(nearest_expiry)
            
            if not option_chain:
                return {'pcr': 1.0, 'call_oi_change': 0, 'put_oi_change': 0, 'bid_ask_spread': 2.0}
            
            # Calculate PCR (Put-Call Ratio)
            total_put_oi = 0
            total_call_oi = 0
            total_call_oi_change = 0
            total_put_oi_change = 0
            bid_ask_spreads = []
            
            for strike_data in option_chain.values():
                if 'CE' in strike_data and strike_data['CE']:
                    ce = strike_data['CE']
                    total_call_oi += ce.oi
                    total_call_oi_change += ce.oi  # Approximate change
                    if ce.bid > 0 and ce.ask > 0:
                        bid_ask_spreads.append(ce.ask - ce.bid)
                
                if 'PE' in strike_data and strike_data['PE']:
                    pe = strike_data['PE']
                    total_put_oi += pe.oi
                    total_put_oi_change += pe.oi
                    if pe.bid > 0 and pe.ask > 0:
                        bid_ask_spreads.append(pe.ask - pe.bid)
            
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
            avg_spread = sum(bid_ask_spreads) / len(bid_ask_spreads) if bid_ask_spreads else 2.0
            
            return {
                'pcr': pcr,
                'call_oi_change': total_call_oi_change,
                'put_oi_change': total_put_oi_change,
                'bid_ask_spread': avg_spread,
                'vix': 12.0  # TODO: Fetch real VIX from Dhan
            }
            
        except Exception as e:
            logger.error(f"Error fetching option flow: {e}")
            return {'pcr': 1.0, 'call_oi_change': 0, 'put_oi_change': 0, 'bid_ask_spread': 2.0}
    
    def check_proximity_trigger(self, ltp: float) -> Optional[TriggerEvent]:
        """
        Check if LTP is near any key level
        
        Returns:
            TriggerEvent if proximity detected, None otherwise
        """
        nearby_levels = self.level_engine.get_proximity_levels(ltp)
        
        if not nearby_levels:
            return None
        
        # Get closest level
        closest_level = min(
            nearby_levels,
            key=lambda lvl: abs(lvl.price - ltp)
        )
        
        distance = abs(closest_level.price - ltp)
        
        return TriggerEvent(
            timestamp=datetime.now(),
            ltp=ltp,
            nearby_level=closest_level.name,
            level_price=closest_level.price,
            distance=distance
        )
    
    def run_sniper_audit(self, market_data: Dict) -> Optional[str]:
        """
        Run full intelligence system when trigger fires
        
        Args:
            market_data: Live market data
        
        Returns:
            Copilot output string or None
        """
        try:
            # Build technical context
            context = self.build_technical_context(market_data)
            
            # Layer 2: Classify scenario
            scenario = self.scenario_classifier.classify(context)
            logger.info(f"Scenario: {scenario.scenario_type.value} | Bias: {scenario.market_bias}")
            
            # Score confluence
            confluence = self.confluence_scorer.score(
                ltp=context.ltp,
                cpr_pivot=context.cpr_pivot,
                cpr_tc=context.cpr_tc,
                cpr_bc=context.cpr_bc,
                pdh=context.pdh,
                pdl=context.pdl,
                ema_5=context.ema_5,
                ema_12=context.ema_12,
                ema_20=context.ema_20,
                ema_50=context.ema_50,
                ema_100=context.ema_100,
                ema_200=context.ema_200,
                rsi=context.rsi,
                macd_histogram=context.macd_histogram,
                macd_line=context.macd_line,
                volume=context.volume,
                volume_20ma=context.volume_20ma,
                pcr=context.pcr,
                call_oi_change=context.call_oi_change,
                put_oi_change=context.put_oi_change,
                bid_ask_spread=context.bid_ask_spread,
                trend_bias=scenario.market_bias,
                in_high_prob_window=self.is_high_probability_window(),
                in_eod_window=self.is_power_hour()
            )
            logger.info(f"Confluence: {confluence.score:.1f}/10 | {confluence.quality}")
            
            # Calculate confidence
            confidence = self.confidence_calculator.calculate(scenario, confluence)
            logger.info(f"Confidence: {confidence.confidence_level} | Score: {confidence.confidence_score:.1f}/10")
            
            # Format copilot output
            # Calculate support/resistance
            pivot = context.cpr_pivot
            r1 = pivot + (context.pdh - context.pdl) * 0.33
            r2 = pivot + (context.pdh - context.pdl) * 0.66
            s1 = pivot - (context.pdh - context.pdl) * 0.33
            s2 = pivot - (context.pdh - context.pdl) * 0.66
            
            # Get ATM strike data
            atm_data = self._get_atm_strike_data(context.ltp)
            
            copilot_output = self.copilot_formatter.format_sniper_output(
                confidence=confidence,
                scenario=scenario,
                confluence=confluence,
                ltp=context.ltp,
                pdh=context.pdh,
                pdl=context.pdl,
                cpr_pivot=pivot,
                r1=r1, r2=r2, s1=s1, s2=s2,
                atm_strike=atm_data['strike'],
                atm_delta=atm_data['delta'],
                atm_ce_ltp=atm_data['ce_ltp'],
                atm_pe_ltp=atm_data['pe_ltp'],
                atm_iv=atm_data['iv'],
                atr=context.atr,
                capital=self.capital,
                risk_pct=self.risk_pct
            )
            
            return copilot_output
            
        except Exception as e:
            logger.error(f"Error in sniper audit: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_atm_strike_data(self, ltp: float) -> Dict:
        """Get ATM strike data from option chain"""
        if not self.dhan_manager:
            # Return dummy data
            atm = round(ltp / 50) * 50
            return {
                'strike': atm,
                'delta': 0.5,
                'ce_ltp': 100.0,
                'pe_ltp': 100.0,
                'iv': 0.20
            }
        
        try:
            expiry_list = self.dhan_manager.get_expiry_list()
            if not expiry_list:
                atm = round(ltp / 50) * 50
                return {
                    'strike': atm,
                    'delta': 0.5,
                    'ce_ltp': 100.0,
                    'pe_ltp': 100.0,
                    'iv': 0.20
                }
            
            option_chain = self.dhan_manager.get_nifty_option_chain(expiry_list[0])
            atm_strikes = self.dhan_manager.get_atm_strikes(option_chain, ltp)
            
            if atm_strikes:
                ce = atm_strikes['CE']
                pe = atm_strikes['PE']
                return {
                    'strike': ce.strike,
                    'delta': ce.delta,
                    'ce_ltp': (ce.bid + ce.ask) / 2,
                    'pe_ltp': (pe.bid + pe.ask) / 2,
                    'iv': ce.iv
                }
            else:
                atm = round(ltp / 50) * 50
                return {
                    'strike': atm,
                    'delta': 0.5,
                    'ce_ltp': 100.0,
                    'pe_ltp': 100.0,
                    'iv': 0.20
                }
                
        except Exception as e:
            logger.error(f"Error fetching ATM data: {e}")
            atm = round(ltp / 50) * 50
            return {
                'strike': atm,
                'delta': 0.5,
                'ce_ltp': 100.0,
                'pe_ltp': 100.0,
                'iv': 0.20
            }
    
    def sleep_mode(self, poll_interval: int = 30):
        """
        Main monitoring loop - sleeps until trigger
        
        Args:
            poll_interval: Seconds between each check (default: 30s)
        """
        logger.info("="*80)
        logger.info("SLEEP & STRIKE ENGINE STARTED")
        logger.info(f"Symbol: {self.symbol} | Max Signals: {self.max_signals} | Poll: {poll_interval}s")
        logger.info("="*80)
        
        while self.trading_active and self.signals_today < self.max_signals:
            try:
                # Check trading hours
                if not self.is_trading_hours():
                    logger.info("Outside trading hours. Sleeping...")
                    time.sleep(60)
                    continue
                
                # Fetch live market data
                logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching market data...")
                market_data = self.fetch_live_market_data()
                
                if not market_data:
                    logger.warning("Failed to fetch data. Retrying...")
                    time.sleep(poll_interval)
                    continue
                
                ltp = market_data['ltp']
                logger.info(f"LTP: ₹{ltp:.2f} | PDH: ₹{market_data['pdh']:.2f} | PDL: ₹{market_data['pdl']:.2f}")
                
                # Update level engine with daily CPR
                self.level_engine.calculate_cpr(
                    market_data['pdh'],
                    market_data['pdl'],
                    market_data['pdc']
                )
                
                # Check proximity trigger
                trigger = self.check_proximity_trigger(ltp)
                
                if trigger:
                    # Check cooldown
                    if self.last_trigger_time:
                        minutes_since_last = (datetime.now() - self.last_trigger_time).seconds / 60
                        if minutes_since_last < self.cooldown_minutes:
                            logger.info(f"Cooldown active ({self.cooldown_minutes - minutes_since_last:.1f}m remaining)")
                            time.sleep(poll_interval)
                            continue
                    
                    logger.warning("="*80)
                    logger.warning(f"TRIGGER ALERT!")
                    logger.warning(f"Level: {trigger.nearby_level} (₹{trigger.level_price:.2f})")
                    logger.warning(f"Distance: {trigger.distance:.2f} points")
                    logger.warning("="*80)
                    
                    # Run sniper audit
                    logger.info("Running Sniper Audit...")
                    copilot_output = self.run_sniper_audit(market_data)
                    
                    if copilot_output:
                        print("\n" + "█"*80)
                        print(copilot_output)
                        print("█"*80 + "\n")
                        
                        self.signals_today += 1
                        self.last_trigger_time = datetime.now()
                        
                        logger.info(f"Signal #{self.signals_today} generated. Remaining: {self.max_signals - self.signals_today}")
                    else:
                        logger.error("Sniper audit failed")
                else:
                    logger.info(f"No triggers. Sleeping for {poll_interval}s...")
                
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.warning("User interrupted. Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in sleep loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(poll_interval)
        
        # Circuit breaker
        if self.signals_today >= self.max_signals:
            logger.warning("="*80)
            logger.warning(f"CIRCUIT BREAKER TRIGGERED! Max signals ({self.max_signals}) reached.")
            logger.warning("Trading stopped for today.")
            logger.warning("="*80)
        
        logger.info("Sleep & Strike engine stopped.")


if __name__ == "__main__":
    # Initialize engine
    engine = SleepAndStrike(
        symbol='NIFTY',
        use_dhan=True,
        proximity_threshold=20.0,
        capital=15000.0,
        risk_pct=1.0
    )
    
    # Load historical levels
    levels_file = Path(__file__).parent / 'data' / 'levels_NIFTY.csv'
    if levels_file.exists():
        engine.load_market_levels(str(levels_file))
        logger.info(f"Loaded {len(engine.level_engine.historical_levels)} historical levels")
    else:
        logger.warning(f"Levels file not found: {levels_file}")
    
    # Start monitoring
    engine.sleep_mode(poll_interval=30)
