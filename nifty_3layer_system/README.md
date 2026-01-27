# NIFTY 3-Layer Trading System

**Status:** 🧪 Experimental | **Development:** Active

A comprehensive, modular 3-layer trading architecture for NIFTY 50 options. Decoupled design for maximum flexibility and extensibility.

## Architecture

```
LAYER 1: WHERE (Level & Context Engine)
  ├─ CPR calculation (Central Pivot Range)
  ├─ Historical level loading
  ├─ Proximity detection
  └─ Zone classification

      ↓

LAYER 2: WHEN (Signal & Momentum Engine)
  ├─ EMA alignment (5 > 12 > 20)
  ├─ VWAP alignment
  ├─ RSI momentum
  ├─ MACD histogram
  └─ Multi-timeframe validation

      ↓

LAYER 3: WHAT (Execution & Greeks Engine)
  ├─ Strike selection by Delta
  ├─ Greeks calculation
  ├─ Liquidity assessment
  ├─ Risk management
  └─ Position sizing
```

## Features

- **Decoupled Design:** Each layer independent and testable
- **Multi-timeframe Analysis:** 5-min, 15-min, and daily candles
- **Technical Confluence:** 5-point validation for strong signals
- **Greeks-based Strike Selection:** Delta, Gamma, Vega, Theta
- **Risk Management:** ATR-based stops, daily loss limits
- **Real Market Data:** Integrated with yfinance

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from orchestrator import TradingOrchestrator
import yfinance as yf

# Initialize
orchestrator = TradingOrchestrator(symbol='^NSEI', capital=15000)

# Fetch data
daily = yf.download('^NSEI', period='1y', interval='1d', progress=False)
intraday = yf.download('^NSEI', period='5d', interval='5m', progress=False)
trend = yf.download('^NSEI', period='5d', interval='15m', progress=False)

# Get complete signal
signal = orchestrator.generate_signal(daily, intraday, trend)

print(f"Signal: {signal.direction}")
print(f"Recommended Strike: {signal.strike}")
print(f"Greeks: Delta={signal.delta:.2f}, Theta={signal.theta:.2f}")
```

## Layer Details

### Layer 1: Level & Context Engine (`layers/level_engine.py`)

Detects where price is relative to support/resistance:

```
- CPR (Central Pivot Range) calculation
- Support/Resistance proximity detection
- Zone classification (above_cpr, inside_cpr, below_cpr)
- Historical level integration
```

### Layer 2: Signal & Momentum Engine (`layers/signal_engine.py`)

Validates 5 technical conditions:

```
1. EMA Alignment - Price & EMA trend alignment
2. VWAP Alignment - Price position relative to VWAP
3. RSI Momentum - Overbought/oversold detection
4. MACD Histogram - Momentum confirmation
5. MTF Alignment - Timeframe agreement (5m & 15m)
```

Signal Strength: 1/5 (weak) to 5/5 (strong)

### Layer 3: Execution & Greeks Engine (`layers/execution_engine.py`)

Strike selection and risk management:

```
- Black-Scholes Greeks calculation
- Strike selection by Delta (0.50-0.60 target)
- Liquidity scoring (volume + OI)
- Risk/reward validation
- Position sizing based on capital
```

## Data Sources

- **Primary:** yfinance (Yahoo Finance)
- **Candles:** 1-year daily + 5-day intraday (5min & 15min)
- **Greeks:** Black-Scholes model (calculated)
- **Option Chain:** Can integrate with Dhan API, broker APIs, or NSE web scraping

## File Structure

```
nifty_3layer_system/
├── orchestrator.py                 # Main coordinator
├── layers/
│   ├── level_engine.py            # Layer 1: WHERE
│   ├── signal_engine.py           # Layer 2: WHEN
│   └── execution_engine.py        # Layer 3: WHAT
├── indicators/
│   └── technical.py               # EMA, RSI, MACD, VWAP, ATR
├── config/
│   └── settings.py                # Configurable parameters
├── data/
│   └── levels_NIFTY.csv           # Historical levels
└── requirements.txt
```

## Configuration

Edit `config/settings.py` to customize:

```python
# Capital
CAPITAL = 15000

# Risk parameters
ATR_MULTIPLIER = 0.50
DAILY_LOSS_LIMIT = 5000

# Technical indicators
EMA_PERIODS = [5, 12, 20, 50, 200]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
```

## Testing

Run the complete system:
```bash
python orchestrator.py
```

## Development Notes

- ✅ All layers individually testable
- ✅ Real market data integration working
- ✅ Layer 1 & 2 validated with real NIFTY data
- ✅ Layer 3 tested with Black-Scholes Greeks
- ⏳ Requires option chain integration for live trading

## Next Steps

- [ ] Integrate real option chain (Dhan API or NSE scraper)
- [ ] Add backtesting framework
- [ ] Implement live trading mode
- [ ] Add portfolio management
- [ ] Create monitoring dashboard

## Version History

- **v0.1** - Initial development (Jan 2026)
- **v0.2** - Real data integration (Jan 2026)
- **v0.3** - Series bugs fixed (Jan 2026)

---

**Last Updated:** January 21, 2026  
**Maintainer:** Scalping Engine Team  
**Status:** Ready for backtesting | Beta for live trading
