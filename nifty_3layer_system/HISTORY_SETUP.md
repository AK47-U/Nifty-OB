# Historical Analysis Setup

## Overview
The trading system now separates historical analysis from daily analysis to avoid loading unnecessary data on every run.

## Two Scripts

### 1. `history_analyzer.py` - Monthly Run
Fetches 365 days of data and caches key levels.

**Run this once per month:**
```powershell
C:\Users\akash\PycharmProjects\scalping_engine_complete_project\nifty_3layer_system\.venv\Scripts\python.exe c:\Users\akash\PycharmProjects\scalping_engine_complete_project\nifty_3layer_system\history_analyzer.py
```

**What it does:**
- Fetches 365 days of NIFTY daily candles
- Calculates 52-week high/low, median, quartiles
- Detects key support/resistance levels from last 90 days
- Computes volatility metrics and IV estimates
- Saves all to `data/historical_levels.json`

**Output:** `data/historical_levels.json` with:
- 52W high/low
- Median, Q1, Q3 prices
- Top 5 resistance/support levels
- Annualized volatility and IV estimates
- Timestamp of generation

### 2. `analyzer.py` - Daily Run (During Market Hours)
Uses cached levels and loads only 2 days of daily data (previous + current day).

**Run during market hours (09:15-15:30 IST):**
```powershell
C:\Users\akash\PycharmProjects\scalping_engine_complete_project\nifty_3layer_system\.venv\Scripts\python.exe c:\Users\akash\PycharmProjects\scalping_engine_complete_project\nifty_3layer_system\analyzer.py
```

**What it does:**
- Checks market hours
- Loads 2 days daily (for PDH/PDL/PDC)
- Loads 10 days of 5-min candles (for indicators)
- Loads 5 days of 15-min candles
- Reads historical levels from cache
- Compares current price against cached S/R levels
- Runs full 3-layer analysis

## Recommended Schedule

1. **First time setup:** Run `history_analyzer.py` to generate the cache
2. **Daily:** Run `analyzer.py` during market hours for live signals
3. **Monthly:** Re-run `history_analyzer.py` to refresh historical levels (1st of each month)

## Benefits

- **Performance:** Daily runs are faster (no 365-day fetch)
- **Reduced API load:** Less Dhan API usage per run
- **Consistency:** Historical levels remain stable throughout the month
- **Cleaner:** Separates strategic (monthly) from tactical (intraday) analysis
