# Option Chain Analysis - Current Implementation

## 1. **GREEKS CALCULATION** (Black-Scholes Model)

### ATM Strike Greeks for Call & Put:
- **Delta (Δ)**: Price sensitivity (-1 to +1)
  - Call Delta: +0.53 means if price moves ₹1, call value increases by ₹0.53
  - Put Delta: -0.47 means if price moves ₹1, put value decreases by ₹0.47
  - **Usage**: Directional exposure, hedge ratio

- **Gamma (Γ)**: Delta's sensitivity to price changes (acceleration)
  - Range: 0 to 1
  - **Usage**: Volatility risk, convexity of position

- **Theta (Θ)**: Time decay per day
  - Call Theta: -22.70/day (option loses ₹22.70 daily due to time decay)
  - Put Theta: -18.58/day
  - **Usage**: Income strategy, theta harvesting

- **Vega (V)**: IV sensitivity (per 1% IV change)
  - Vega: 13.84 means if IV rises by 1%, option value increases by ₹13.84
  - **Usage**: Volatility trading, IV prediction

- **Rho (ρ)**: Interest rate sensitivity (simplified to 0)

---

## 2. **IMPLIED VOLATILITY (IV) ANALYSIS**

### Current IV Rank:
```
IV Rank = ((Current IV - 52W Low) / (52W High - 52W Low)) × 100
```

### IV Status Categories:
- **LOW** (IV Rank 0-25%): Volatility cheap → Buy options, sell wide spreads
- **MEDIUM_LOW** (25-50%): Below average
- **MEDIUM_HIGH** (50-75%): Above average
- **HIGH** (75-100%): Volatility expensive → Sell options, buy tight spreads

### Example Output:
```
Current IV: 20.71%
IV Rank: 38% (MEDIUM_LOW)
52W Range: 12.00% - 35.00%
```

---

## 3. **PUT-CALL SKEW ANALYSIS**

### Skew Definition:
```
Put-Call Skew = OTM Put IV - OTM Call IV
```

### Direction Bias:
- **Positive Skew (>2%)**: BEARISH (puts more expensive)
  - Market expects downside protection
  - Traders hedging downside
  
- **Negative Skew (<-2%)**: BULLISH (calls more expensive)
  - Market expects upside moves
  - Traders buying calls
  
- **Neutral (-2% to +2%)**: NEUTRAL

### Individual Skews:
- **Call Skew**: OTM Call IV - ATM Call IV
- **Put Skew**: OTM Put IV - ATM Put IV

---

## 4. **MAX PAIN CALCULATION**

### Definition:
Strike price where maximum number of options expire worthless (max losses to traders)

### Formula:
```
Total Pain at Strike = |Current Price - Strike| × Call OI + |Strike - Current Price| × Put OI
Max Pain = Strike with minimum total pain
```

### Usage:
- If Max Pain is above current price → Price likely to move towards Max Pain (upside bias)
- If Max Pain is below current price → Price likely to move towards Max Pain (downside bias)

---

## 5. **OPTION CHAIN DATA EXTRACTED FROM DHAN API**

### Per Strike (Call & Put):
```
- Strike Price
- Last Traded Price (LTP)
- Delta, Gamma, Vega, Theta (from API greeks)
- Implied Volatility (IV)
- Open Interest (OI)
- Volume (traded today)
- Bid Price & Quantity (top bid)
- Ask Price & Quantity (top ask)
- Bid-Ask Spread
```

### Data Normalization:
- IV normalized from raw percentage (e.g., 5.228% → 0.05228)
- Greeks validated for consistency
- OI used for Put-Call Ratio (PCR) calculation

---

## 6. **CURRENT OUTPUT IN ANALYZER.PY**

```
💵 ATM STRIKE ANALYSIS: 25100

   Call (25100CE):
   ├─ Delta: +0.533 | Gamma: 0.0006
   ├─ Theta: -22.61/day | Vega: 13.83
   └─ IV: 20.71%

   Put (25100PE):
   ├─ Delta: -0.467 | Gamma: 0.0006
   ├─ Theta: -18.49/day | Vega: 13.83
   └─ IV: 20.71%

   IV Analysis:
   ├─ Current IV: 20.71%
   ├─ IV Rank: 38%
   └─ 52W Range: 12.00% - 35.00%
```

---

## 7. **WHAT'S NOT CURRENTLY ANALYZED**

### Missing Analyses:
1. **Put-Call Ratio (PCR)**: Total Put OI / Total Call OI
   - PCR > 1.2: Bearish (too many puts buying protection)
   - PCR < 0.8: Bullish (too many calls, aggressive buying)

2. **OI Analysis**:
   - Call OI buildup → Resistance formation
   - Put OI buildup → Support formation
   - OI Change vs Volume → Smart money vs retail detection

3. **Volatility Smile/Skew**:
   - Full skew curve across strikes
   - Pin risk zones

4. **Support/Resistance from OI Clusters**:
   - High OI strikes act as price magnets
   - Can predict breakout levels

5. **Greeks Greeks (2nd Order)**:
   - Gamma scalping profit potential
   - Vanna/Volga risk

6. **Volatility Surface**:
   - IV term structure (near-term vs far-term IV)
   - Calendar spread opportunity detection

7. **Liquidity Analysis**:
   - Bid-Ask Spread analysis per strike
   - Volume per strike for execution planning

8. **Unusual Options Activity**:
   - Large volume on specific strikes
   - Deviations from normal OI patterns
   - Institutional positioning

---

## 8. **TRADING SIGNALS FROM OPTIONS**

### Current Signals Available:
```
✓ IV Rank tells us: Are options cheap or expensive?
✓ ATM Greeks show: What's the directional bet, time decay cost?
✓ Put-Call Skew shows: What's the market's directional bias?
✓ Max Pain shows: Where is price likely to be pulled?
```

### Recommended Additions:
1. **PCR Analysis** → Market sentiment
2. **OI Buildup** → Resistance/Support strength
3. **IV Term Structure** → Volatility direction
4. **Spread Opportunities** → Risk-reward setups
5. **Options Volume Spikes** → Smart money direction

---

## 9. **FORMULA REFERENCE**

### Black-Scholes Components:
```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 - σ√T

Call Delta = N(d1)
Put Delta = N(d1) - 1
Gamma = φ(d1) / (S × σ × √T)
Theta = [-(S×φ(d1)×σ) / 2√T] + [-r×K×e^(-rT)×N(d2)]
Vega = S × φ(d1) × √T / 100
```

Where:
- S = Spot Price (25113)
- K = Strike Price (25100)
- T = Time to Expiry (4 days / 365)
- r = Risk-free Rate (6%)
- σ = Implied Volatility (0.207 or 20.7%)
- N() = Standard Normal CDF
- φ() = Standard Normal PDF
