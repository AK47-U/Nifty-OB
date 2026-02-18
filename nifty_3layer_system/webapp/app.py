import sys
from pathlib import Path
from typing import Dict, Set, Any
from datetime import datetime, timedelta
import asyncio
import json
import numpy as np
import pandas as pd

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Allow importing project modules
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from integrations.dhan_client import DhanAPIClient, DhanConfig
from integrations.dhan_websocket import DhanWebSocket, ExchangeSegment, InstrumentType, TickData
from config.instrument_config import InstrumentManager
from ml_models.trading_levels_generator import TradingLevelsGenerator
from ml_models.level_tracker import LevelTracker


app = FastAPI(title="NIFTY/SENSEX Levels Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Initialize clients with error handling
try:
    dhan_client = DhanAPIClient()
    print("DhanAPIClient initialized successfully")
except Exception as e:
    print(f"ERROR: Failed to initialize DhanAPIClient: {e}")
    print(f"DhanAPIClient type: {type(dhan_client)}")
    raise

levels_generator = TradingLevelsGenerator()
level_tracker = LevelTracker(db_path="data/trading_metrics.db")
LEVEL_CACHE: Dict[str, Dict[str, Any]] = {}
ACTIVE_SIGNALS: Dict[str, Dict[str, Any]] = {}  # Track active signals for outcome checking
HOLD_WINDOW_SECONDS = 15 * 60  # 15-minute cadence from server start


def load_pending_signals_from_db():
    """Load pending signals (no outcome yet) from DB into ACTIVE_SIGNALS on startup"""
    import sqlite3
    try:
        conn = sqlite3.connect("data/trading_metrics.db")
        cursor = conn.cursor()
        # Get today's signals with no outcome
        cursor.execute("""
            SELECT id, symbol, direction, entry_price, target_price, sl_price, timestamp
            FROM level_signals 
            WHERE outcome IS NULL 
            AND date(timestamp) >= date('now', '-1 day')
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            sig_id, symbol, direction, entry, target, sl, timestamp = row
            symbol = symbol or "NIFTY"  # Default to NIFTY if null
            if symbol not in ACTIVE_SIGNALS:
                ACTIVE_SIGNALS[symbol] = {
                    "id": sig_id,
                    "direction": direction,
                    "entry": entry,
                    "target": target,
                    "stoploss": sl,
                    "logged_at": timestamp,
                }
                print(f"✓ Loaded pending signal: {symbol} {direction} @ {entry}")
        
        print(f"✓ Loaded {len(ACTIVE_SIGNALS)} pending signals from DB")
    except Exception as e:
        print(f"Error loading pending signals: {e}")


# Load pending signals on module load
load_pending_signals_from_db()


class StreamHub:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def register(self, symbol: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(symbol, set()).add(ws)

    def unregister(self, symbol: str, ws: WebSocket):
        if symbol in self.connections and ws in self.connections[symbol]:
            self.connections[symbol].remove(ws)

    async def broadcast(self, symbol: str, payload: Dict):
        if symbol not in self.connections:
            return
        dead = []
        for ws in self.connections[symbol]:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(symbol, ws)


stream_hub = StreamHub()


def _instrument_lookup():
    mapping = {}
    for key in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        inst = InstrumentManager.get_instrument(key)
        if inst:
            mapping[inst.security_id] = inst.symbol
    return mapping


SECURITY_ID_TO_SYMBOL = _instrument_lookup()


async def _start_dhan_stream():
    config = DhanConfig.from_env()
    ws = DhanWebSocket(access_token=config.access_token, client_id=config.client_id)

    def on_tick(tick: TickData):
        symbol = SECURITY_ID_TO_SYMBOL.get(str(tick.security_id))
        if not symbol:
            return
        payload = {
            "symbol": symbol,
            "ltp": tick.ltp,
            "timestamp": tick.timestamp.isoformat(),
        }
        asyncio.create_task(stream_hub.broadcast(symbol, payload))
        
        # Check if active signal hit target or SL
        active = ACTIVE_SIGNALS.get(symbol)
        if active:
            ltp = tick.ltp
            direction = active.get("direction")
            target = active.get("target")
            stoploss = active.get("stoploss")
            entry = active.get("entry")
            signal_id = active.get("id")
            
            # Debug logging
            print(f"[TICK] {symbol} LTP:{ltp:.2f} | Active: {direction} Entry:{entry:.2f} Tgt:{target:.2f} SL:{stoploss:.2f}")
            
            outcome = None
            pnl = 0
            if direction == "BUY":
                if ltp >= target:
                    outcome = "TARGET"
                    pnl = target - entry
                elif ltp <= stoploss:
                    outcome = "SL"
                    pnl = stoploss - entry
            elif direction == "SELL":
                if ltp <= target:
                    outcome = "TARGET"
                    pnl = entry - target
                elif ltp >= stoploss:
                    outcome = "SL"
                    pnl = entry - stoploss
            
            if outcome:
                # Update database with outcome using actual signal ID
                try:
                    import sqlite3
                    conn = sqlite3.connect("data/trading_metrics.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE level_signals 
                        SET outcome = ?, outcome_price = ?, outcome_time = ?, pnl_points = ?
                        WHERE id = ?
                    """, (outcome, ltp, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), pnl, signal_id))
                    rows_affected = cursor.rowcount
                    conn.commit()
                    conn.close()
                    print(f"✓ DB Updated ID:{signal_id} | {direction} @ {entry} -> {outcome} @ {ltp} | P&L: {pnl:.2f} | Rows: {rows_affected}")
                except Exception as e:
                    print(f"DB update error: {e}")
                
                # Broadcast outcome to connected clients
                outcome_payload = {
                    "type": "outcome",
                    "symbol": symbol,
                    "outcome": outcome,
                    "price": ltp,
                    "direction": direction,
                    "entry": entry,
                    "target": target,
                    "stoploss": stoploss,
                    "pnl": pnl,
                }
                asyncio.create_task(stream_hub.broadcast(symbol, outcome_payload))
                # Clear active signal
                del ACTIVE_SIGNALS[symbol]
                print(f"✓ {symbol} {direction} signal hit {outcome} @ {ltp}")

    ws.on_tick(on_tick)
    await ws.connect()

    for key in ["NIFTY", "SENSEX"]:
        inst = InstrumentManager.get_instrument(key)
        if not inst:
            continue
        await ws.subscribe_ticker(
            security_id=inst.security_id,
            exchange_segment=ExchangeSegment.IDX_I,
            instrument_type=InstrumentType.INDEX,
        )


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_start_dhan_stream())


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/stats")
def stats(days: int = Query(7, ge=1, le=90)):
    """Get win rate and performance statistics from tracked signals"""
    try:
        stats = level_tracker.get_statistics(days=days)
        sl_analysis = level_tracker.get_sl_analysis()
        
        # Add active signals info
        stats["active_signals"] = len(ACTIVE_SIGNALS)
        stats["active_symbols"] = list(ACTIVE_SIGNALS.keys())
        
        # Convert SL analysis to dict
        if not sl_analysis.empty:
            stats["sl_reasons"] = sl_analysis.to_dict(orient="records")
        else:
            stats["sl_reasons"] = []
            
        return stats
    except Exception as e:
        return {"error": str(e), "message": "No data available yet"}


