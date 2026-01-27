"""
Backtesting framework for evaluating trading strategies
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from loguru import logger

from data.fetcher import DataFetcher
from signals.generator import SignalGenerator
from config.settings import TradingConfig

class Backtester:
    """
    Backtesting engine for options trading strategies
    """
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = []
        self.trade_history = []
        self.performance_metrics = {}
        
    def backtest_strategy(self, 
                         symbol: str,
                         start_date: str,
                         end_date: str,
                         initial_capital: float = None) -> Dict:
        """
        Run backtest for a specific symbol and date range
        
        Args:
            symbol: Trading symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
        
        Returns:
            Backtest results dictionary
        """
        if initial_capital:
            self.current_capital = initial_capital
            self.initial_capital = initial_capital
        
        logger.info(f"Starting backtest for {symbol} from {start_date} to {end_date}")
        
        # Fetch data
        fetcher = DataFetcher()
        signal_generator = SignalGenerator(self.config)
        
        # Get historical data
        data = fetcher.fetch_historical_data(symbol, period='2y')
        if data is None:
            logger.error(f"No data available for {symbol}")
            return {}
        
        # Filter data by date range
        data = data[start_date:end_date]
        
        if data.empty:
            logger.error(f"No data in specified date range")
            return {}
        
        # Calculate indicators
        from indicators.technical import TechnicalIndicators
        indicators = TechnicalIndicators()
        data = indicators.calculate_all_indicators(data, self.config)
        data = data.dropna()
        
        # Run backtest
        for i in range(20, len(data)):  # Start after indicator warm-up period
            current_data = data.iloc[:i+1]
            date = data.index[i]
            price = data['Close'].iloc[i]
            
            # Generate signals
            signals = signal_generator.generate_option_signals(current_data)
            
            # Process signals
            self._process_signals(signals, date, price, symbol)
        
        # Calculate final metrics
        self.performance_metrics = self._calculate_performance_metrics()
        
        return {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.current_capital,
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital * 100,
            'total_trades': len(self.trade_history),
            'performance_metrics': self.performance_metrics,
            'trade_history': self.trade_history
        }
    
    def _process_signals(self, signals: Dict, date: datetime, price: float, symbol: str):
        """Process trading signals and execute trades"""
        
        # Simple signal processing logic
        call_signal = signals['signals']['call']
        put_signal = signals['signals']['put']
        
        position_size = self.current_capital * 0.05  # 5% per trade
        
        # Call option logic
        if call_signal['action'] == 'buy' and call_signal['strength'] >= 0.7:
            self._execute_trade('CALL', 'BUY', position_size, price, date, symbol)
        
        # Put option logic  
        if put_signal['action'] == 'buy' and put_signal['strength'] >= 0.7:
            self._execute_trade('PUT', 'BUY', position_size, price, date, symbol)
    
    def _execute_trade(self, option_type: str, action: str, amount: float, 
                      price: float, date: datetime, symbol: str):
        """Execute a trade"""
        
        # Simplified options pricing (for demo purposes)
        # In real implementation, use Black-Scholes or other pricing models
        option_price = price * 0.02  # Assume 2% of underlying price
        
        if action == 'BUY':
            quantity = amount / option_price
            cost = quantity * option_price
            
            if cost <= self.current_capital:
                self.current_capital -= cost
                
                trade = {
                    'date': date,
                    'symbol': symbol,
                    'option_type': option_type,
                    'action': action,
                    'quantity': quantity,
                    'price': option_price,
                    'cost': cost,
                    'underlying_price': price
                }
                
                self.trade_history.append(trade)
                logger.info(f"Executed {action} {option_type} trade: {quantity:.2f} @ ₹{option_price:.2f}")
    
    def _calculate_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        
        if not self.trade_history:
            return {}
        
        # Convert trade history to DataFrame for easier analysis
        trades_df = pd.DataFrame(self.trade_history)
        
        # Basic metrics
        total_trades = len(trades_df)
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100
        
        # Calculate daily returns (simplified)
        daily_returns = [0]  # Would need more sophisticated calculation in real implementation
        
        metrics = {
            'total_trades': total_trades,
            'total_return_pct': total_return,
            'final_capital': self.current_capital,
            'trades_by_type': trades_df['option_type'].value_counts().to_dict() if not trades_df.empty else {},
            'avg_trade_size': trades_df['cost'].mean() if not trades_df.empty else 0,
        }
        
        return metrics
    
    def generate_report(self, backtest_results: Dict) -> str:
        """Generate a formatted backtest report"""
        
        if not backtest_results:
            return "No backtest results available"
        
        report = []
        report.append("=" * 60)
        report.append("🔄 BACKTEST RESULTS")
        report.append("=" * 60)
        report.append(f"Symbol: {backtest_results['symbol']}")
        report.append(f"Period: {backtest_results['start_date']} to {backtest_results['end_date']}")
        report.append(f"Initial Capital: ₹{backtest_results['initial_capital']:,.2f}")
        report.append(f"Final Capital: ₹{backtest_results['final_capital']:,.2f}")
        report.append(f"Total Return: {backtest_results['total_return']:.2f}%")
        report.append(f"Total Trades: {backtest_results['total_trades']}")
        
        metrics = backtest_results.get('performance_metrics', {})
        if metrics:
            report.append("")
            report.append("📊 Performance Metrics:")
            report.append(f"Average Trade Size: ₹{metrics.get('avg_trade_size', 0):,.2f}")
            
            trades_by_type = metrics.get('trades_by_type', {})
            for option_type, count in trades_by_type.items():
                report.append(f"{option_type} Trades: {count}")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def plot_performance(self, backtest_results: Dict):
        """Plot backtest performance charts"""
        
        try:
            # Create a simple performance chart
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
            
            # Capital curve (simplified)
            dates = [trade['date'] for trade in backtest_results.get('trade_history', [])]
            if dates:
                ax1.plot(dates, [self.initial_capital] * len(dates), label='Capital')
                ax1.set_title('Capital Curve')
                ax1.set_ylabel('Capital (₹)')
                ax1.legend()
            
            # Trade distribution
            metrics = backtest_results.get('performance_metrics', {})
            trades_by_type = metrics.get('trades_by_type', {})
            if trades_by_type:
                ax2.bar(trades_by_type.keys(), trades_by_type.values())
                ax2.set_title('Trades by Option Type')
                ax2.set_ylabel('Number of Trades')
            
            plt.tight_layout()
            plt.savefig('backtest_results.png')
            plt.show()
            
        except Exception as e:
            logger.error(f"Error plotting performance: {e}")

def run_sample_backtest():
    """Run a sample backtest"""
    
    backtester = Backtester(initial_capital=100000)
    
    # Run backtest for SENSEX
    results = backtester.backtest_strategy(
        symbol='SENSEX',
        start_date='2024-01-01',
        end_date='2024-06-30',
        initial_capital=100000
    )
    
    if results:
        # Generate report
        report = backtester.generate_report(results)
        print(report)
        
        # Plot results (optional)
        # backtester.plot_performance(results)
    
    return results

if __name__ == "__main__":
    run_sample_backtest()