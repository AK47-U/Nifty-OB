# ML Pipeline for 30-Min Direction Prediction

## Overview
Machine learning system using XGBoost to predict NIFTY direction 30 minutes ahead.

## Architecture

```
ml_models/
├── data_extractor.py      # Fetch 90 days from Dhan API + create labels
├── feature_engineer.py    # Generate 30 technical features
├── model_trainer.py       # Train XGBoost classifier
├── live_predictor.py      # Real-time predictions
└── train_pipeline.py      # Complete training pipeline

models/
├── training_data.csv              # Raw OHLCV + labels
├── featured_data.csv              # Processed features
├── xgboost_direction_model.pkl    # Trained model
├── xgboost_direction_model.json   # Performance metrics
└── feature_importance.csv         # Feature rankings
```

## Installation

```bash
# Install ML dependencies
pip install xgboost scikit-learn

# Or update all requirements
pip install -r requirements.txt
```

## Usage

### 1. Train Model (First Time / Daily Retraining)

```bash
# Complete pipeline: extract → engineer → train
python -m ml_models.train_pipeline

# Or run steps individually:
python -m ml_models.data_extractor      # Step 1: Get data
python -m ml_models.feature_engineer    # Step 2: Create features
python -m ml_models.model_trainer       # Step 3: Train model
```

**Output:**
- Model accuracy (expected 55-65%)
- Top 15 important features
- Confusion matrix
- Saved model in `models/`

### 2. Live Predictions

```bash
# Test predictions on recent data
python -m ml_models.live_predictor
```

**Output:**
```
Prediction: BUY | Confidence: 67.5% | Action: BUY
Prediction: SELL | Confidence: 52.3% | Action: WAIT  # Low confidence
```

### 3. Integration with analyzer.py (Coming Soon)

```python
from ml_models.live_predictor import LivePredictor

# In analyzer.py
predictor = LivePredictor()
ml_prediction = predictor.predict_direction(df5m)

if ml_prediction['confidence'] > 60:
    final_decision = ml_prediction['direction']  # BUY/SELL
```

## Features (30 Total)

### Technical Indicators
- RSI (14, 5, 21 periods)
- MACD (line, signal, histogram)
- Bollinger Bands (width)
- ATR (volatility percentage)

### Price Features
- Price position in range
- Price change (1, 5, 10 candles)
- Rate of change (ROC)
- Distance from EMAs (5, 20, 50)
- EMA alignment

### Volume Features
- Volume ratio vs average
- Volume change
- Price-volume correlation

### Time Features
- Hour of day
- Minute
- Day of week
- Market phase (open/mid/close)

### Volatility Features
- Rolling volatility (5, 20 periods)
- Volatility ratio

## Model Performance

**Target Metrics:**
- Accuracy: 55-65% (realistic for 30-min predictions)
- Precision: 60%+ (avoid false signals)
- Confidence threshold: 60% (only trade high-confidence signals)

**Retraining:**
- Frequency: Daily (3:45 PM after market close)
- Data: Rolling 90-day window
- Keeps model adapted to current market conditions

## Prediction Output

```python
{
    'direction': 'BUY',           # BUY or SELL
    'confidence': 67.5,            # 0-100%
    'up_probability': 67.5,        # Probability of UP move
    'down_probability': 32.5,      # Probability of DOWN move
    'timestamp': '2026-02-02 10:30:00',
    'action': 'BUY'                # BUY/SELL/WAIT (based on confidence)
}
```

## Next Steps

1. ✅ Train initial model: `python -m ml_models.train_pipeline`
2. ✅ Test predictions: `python -m ml_models.live_predictor`
3. ⏳ Integrate with analyzer.py
4. ⏳ Setup daily retraining at 3:45 PM