@app.get("/api/stats/today")
def stats_today():
    """Get today's performance only"""
    try:
        stats = level_tracker.get_statistics(days=1)
        stats["active_signals"] = len(ACTIVE_SIGNALS)
        return stats
    except Exception as e:
        return {"error": str(e)}


def _normalize_time_index(df: pd.DataFrame, interval: int) -> pd.DataFrame:
    if isinstance(df.index, pd.DatetimeIndex):
        return df

    # Rebuild a datetime index if missing (cache path)
    end = datetime.utcnow()
    freq = f"{interval}min"
    df = df.copy()
    df.index = pd.date_range(end=end, periods=len(df), freq=freq)
    return df


def _fetch_candles(symbol: str, interval: int, days: int):
    instrument = InstrumentManager.get_instrument(symbol)
    if not instrument:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}")

    df = dhan_client.get_historical_candles(
        security_id=instrument.security_id,
        exchange_segment=instrument.exchange_segment,
        instrument=instrument.instrument_type,
        interval=interval,
        days=days,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No candle data returned")

    df = _normalize_time_index(df, interval)
    df = df.copy()
    df.reset_index(inplace=True)

    if "timestamp" not in df.columns:
        if "index" in df.columns:
            df["timestamp"] = pd.to_datetime(df["index"], errors="coerce")
        else:
            df["timestamp"] = pd.to_datetime(datetime.utcnow())

    # Convert to Unix epoch seconds properly
    df["time"] = df["timestamp"].apply(lambda x: int(x.timestamp()))

    candles = df[["time", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

    return candles, float(df["close"].iloc[-1])


def _is_levels_unchanged(new_levels: Dict[str, Any], prev_levels: Dict[str, Any]) -> bool:
    if not prev_levels:
        return False
    # Consider unchanged if direction same and entry/target/SL within small tolerance
    direction_same = new_levels.get("direction") == prev_levels.get("direction")

    def close_enough(a, b, pct=0.0005, points=0.2):
        if a is None or b is None:
            return False
        return abs(a - b) <= max(points, pct * max(abs(a), abs(b)))

    stable = (
        direction_same
        and close_enough(new_levels.get("entry"), prev_levels.get("entry"))
        and close_enough(new_levels.get("exit_target"), prev_levels.get("exit_target"))
        and close_enough(new_levels.get("stoploss"), prev_levels.get("stoploss"))
    )
    return stable


@app.get("/api/candles")
def candles(
    symbol: str = Query("NIFTY"),
    interval: int = Query(5, ge=1, le=60),
    days: int = Query(5, ge=1, le=90),
):
    data, last_price = _fetch_candles(symbol, interval, days)
    return {"symbol": symbol.upper(), "interval": interval, "last_price": last_price, "candles": data}


@app.get("/api/levels")
def levels(
    symbol: str = Query("NIFTY"),
    interval: int = Query(5, ge=1, le=60),
    days: int = Query(5, ge=1, le=90),
):
    instrument = InstrumentManager.get_instrument(symbol)
    if not instrument:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}")

    now = datetime.utcnow()
    cache_entry = LEVEL_CACHE.get(symbol.upper())
    if cache_entry:
        age = (now - cache_entry["generated_at"]).total_seconds()
        if age < HOLD_WINDOW_SECONDS:
            cached = cache_entry["data"].copy()
            cached["position_status"] = "HOLD"
            cached["hold_reason"] = f"Within 15-min window; next refresh in {int(HOLD_WINDOW_SECONDS - age)}s"
            return cached

    df = dhan_client.get_historical_candles(
        security_id=instrument.security_id,
        exchange_segment=instrument.exchange_segment,
        instrument=instrument.instrument_type,
        interval=interval,
        days=days,
    )

    df = _normalize_time_index(df, interval)

    if len(df) < 60:
        raise HTTPException(status_code=400, detail="Not enough candles for feature generation")

    result = levels_generator.calculate_levels(df)
    result["symbol"] = symbol.upper()
    result["generated_at_utc"] = now.isoformat()

    def _to_python(value: Any):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {k: _to_python(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_to_python(v) for v in value]
        return value
    result_py = _to_python(result)

    # Compare with previous levels to decide HOLD vs NEW
    prev_entry = LEVEL_CACHE.get(symbol.upper())
    if prev_entry and _is_levels_unchanged(result_py, prev_entry["data"]):
        result_py["position_status"] = "HOLD"
        result_py["hold_reason"] = "Structure unchanged; keeping previous position"
        # Do not update cache timestamp so we still respect the 15-min cadence
        return result_py

    result_py["position_status"] = "NEW"
    result_py["hold_reason"] = None
    LEVEL_CACHE[symbol.upper()] = {
        "data": result_py,
        "generated_at": now,
    }

    # Log new signal to tracker for outcome analysis
    try:
        signal_id = level_tracker.log_signal(result_py)
        if signal_id:
            # Store active signal for real-time outcome checking
            ACTIVE_SIGNALS[symbol.upper()] = {
                "id": signal_id,  # Actual DB ID
                "direction": result_py.get("direction"),
                "entry": result_py.get("entry"),
                "target": result_py.get("exit_target"),
                "stoploss": result_py.get("stoploss"),
                "logged_at": now,
            }
            print(f"✓ Active signal stored: {symbol.upper()} ID:{signal_id}")
    except Exception as e:
        print(f"Warning: Failed to log signal: {e}")

    return result_py


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "NIFTY").upper()
    await stream_hub.register(symbol, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        stream_hub.unregister(symbol, websocket)
