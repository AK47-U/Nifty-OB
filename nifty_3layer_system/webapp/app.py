import sys
from pathlib import Path
from typing import Dict, Set, Any
from datetime import datetime
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


dhan_client = DhanAPIClient()
levels_generator = TradingLevelsGenerator()


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

    epoch_values = pd.to_datetime(df["timestamp"]).astype("int64")
    if epoch_values.max() > 10**12:
        epoch_values = epoch_values // 10**9
    df["time"] = epoch_values.astype(int)

    candles = df[["time", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

    return candles, float(df["close"].iloc[-1])


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

    def _to_python(value: Any):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {k: _to_python(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_to_python(v) for v in value]
        return value

    return _to_python(result)


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    symbol = websocket.query_params.get("symbol", "NIFTY").upper()
    await stream_hub.register(symbol, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        stream_hub.unregister(symbol, websocket)
