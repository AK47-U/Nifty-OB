"""
Main trading strategy implementation
Combines all components to create a comprehensive trading system
"""

import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from signals.generator import SignalGenerator
from config.settings import TradingConfig

class TradingStrategy:
    """
    Main trading strategy class that orchestrates the entire system
    """
    
    def __init__(self, 
                 symbols: List[str] = None, 
                 config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.symbols = symbols or self.config.INDICES
        self.data_fetcher = DataFetcher(self.config.DATA_SOURCE)
        self.indicators = TechnicalIndicators()
        self.signal_generator = SignalGenerator(self.config)
        self.active_signals = {}
        self.performance_metrics = {symbol: {} for symbol in self.symbols}
        
        logger.info(f"Trading strategy initialized for symbols: {self.symbols}")
    
    def fetch_and_prepare_data(self, symbol: str, timeframe: str = '1d') -> Optional[pd.DataFrame]:
        """
        Fetch and prepare data with all technical indicators
        
        Args:
            symbol: Trading symbol (SENSEX/NIFTY)
            timeframe: Data timeframe
        
        Returns:
            DataFrame with OHLCV data and all indicators
        """
        try:
            # Determine if intraday interval (contains 'm' or 'h')
            intraday_requested = any(x in timeframe for x in ['m', 'h'])
            if intraday_requested:
                interval = timeframe
            else:
                interval = self.config.INTRADAY_INTERVAL if timeframe == 'intraday' else timeframe

            if any(x in interval for x in ['m', 'h']):
                # Intraday fetch using dedicated method
                days = self.config.INTRADAY_DAYS
                data = self.data_fetcher.fetch_intraday_data(symbol=symbol, interval=interval, days=days)
            else:
                # Daily/longer timeframe historical fetch
                period = '6mo' if interval in ['1d', '1wk', '1mo', '3mo'] else '1y'
                data = self.data_fetcher.fetch_historical_data(symbol=symbol, period=period, interval=interval)
            
            if data is None or data.empty:
                logger.error(f"No data available for {symbol}")
                return None
            
            # Calculate all technical indicators
            data_with_indicators = self.indicators.calculate_all_indicators(data, self.config)
            
            # Remove rows with NaN values (due to indicator calculations)
            data_with_indicators = data_with_indicators.dropna()
            
            logger.info(f"Prepared {len(data_with_indicators)} data points for {symbol}")
            return data_with_indicators
            
        except Exception as e:
            logger.error(f"Error preparing data for {symbol}: {e}")
            return None
    
    def generate_signals_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate trading signals for a specific symbol
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Signal dictionary or None if error
        """
        try:
            # Prepare data
            data = self.fetch_and_prepare_data(symbol)
            if data is None:
                return None
            
            # Generate signals
            signals = self.signal_generator.generate_option_signals(data)
            signals['symbol'] = symbol
            
            # Store active signals
            self.active_signals[symbol] = signals
            
            logger.info(f"Generated signals for {symbol}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return None
    
    def scan_all_symbols(self) -> Dict[str, Dict[str, Any]]:
        """
        Scan all configured symbols and generate signals
        
        Returns:
            Dictionary with signals for all symbols
        """
        all_signals = {}
        
        for symbol in self.symbols:
            logger.info(f"Scanning {symbol}...")
            signals = self.generate_signals_for_symbol(symbol)
            if signals:
                all_signals[symbol] = signals
        
        return all_signals
    
    def get_market_overview(self) -> Dict[str, Any]:
        """
        Get comprehensive market overview with live data
        
        Returns:
            Market overview dictionary
        """
        market_data = {}
        
        for symbol in self.symbols:
            try:
                # Get live data
                live_data = self.data_fetcher.fetch_live_data(symbol)
                if live_data:
                    market_data[symbol] = live_data
            except Exception as e:
                logger.error(f"Error fetching live data for {symbol}: {e}")
        
        # Get market status
        market_status = self.data_fetcher.get_market_status()
        
        return {
            'market_status': market_status,
            'live_data': market_data,
            'last_updated': datetime.now()
        }
    
    def run_analysis(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Run complete analysis for specified symbols
        
        Args:
            symbols: List of symbols to analyze (default: all configured)
        
        Returns:
            Complete analysis results
        """
        target_symbols = symbols or self.symbols
        
        results = {
            'analysis_time': datetime.now(),
            'market_overview': self.get_market_overview(),
            'signals': {},
            'summary': {}
        }
        
        # Generate signals for each symbol
        for symbol in target_symbols:
            signals = self.generate_signals_for_symbol(symbol)
            if signals:
                results['signals'][symbol] = signals
        
        # Create summary
        results['summary'] = self._create_summary(results['signals'])
        
        return results

    def run_intraday_analysis(self, symbols: List[str] = None, interval: str = None) -> Dict[str, Any]:
        """Run intraday analysis using configured or provided interval (default 5m)."""
        interval = interval or self.config.INTRADAY_INTERVAL
        target_symbols = symbols or self.symbols
        results = {
            'analysis_time': datetime.now(),
            'market_overview': self.get_market_overview(),
            'signals': {},
            'summary': {}
        }
        for symbol in target_symbols:
            data = self.fetch_and_prepare_data(symbol, timeframe=interval)
            if data is None:
                continue
            signals = self.signal_generator.generate_option_signals(data)
            signals['symbol'] = symbol
            results['signals'][symbol] = signals
        results['summary'] = self._create_summary(results['signals'])
        return results
    
    def _create_summary(self, signals_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create summary of all signals
        
        Args:
            signals_data: Dictionary with signals for all symbols
        
        Returns:
            Summary dictionary
        """
        summary = {
            'total_symbols': len(signals_data),
            'call_signals': 0,
            'put_signals': 0,
            'hold_signals': 0,
            'strong_signals': []
        }
        
        for symbol, signal_data in signals_data.items():
            signals = signal_data.get('signals', {})
            
            # Count signal types
            if signals.get('call', {}).get('action') == 'buy':
                summary['call_signals'] += 1
                if signals['call']['strength'] >= 0.8:
                    summary['strong_signals'].append(f"{symbol} CALL")
            
            if signals.get('put', {}).get('action') == 'buy':
                summary['put_signals'] += 1
                if signals['put']['strength'] >= 0.8:
                    summary['strong_signals'].append(f"{symbol} PUT")
            
            if (signals.get('call', {}).get('action') == 'hold' and 
                signals.get('put', {}).get('action') == 'hold'):
                summary['hold_signals'] += 1
        
        return summary
    
    def format_analysis_report(self, analysis_results: Dict[str, Any]) -> str:
        """
        Format analysis results into a readable report
        
        Args:
            analysis_results: Results from run_analysis
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("🎯 INDIAN INDICES OPTIONS TRADING ANALYSIS")
        report.append("=" * 60)
        report.append(f"📅 Analysis Time: {analysis_results['analysis_time'].strftime('%Y-%m-%d %H:%M:%S')}")

        # Market status
        market_status = analysis_results['market_overview']['market_status']
        status_emoji = "🟢" if market_status['is_open'] else "🔴"
        report.append(f"{status_emoji} Market Status: {'OPEN' if market_status['is_open'] else 'CLOSED'}")

        # Quick price line for each symbol (from live data when available)
        live_data = analysis_results['market_overview']['live_data']
        for symbol in self.symbols:
            ld = live_data.get(symbol)
            if ld:
                change_emoji = "📈" if ld['change'] >= 0 else "📉"
                report.append(f"{change_emoji} {symbol}: ₹{ld['current_price']:.2f} ({ld['change_percent']:+.2f}%)")

        report.append("")
        report.append("🔍 DETAILED ANALYSIS (BY SYMBOL):")
        report.append("-" * 60)

        # Helper to format EMA values in a consistent order
        def _format_emas(ema_values: Dict[int, float]) -> str:
            order = [5, 12, 20, 50, 200]
            parts = []
            for p in order:
                if p in ema_values:
                    parts.append(f"EMA{p}: ₹{ema_values[p]:.2f}")
            return " | ".join(parts[:5])

        # Per-symbol blocks in configured order
        for symbol in self.symbols:
            signal_data = analysis_results['signals'].get(symbol)
            if not signal_data:
                continue

            report.append(f"📌 {symbol}")
            report.append("~" * 60)

            price = signal_data.get('current_price')
            # Prefer live change percent if available
            ld = live_data.get(symbol)
            change_pct = ld['change_percent'] if ld else None
            if price is not None:
                if change_pct is not None:
                    report.append(f"Price: ₹{price:.2f} ({change_pct:+.2f}%)")
                else:
                    report.append(f"Price: ₹{price:.2f}")

            # Trend
            trend = signal_data.get('trend_analysis', {})
            overall = trend.get('overall_trend', 'neutral').replace('_', ' ').title()
            aligned = 'Aligned Bullish ✅' if trend.get('ema_alignment_bullish') else (
                      'Aligned Bearish ✅' if trend.get('ema_alignment_bearish') else 'Mixed ⚪')
            report.append(f"Trend: {overall} | EMA: {aligned}")

            ema_values = trend.get('ema_values', {})
            if ema_values:
                report.append(f"EMAs: {_format_emas(ema_values)}")

            # Momentum
            mom = signal_data.get('momentum_analysis', {})
            rsi = mom.get('rsi_value')
            if rsi is not None:
                rsi_status = "Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral")
                report.append(f"RSI: {rsi:.1f} ({rsi_status}) | MACD: {mom.get('macd_trend','neutral').title()}")

            # Support/Resistance or Zone
            sr = signal_data.get('support_resistance', {})
            sup = sr.get('nearest_support')
            res = sr.get('nearest_resistance')
            if sup and res and price:
                gap_pct = (res - sup) / price if price else None
                if gap_pct is not None and gap_pct < 0.0002:  # < 0.02% -> treat as a balance zone
                    report.append(f"Zone: Balance ₹{sup:.2f} – ₹{res:.2f}")
                else:
                    report.append(f"Support: ₹{sup:.2f} | Resistance: ₹{res:.2f}")
            else:
                if sup:
                    report.append(f"Support: ₹{sup:.2f}")
                if res:
                    report.append(f"Resistance: ₹{res:.2f}")

            # Signals
            call_sig = signal_data['signals'].get('call', {})
            put_sig = signal_data['signals'].get('put', {})

            def _fmt_sig(name: str, sig: Dict[str, Any]) -> str:
                action = sig.get('action', 'hold').upper()
                strength = sig.get('strength', 0)
                reasons = sig.get('reasons', [])
                if action == 'HOLD':
                    return f"{name}: HOLD"
                top_reasons = '; '.join(reasons[:2]) if reasons else ''
                return f"{name}: {action} (Strength {strength:.2f})" + (f" | {top_reasons}" if top_reasons else '')

            report.append(_fmt_sig('CALL', call_sig))
            report.append(_fmt_sig('PUT', put_sig))

            report.append("-" * 60)

        # Summary
        summary = analysis_results['summary']
        report.append("")
        report.append("📊 SUMMARY:")
        report.append(f"Total Symbols Analyzed: {summary['total_symbols']}")
        report.append(f"Call Signals: {summary['call_signals']}")
        report.append(f"Put Signals: {summary['put_signals']}")
        report.append(f"Hold Signals: {summary['hold_signals']}")

        if summary['strong_signals']:
            report.append("\n⚡ STRONG SIGNALS:")
            for signal in summary['strong_signals']:
                report.append(f"   • {signal}")

        report.append("=" * 60)

        return "\n".join(report)
    
    def start_monitoring(self, interval_minutes: int = 5):
        """
        Start continuous monitoring and signal generation
        
        Args:
            interval_minutes: Update interval in minutes
        """
        import time
        
        logger.info(f"Starting monitoring with {interval_minutes}-minute intervals...")
        
        # Different intervals based on market status
        market_open_interval = interval_minutes * 60  # Normal interval when market open
        market_closed_interval = interval_minutes * 60 * 3  # Slower when market closed
        
        while True:
            try:
                # Check if market is open
                is_open = self.data_fetcher.is_market_open()
                current_interval = market_open_interval if is_open else market_closed_interval
                
                if is_open:
                    logger.info("🟢 Market is open - running real-time analysis...")
                    
                    # Run analysis
                    results = self.run_analysis()
                    
                    # Format and log report
                    report = self.format_analysis_report(results)
                    print(report)
                    
                    # Check for strong signals and alert
                    strong_signals = results['summary'].get('strong_signals', [])
                    if strong_signals:
                        print("\n🚨 STRONG SIGNAL ALERT!")
                        for signal in strong_signals:
                            print(f"   ⚡ {signal}")
                        print()
                        
                        # Here you could add notification logic (email, Telegram, etc.)
                        # Example: send_notification(f"Strong signal detected: {signal}")
                    
                else:
                    logger.info("🔴 Market is closed - running basic checks...")
                    
                    # Just check live data when market closed
                    overview = self.get_market_overview()
                    print(f"\n📊 Market Status: CLOSED")
                    for symbol, data in overview['live_data'].items():
                        print(f"   {symbol}: ₹{data['current_price']:,.2f} ({data['change_percent']:+.2f}%)")
                
                # Show next update time
                next_update = time.time() + current_interval
                next_update_str = time.strftime('%H:%M:%S', time.localtime(next_update))
                print(f"\n⏰ Next update at: {next_update_str}")
                print("=" * 60)
                
                # Wait for next interval
                time.sleep(current_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying


if __name__ == "__main__":
    # Minimal CLI with interactive fallback
    cfg = TradingConfig()
    strat = TradingStrategy(config=cfg)

    # Determine mode: CLI arg > env var > interactive prompt > default
    env_mode = os.getenv("TRADEBOT_MODE", "").strip().lower()
    cli_mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""
    mode = cli_mode or env_mode

    if not mode:
        try:
            if sys.stdin.isatty():
                print("Select mode:")
                print("  [1] Analyze once (intraday)")
                print("  [2] Monitor (live updates)")
                choice = input("Enter 1 or 2 [default 1]: ").strip()
                if choice == "2":
                    mode = "monitor"
                else:
                    mode = "analyze"
            else:
                mode = "analyze"
        except Exception:
            mode = "analyze"

    if mode in ("monitor", "watch", "live", "2", "m"):
        print("Starting live monitoring (5m updates by default)...")
        # Determine interval minutes: CLI arg #2 > env > default 5
        interval_arg = 5
        if len(sys.argv) > 2:
            try:
                interval_arg = int(sys.argv[2])
            except ValueError:
                interval_arg = 5
        else:
            try:
                interval_env = os.getenv("TRADEBOT_INTERVAL_MINUTES", "").strip()
                if interval_env:
                    interval_arg = int(interval_env)
            except ValueError:
                interval_arg = 5
        strat.start_monitoring(interval_minutes=interval_arg)
    else:
        print("Running one-time intraday analysis (configured interval)...\n")
        results = strat.run_intraday_analysis(interval=cfg.INTRADAY_INTERVAL)
        report = strat.format_analysis_report(results)
        print(report)