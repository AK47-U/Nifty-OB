# NIFTY Options Trading System with ML

**78.4% accuracy ML model for profitable NIFTY options scalping**

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Dhan API credentials in .env
cp .env.example .env
# Edit .env with your Dhan API credentials

# 3. Run the system
python levels_monitor_adaptive.py
```

## System Overview

### What It Does
- Predicts profitable 5+ point moves in NIFTY (15-min horizon)
- Generates option trading levels with entry, target, and stop-loss
- Applies 5 adaptive filters to prevent bad trades
- Sends Telegram alerts with complete trade setup
- Auto-adjusts parameters based on past failures

### Key Features
- **78.4% Accuracy** - Predicts profitable moves (not just direction)
- **74 ML Features** - Technical indicators, CPR, VWAP, microstructure, volatility regime
- **Capital Protection** - Max Rs.900 daily loss, 13-point SL limit
- **5 Adaptive Filters**:
  1. Trend Alignment (15-min EMA)
  2. Entry Quality (Support/Resistance proximity)
  3. Failure Detection (learns from past SL hits)
  4. Parameter Learning (auto-adjusts confidence thresholds)
  5. Position Sizing (enforces risk limits)

### Architecture

```
levels_monitor_adaptive.py (Main Loop)
├── ml_models/
│   ├── trading_levels_generator.py (Converts ML → Trading levels)
│   ├── live_predictor.py (XGBoost model inference)
│   ├── feature_engineer.py (74 features calculation)
│   ├── data_extractor.py (Fetches data from Dhan API)
│   └── real_option_fetcher.py (Gets real option premiums)
├── intelligence/
│   ├── trend_analyzer.py (15-min trend filter)
│   ├── entry_quality_filter.py (S/R proximity check)
│   ├── failure_analyzer.py (Learns from past SL hits)
│   ├── parameter_learner.py (Auto-adjusts thresholds)
│   └── position_sizer.py (Enforces capital limits)
├── integrations/
│   └── dhan_client.py (Dhan API wrapper)
└── config/
    └── settings.py (System configuration)
```

## Model Details

- **Type**: XGBoost Classifier
- **Target**: Profitable 5+ point moves (YES/NO)
- **Training**: 4,700 samples (90 days of 5-min NIFTY data)
- **Features**: 74 total
  - Technical: RSI, MACD, Bollinger Bands, ATR, EMA, VWAP
  - CPR: Central Pivot Range (TC, BC, Pivot, Width)
  - Microstructure: Order flow, tick direction, spread
  - Volatility: Garman-Klass, Parkinson, Vol-of-Vol
  - Support/Resistance: Distance, touches, proximity
  - Gap/Open: Day open tracking, gap detection
  - Options-derived: PCR, OI skew, IV skew

## Risk Management

- **Total Capital**: Rs.15,000
- **Daily Loss Limit**: Rs.900 (6% of capital)
- **Max Stop Loss**: 13 points (Rs.845 per trade)
- **Max Trades/Day**: 2
- **Lot Size**: 65 (NIFTY options)
- **Risk:Reward**: 1:1.3 minimum

## Configuration

Edit `config/settings.py` or `.env`:

```python
# Dhan API
DHAN_CLIENT_ID = "your_client_id"
DHAN_ACCESS_TOKEN = "your_access_token"

# Telegram
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# Risk Management
MAX_DAILY_LOSS = 900
MAX_TRADES_PER_DAY = 2
LOT_SIZE = 65
```

## Output Example

```
📡 ITERATION #1 - 2026-02-07 09:30:00 IST
🔄 Fetching 5 days of 5-min NIFTY candles...
✓ Got 376 candles

🧠 Running ML prediction (78.4% accuracy - profitable moves)...
✓ Prediction: SELL @ 72.3% confidence | Action: SELL

💰 Checking position sizing & capital constraints...
   ✅ CAN TRADE: 2 slots left, ₹900 loss available
   ✅ Position valid: 13.0 pt SL = ₹845 loss

✅ ALL FILTERS PASSED - SIGNAL READY TO TRADE

🎯 STRIKE & DIRECTION:
   Strike:                 25650 PE
   Direction:              SELL

💰 PREMIUM LEVELS:
   📥 ENTRY PREMIUM:       ₹112.90
   ✅ TARGET PREMIUM:      ₹132.90 (+₹1,300 profit)
   🛑 STOP LOSS PREMIUM:   ₹97.90 (-₹975 loss)
   
💼 P&L CALCULATION (Lot = 65):
   Capital Required:       ₹7,338.50
   Risk:Reward Ratio:      1:1.33
```

## Files Structure

### Core Files
- `levels_monitor_adaptive.py` - Main monitoring loop
- `dhan_api_client.py` - Dhan API integration
- `telegram_notifier.py` - Telegram alerts
- `requirements.txt` - Python dependencies

### Directories
- `ml_models/` - ML model, feature engineering, data extraction
- `intelligence/` - 5 adaptive filters
- `integrations/` - External API integrations
- `config/` - System configuration
- `data/` - Database and historical data
- `models/` - Trained XGBoost model

## Requirements

- Python 3.10+
- Dhan API account
- Telegram bot (for alerts)
- 90 days of historical data (auto-fetched)

## Training

Model is pre-trained. To retrain:

```bash
python ml_models/train_pipeline.py
```

This will:
1. Fetch 90 days of 5-min NIFTY data from Dhan
2. Generate 74 features
3. Train XGBoost on profitable 5+ point moves
4. Save model to `models/xgboost_direction_model.pkl`

Training takes ~2-3 minutes.

## License

MIT

## Disclaimer

This is for educational purposes only. Trading involves risk. Past performance does not guarantee future results.
