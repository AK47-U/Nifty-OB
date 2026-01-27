<!-- Trading Signal Generator for Indian Indices Options Trading -->

## Project Context
This is a Python-based trading signal generator for Indian indices (SENSEX and NIFTY) options trading. The system uses multiple technical analysis indicators to generate buy/sell signals for call and put options.

## Technical Indicators Used
- EMA: 5, 12, 20, 50, 200 periods
- CPR (Central Pivot Range) with classical support/resistance
- Previous high/low levels
- VWAP (Volume Weighted Average Price)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)

## Project Structure
- `data/` - Data fetching and processing modules
- `indicators/` - Technical indicator calculations
- `signals/` - Signal generation logic
- `strategies/` - Trading strategy implementations
- `backtesting/` - Backtesting framework
- `utils/` - Utility functions
- `config/` - Configuration files
- `tests/` - Unit tests

## Data Sources
- Yahoo Finance API (primary free source)
- NSE/BSE APIs (backup)
- Real-time and historical data support

## Coding Guidelines
- Use pandas for data manipulation
- Implement proper error handling and logging
- Follow modular design patterns
- Include comprehensive docstrings
- Use type hints for better code clarity
- Implement configuration-driven parameters
- Focus on performance optimization for real-time data processing

## Signal Generation Rules
- Multi-timeframe analysis support
- Risk management integration
- Position sizing calculations
- Entry/exit timing optimization
- Backtesting validation required