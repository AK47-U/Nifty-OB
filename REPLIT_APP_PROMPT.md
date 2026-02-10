# Replit App Prompt: NIFTY/SENSEX Trading Dashboard

## PROJECT OBJECTIVE
Build a real-time web application that generates intraday trading levels and market analysis reports for NIFTY and SENSEX using ML predictions and technical analysis.

## CORE REQUIREMENTS

### 1. TECH STACK
- **Backend**: Python Flask/FastAPI + SQLite
- **Frontend**: React + Tailwind CSS (modern, dark theme)
- **Real-time Data**: WebSocket for market updates
- **ML Model**: XGBoost (78.4% accuracy for profitable 5+ point moves)
- **APIs**: Dhan API for NIFTY data, Yahoo Finance API for SENSEX

### 2. MAIN FEATURES

#### Feature 1: Market Analysis Report Button
**Functionality:**
- Single click generates comprehensive market report
- Shows current market structure (trending/range-bound)
- Displays trend direction (UP/DOWN/NEUTRAL) with strength %
- Calculates support/resistance levels (from last 20 candles)
- Shows CPR (Central Pivot Range) zones
- Market bias (bullish/bearish/neutral based on EMAs)
- Volatility regime (high/medium/low with Parkinson volatility)
- RSI extremes (oversold < 30 / overbought > 70)

**Data to Display:**
```
┌─ MARKET STRUCTURE ─────────────────┐
│ Status: TRENDING UP                │
│ Strength: 65.3%                    │
│ Trend: 15-min EMA(9) above EMA(21) │
├─ SUPPORT/RESISTANCE ──────────────┤
│ Resistance: 25,850.50              │
│ CPR TC (Top Central): 25,825.30    │
│ CPR Pivot: 25,800.10               │
│ CPR BC (Bottom Central): 25,774.90 │
│ Support: 25,750.20                 │
├─ VOLATILITY & MOMENTUM ───────────┤
│ Volatility: MEDIUM (ATR: 34.5)     │
│ RSI(14): 58.2 (Neutral)            │
│ MACD: Bullish (above signal line)  │
├─ MARKET BIAS ─────────────────────┤
│ Short-term: BULLISH ✅             │
│ Long-term: BULLISH ✅              │
│ Recommendation: SUPPORT DIPS       │
└────────────────────────────────────┘
```

#### Feature 2: Trading Levels Display
**Functionality:**
- Shows ML-generated trading levels
- Entry, Target, Stop Loss, Risk:Reward ratio
- Real option premiums (from Dhan API)
- Profit/Loss per contract
- Capital required

**Data to Display:**
```
┌─ ML TRADING SIGNAL ────────────────┐
│ Direction: SELL 🔴                 │
│ Confidence: 78.4%                  │
│ Strike: 25,850 PE                  │
├─ PREMIUM LEVELS ──────────────────┤
│ Entry: ₹156.50                     │
│ Target: ₹176.50 (+₹20.00)         │
│ Stop Loss: ₹141.50 (-₹15.00)       │
├─ P&L (65 contracts) ──────────────┤
│ Profit Potential: +₹1,300          │
│ Max Loss: -₹975                    │
│ Risk:Reward: 1:1.33                │
│ Capital Required: ₹10,172.50       │
├─ FILTERS STATUS ──────────────────┤
│ ✅ Confidence Pass (78.4% > 60%)   │
│ ✅ RR Ratio Pass (1:1.33 > 1:1)    │
│ ✅ Trend Aligned (SELL vs DOWN)    │
│ ✅ Entry Quality (GOOD)            │
│ ✅ Position Size (13pt SL < 13.8)  │
└────────────────────────────────────┘
```

#### Feature 3: NIFTY vs SENSEX Toggle Buttons
**Functionality:**
- Two separate analysis reports
- Independent levels for each index
- Side-by-side comparison option

### 3. UI/UX ARCHITECTURE

```
Header
├── Logo | "NIFTY/SENSEX Trading Dashboard"
├── Live Price Display (NIFTY | SENSEX)
└── Last Updated: HH:MM:SS IST

Main Panel
├── Index Selector (NIFTY | SENSEX)
├── ┌─ Analysis Report Section ──────┐
│  │ [📊 Generate Market Report] Btn │
│  │ (Updates every 15 min or on click)
│  └────────────────────────────────┘
├── ┌─ Market Structure Card ────────┐
│  │ Trend | Support/Resistance     │
│  │ CPR Zones | Volatility         │
│  └────────────────────────────────┘
├── ┌─ Trading Levels Card ─────────┐
│  │ ML Signal with all metrics     │
│  │ [✅ Copy Levels] [📋 Export]   │
│  └────────────────────────────────┘
└── ┌─ Historical Signals Table ────┐
   │ Time | Symbol | Direction | ✅/❌ │
   └────────────────────────────────┘

Footer
├── Last 24h Stats (Win Rate, Accuracy)
└── Settings | About
```

### 4. DATA FLOW

```
Backend Process (every 15 minutes):
1. Fetch 5 days of 5-min candles from Dhan API
2. Calculate 74 ML features:
   - Technical: RSI, MACD, Bollinger, ATR, EMA, VWAP
   - CPR: TC, BC, Pivot, Width
   - Microstructure: Order flow, tick direction
   - Volatility: Garman-Klass, Parkinson, Vol-of-Vol
   - Support/Resistance: Distance, touches
   - Gap/Open: Day open tracking
3. Run XGBoost model prediction
4. Apply 5 filters:
   - Trend alignment
   - Entry quality (S/R proximity)
   - Position sizing (SL validation)
   - Failure detection
   - Parameter learning
5. Generate trading levels
6. Fetch real option premiums from Dhan
7. Store in SQLite database
8. Send via WebSocket to frontend (real-time)
```

