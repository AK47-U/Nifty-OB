# Replit Deployment Configuration Fix

## Error: Invalid Run Command

### Current Problem
The "Run command" field has an invalid/corrupted bash command:
```
bash -c printf "%s\n\n%s" "$0" "$1" Please use the 𝙲𝚘𝚗𝚜𝚘𝚕𝚎𝚆𝚎𝚋𝙷𝚘𝚜𝚝...
```

**Status**: ❌ Invalid run command

---

## Solution

### Step 1: Clear the Run Command Field
1. Click on the **Run command** input field
2. Select all text (Ctrl+A)
3. Delete it completely

### Step 2: Enter Correct Run Command
Choose ONE of these based on your framework:

**Option A: Flask** (Recommended for simplicity)
```bash
python app.py
```

**Option B: FastAPI with Uvicorn**
```bash
python -m uvicorn app:app --host 0.0.0.0 --port 5000
```

**Option C: Flask with Gunicorn** (Production)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Step 3: Set Build Command (Optional)
In the **Build command** field, add:
```bash
pip install -r requirements.txt
```

---

## Complete Replit Configuration

### File: `.replit`
Create this file in your project root:

```yaml
run = "python app.py"
build = "pip install -r requirements.txt"

[languages.python]
pattern = "**/*.py"

[languages.python.languageServer]
start = "pylsp"

[env]
PYTHONUNBUFFERED = "1"
```

### File: `requirements.txt`
```
Flask==2.3.0
python-dotenv==1.0.0
requests==2.31.0
xgboost==2.0.0
pandas==2.0.0
numpy==1.24.0
yfinance==0.2.28
python-telegram-bot==20.0
APScheduler==3.10.0
Flask-CORS==4.0.0
```

### File: `app.py`
```python
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'NIFTY/SENSEX Trading Dashboard API',
        'version': '1.0.0'
    })

@app.route('/api/market-structure', methods=['GET'])
def market_structure():
    symbol = request.args.get('symbol', 'NIFTY')
    # TODO: Implement market structure calculation
    return jsonify({
        'symbol': symbol,
        'trend': 'BULLISH',
        'strength': 65.3,
        'resistance': 25850.50,
        'support': 25750.20
    })

@app.route('/api/trading-levels', methods=['GET'])
def trading_levels():
    symbol = request.args.get('symbol', 'NIFTY')
    # TODO: Implement trading levels generation
    return jsonify({
        'symbol': symbol,
        'direction': 'SELL',
        'confidence': 78.4,
        'entry': 156.50,
        'target': 176.50,
        'stoploss': 141.50
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
```

---

## Troubleshooting

### If still getting "Invalid run command"
1. Check there are NO special Unicode characters (the error shows fancy Unicode text)
2. Use plain ASCII only: `python app.py`
3. Save and refresh page
4. Click "Run" button again

### If "Module not found" error
1. Ensure `requirements.txt` exists in root directory
2. Run build command first
3. Wait for installation to complete

### If port already in use
1. Change port in command: `python app.py --port 8080`
2. Or use dynamic port from environment:
   ```python
   port = int(os.environ.get('PORT', 5000))
   app.run(host='0.0.0.0', port=port)
   ```

---

## Deployment Steps

1. ✅ Create `.replit` file with correct run command
2. ✅ Create `requirements.txt` with all dependencies
3. ✅ Create `app.py` with Flask/FastAPI starter code
4. ✅ Push to GitHub
5. ✅ Connect Replit to GitHub repo
6. ✅ Replit auto-deploys when you push

---

## Verification

After fixing, your Run command should show:
```
✅ Run: python app.py
```

Click **Run** button → App should start on `https://your-replit-url.repl.co`