### 5. API ENDPOINTS NEEDED

```
GET /api/market-structure?symbol=NIFTY
→ Returns: trend, strength, SR levels, CPR, volatility, bias

GET /api/trading-levels?symbol=NIFTY
→ Returns: entry, target, SL, confidence, filters_status, option_premium

GET /api/levels-history?symbol=NIFTY&days=7
→ Returns: past signals with outcomes (WIN/LOSS)

GET /api/sensex-market-structure
→ Same as NIFTY but for SENSEX (from Yahoo Finance)

GET /api/sensex-trading-levels
→ Same logic adapted for SENSEX

WebSocket /ws/live-updates?symbol=NIFTY
→ Real-time price, trend, level updates
```

### 6. DATABASE SCHEMA

```sql
-- Signals Table
CREATE TABLE signals (
    id PRIMARY KEY,
    timestamp DATETIME,
    symbol TEXT (NIFTY/SENSEX),
    direction TEXT (BUY/SELL),
    confidence FLOAT,
    entry FLOAT,
    target FLOAT,
    stoploss FLOAT,
    strike TEXT,
    premium_entry FLOAT,
    premium_target FLOAT,
    premium_sl FLOAT,
    rr_ratio FLOAT,
    status TEXT (PENDING/EXECUTED/CANCELLED),
    outcome TEXT (WIN/LOSS/OPEN)
);

-- Market Structure Table
CREATE TABLE market_structure (
    id PRIMARY KEY,
    timestamp DATETIME,
    symbol TEXT,
    trend TEXT,
    trend_strength FLOAT,
    resistance FLOAT,
    support FLOAT,
    cpr_tc FLOAT,
    cpr_pivot FLOAT,
    cpr_bc FLOAT,
    volatility_regime TEXT,
    atr FLOAT,
    rsi FLOAT,
    bias TEXT
);
```

### 7. FEATURE BREAKDOWN FOR NIFTY

**Data Source**: Dhan API (5-min candles)
- Fetch: Last 5 days = 376 candles (5×78 trading min/day)
- Calculate: 74 features in real-time
- Model: XGBoost (trained on 90 days, 78.4% accuracy)
- Filtering: 5 adaptive filters applied sequentially
- Output: Trading levels with option premium

### 8. FEATURE BREAKDOWN FOR SENSEX

**Data Source**: Yahoo Finance API
- Symbol: ^BSESN
- Fetch: Last 5 days = 376 candles (5-min)
- Calculate: Same 74 features (adapted for SENSEX)
- Model: Use same XGBoost (trained generic, not symbol-specific)
- Note: Sensex uses simplified option strike mapping
- Output: Trading levels with estimated premiums

### 9. ML MODEL INTEGRATION

```python
# Input Data:
- OHLCV candles (5-min, last 5 days)
- 74 features (technical, CPR, microstructure, volatility)

# Model Output:
- Prediction: BUY or SELL
- Confidence: 0-100%
- Probability UP/DOWN: for risk calculation

# Filters Applied (in order):
1. Position Sizing (13pt SL max) → Pass/Block
2. Confidence Threshold (60% min) → Pass/Block
3. Trend Alignment (with 15-min EMA) → Pass/Warning
4. Entry Quality (S/R proximity) → Pass/Fair/Poor
5. Failure Detection (3+ SL hits pause trading) → Pass/Block

# Output:
- Trading Level: Entry, Target, SL, Risk:Reward
- Option Strike: ATM or nearest liquid strike
- Premium Levels: Calculated from live Dhan data
- P&L: Per contract and total (65 lot)
```

### 10. UI INTERACTIONS

**Button 1: "📊 Generate Market Report"**
- Click → Fetch latest data → Calculate structure → Display report
- Auto-refresh every 15 minutes during market hours
- Loading spinner while fetching

**Button 2: "NIFTY" | "SENSEX" Toggle**
- Switch between NIFTY and SENSEX analysis
- Save selected in localStorage
- Update all cards immediately

**Copy Levels**: Copy trading setup to clipboard
**Export**: Download report as PDF/CSV
**Refresh**: Manual update button

### 11. ERROR HANDLING

- No market data: Show "Market Closed" message
- API failure: Retry with exponential backoff
- Model prediction failure: Show "Analysis unavailable"
- Invalid filters: Show which filter blocked trade

### 12. PERFORMANCE REQUIREMENTS

- Report generation: < 3 seconds
- Page load: < 2 seconds
- Real-time updates: < 500ms latency
- Concurrent users: Support 10+

### 13. RESPONSIVENESS

- Desktop: Full layout
- Tablet: 2-column layout
- Mobile: Stack vertically, hide non-critical info

### 14. AUTHENTICATION (Optional)

- If needed: Simple login (email/password)
- Store API credentials securely in backend
- Session management with JWT

### 15. DEPLOYMENT

- Replit: Auto-deploy from GitHub
- Database: SQLite (local) or PostgreSQL (if scaling)
- Scheduler: APScheduler for 15-min updates
- Background jobs: Celery for async report generation

## IMPLEMENTATION PRIORITY

1. Backend: Market structure calculation (easy)
2. Frontend: Dashboard layout (easy)
3. ML integration: Trading levels generation (medium)
4. Real-time updates: WebSocket (medium)
5. SENSEX support: Adapt for different index (easy)
6. Advanced features: Export, comparison (low priority)

## SUCCESS CRITERIA

✅ Market report generated in < 3 seconds
✅ Trading levels show all 5 filters with pass/fail status
✅ NIFTY and SENSEX work independently
✅ Real-time updates every 15 minutes
✅ Mobile-responsive design
✅ No data inconsistencies

---

**Note**: This prompt is ready for Replit's AI assistant or direct implementation. All technical details, data structures, and integration points are specified.
