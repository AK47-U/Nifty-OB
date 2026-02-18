"""
DHAN WEBSOCKET CLIENT
Real-time market feed for LTP, Option Chain updates, and Market Depth

WebSocket URL: wss://api-feed.dhan.co?version=2
Protocol: Dhan Feed API v2
"""

import json
import asyncio
import websockets
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from enum import Enum


class InstrumentType(Enum):
    """Dhan instrument types for WebSocket"""
    INDEX = 0
    EQUITY = 1
    FUTIDX = 2
    FUTSTK = 3
    OPTIDX = 4
    OPTSTK = 5


class ExchangeSegment(Enum):
    """Exchange segments - Dhan API v2 (matches dhanhq library)"""
    IDX_I = 0       # Index segment
    NSE_EQ = 1      # NSE Cash
    NSE_FNO = 2     # NSE F&O
    NSE_CURRENCY = 3
    BSE_EQ = 4      # BSE Cash
    MCX_COMM = 5    # MCX Commodity
    BSE_CURRENCY = 7
    BSE_FNO = 8


@dataclass
class TickData:
    """Real-time tick data"""
    security_id: str
    exchange_segment: int
    ltp: float
    ltt: Optional[datetime]  # Last traded time
    ltq: Optional[int]  # Last traded quantity
    volume: Optional[int]
    bid: Optional[float]
    ask: Optional[float]
    oi: Optional[int]  # Open Interest
    oi_change: Optional[int]
    timestamp: datetime


@dataclass
class MarketDepth:
    """20-level market depth"""
    security_id: str
    exchange_segment: int
    bids: List[Dict[str, float]]  # [{'price': x, 'qty': y, 'orders': z}, ...]
    asks: List[Dict[str, float]]
    timestamp: datetime


class DhanWebSocket:
    """
    Dhan WebSocket client for real-time market data
    
    Subscription Types:
    - Ticker: Basic LTP, Volume, OI
    - Quote: LTP + Best Bid/Ask + OHLC
    - Depth: 20-level market depth
    """
    
    def __init__(self, access_token: str, client_id: str):
        """
        Args:
            access_token: Dhan JWT token
            client_id: Dhan client ID
        """
        self.access_token = access_token
        self.client_id = client_id
        # Build URL with query parameters (auth in URL, not headers)
        self.ws_url = f"wss://api-feed.dhan.co?version=2&token={access_token}&clientId={client_id}&authType=2"
        
        self.websocket = None
        self.is_connected = False
        self.subscriptions = {}
        
        # Callbacks
        self.on_tick_callback: Optional[Callable[[TickData], None]] = None
        self.on_depth_callback: Optional[Callable[[MarketDepth], None]] = None
        self.on_error_callback: Optional[Callable[[str], None]] = None
        
        logger.info("Dhan WebSocket client initialized")
    
    async def connect(self):
        """Establish WebSocket connection with retry logic"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to Dhan WebSocket Feed (attempt {retry_count + 1}/{max_retries})...")
                
                connect_kwargs = {
                    "ping_interval": 30,
                    "ping_timeout": 10,
                }

                self.websocket = await websockets.connect(
                    self.ws_url,
                    **connect_kwargs
                )
                
                self.is_connected = True
                logger.success("WebSocket connected successfully ✓")
                
                # Start message receiver
                asyncio.create_task(self._receive_messages())
                return  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                logger.error(f"WebSocket connection failed (attempt {retry_count}/{max_retries}): {e}")
                self.is_connected = False
                
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8, 16 seconds
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Failed to connect after maximum retries. Check your token validity.")
                    if self.on_error_callback:
                        self.on_error_callback(str(e))
    
    async def disconnect(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("WebSocket disconnected")
    
    async def subscribe_ticker(
        self,
        security_id: str,
        exchange_segment: ExchangeSegment,
        instrument_type: InstrumentType
    ):
        """
        Subscribe to ticker (LTP, Volume, OI)
        
        Args:
            security_id: Security identifier (e.g., '13' for NIFTY)
            exchange_segment: Exchange segment
            instrument_type: Instrument type
        """
        if not self.is_connected:
            logger.error("WebSocket not connected")
            return
        
        subscription_code = 15  # Ticker data
        
        # Map exchange segment to string format expected by Dhan v2 API
        exchange_map = {
            0: "IDX_I",      # Index
            1: "NSE_EQ",     # NSE Cash
            2: "NSE_FNO",    # NSE F&O
            3: "NSE_CURRENCY",
            4: "BSE_EQ",
            5: "MCX_COMM",
            7: "BSE_CURRENCY",
            8: "BSE_FNO"
        }
        actual_exchange = exchange_map.get(exchange_segment.value, "IDX_I")
        
        request = {
            "RequestCode": subscription_code,
            "InstrumentCount": 1,
            "InstrumentList": [{
                "ExchangeSegment": actual_exchange,
                "SecurityId": str(security_id)
            }]
        }
        
        try:
            await self.websocket.send(json.dumps(request))
            
            key = f"{exchange_segment.value}:{security_id}"
            self.subscriptions[key] = "ticker"
            
            logger.info(f"Subscribed to ticker: {security_id} ({exchange_segment.name})")
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
    
    async def subscribe_quote(
        self,
        security_id: str,
        exchange_segment: ExchangeSegment,
        instrument_type: InstrumentType
    ):
        """
        Subscribe to quote (LTP + Best Bid/Ask + OHLC)
        
        Args:
            security_id: Security identifier
            exchange_segment: Exchange segment
            instrument_type: Instrument type
        """
        if not self.is_connected:
            logger.error("WebSocket not connected")
            return
        
        subscription_code = 17  # Quote data
        
        request = {
            "RequestCode": subscription_code,
            "InstrumentCount": 1,
            "InstrumentList": [{
                "ExchangeSegment": exchange_segment.value,
                "SecurityId": security_id,
                "InstrumentType": instrument_type.value
            }]
        }
        
        try:
            await self.websocket.send(json.dumps(request))
            
            key = f"{exchange_segment.value}:{security_id}"
            self.subscriptions[key] = "quote"
            
            logger.info(f"Subscribed to quote: {security_id} ({exchange_segment.name})")
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
    
    async def subscribe_depth(
        self,
        security_id: str,
        exchange_segment: ExchangeSegment,
        instrument_type: InstrumentType
    ):
        """
        Subscribe to 20-level market depth
        
        Args:
            security_id: Security identifier
            exchange_segment: Exchange segment
            instrument_type: Instrument type
        """
        if not self.is_connected:
            logger.error("WebSocket not connected")
            return
        
        subscription_code = 19  # Market depth
        
        request = {
            "RequestCode": subscription_code,
            "InstrumentCount": 1,
            "InstrumentList": [{
                "ExchangeSegment": exchange_segment.value,
                "SecurityId": security_id,
                "InstrumentType": instrument_type.value
            }]
        }
        
        try:
            await self.websocket.send(json.dumps(request))
            
            key = f"{exchange_segment.value}:{security_id}"
            self.subscriptions[key] = "depth"
            
            logger.info(f"Subscribed to depth: {security_id} ({exchange_segment.name})")
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
    
    async def unsubscribe(
        self,
        security_id: str,
        exchange_segment: ExchangeSegment,
        instrument_type: InstrumentType,
        subscription_type: str = "ticker"
    ):
        """
        Unsubscribe from instrument
        
        Args:
            security_id: Security identifier
            exchange_segment: Exchange segment
            instrument_type: Instrument type
            subscription_type: 'ticker', 'quote', or 'depth'
        """
        if not self.is_connected:
            return
        
        code_map = {
            "ticker": 16,
            "quote": 18,
            "depth": 20
        }
        
        subscription_code = code_map.get(subscription_type, 16)
        
        request = {
            "RequestCode": subscription_code,
            "InstrumentCount": 1,
            "InstrumentList": [{
                "ExchangeSegment": exchange_segment.value,
                "SecurityId": security_id,
                "InstrumentType": instrument_type.value
            }]
        }
        
        try:
            await self.websocket.send(json.dumps(request))
            
            key = f"{exchange_segment.value}:{security_id}"
            if key in self.subscriptions:
                del self.subscriptions[key]
            
            logger.info(f"Unsubscribed from {subscription_type}: {security_id}")
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
    
    async def _receive_messages(self):
        """Receive and process WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    # Check if binary data
                    if isinstance(message, bytes):
                        await self._process_binary_message(message)
                    else:
                        # JSON message
                        data = json.loads(message)
                        await self._process_message(data)
                except json.JSONDecodeError:
                    await self._process_binary_message(message.encode() if isinstance(message, str) else message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e.rcvd_then_sent}")
            self.is_connected = False
            logger.error(f"Close code: {e.rcvd.code if e.rcvd else 'None'}, reason: {e.rcvd.reason if e.rcvd else 'No reason'}")
            logger.info("This usually means: invalid token, expired token, or authentication failed")
        except Exception as e:
            logger.error(f"Error in message receiver: {e}")
            self.is_connected = False
            if self.on_error_callback:
                self.on_error_callback(str(e))
    
    async def _process_message(self, data: Dict):
        """Process JSON message from WebSocket"""
        try:
            # Ticker/Quote data
            if 'type' in data and data['type'] == 'Ticker':
                tick = self._parse_tick_data(data)
                if self.on_tick_callback:
                    self.on_tick_callback(tick)
            
            elif 'type' in data and data['type'] == 'Quote':
                tick = self._parse_quote_data(data)
                if self.on_tick_callback:
                    self.on_tick_callback(tick)
            
            # Market depth data
            elif 'type' in data and data['type'] == 'MarketDepth':
                depth = self._parse_depth_data(data)
                if self.on_depth_callback:
                    self.on_depth_callback(depth)
            
            else:
                logger.debug(f"Unknown message type: {data}")
        
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
    
    async def _process_binary_message(self, data: bytes):
        """Process binary message from Dhan WebSocket (v2 ticker format)"""
        if len(data) < 16:
            return
            
        try:
            import struct
            
            # First byte indicates message type
            msg_type = data[0]
            
            if msg_type == 2:  # Ticker data
                # Format: <BHBIfI = type(1), ?(2), exchange_seg(1), security_id(4), ltp(4), ?(4) = 16 bytes
                unpacked = struct.unpack('<BHBIfI', data[0:16])
                exchange_segment = unpacked[2]
                security_id = unpacked[3]
                ltp = unpacked[4]
                
                tick = TickData(
                    security_id=str(security_id),
                    exchange_segment=exchange_segment,
                    ltp=ltp,
                    ltt=None,
                    ltq=None,
                    volume=None,
                    bid=None,
                    ask=None,
                    oi=None,
                    oi_change=None,
                    timestamp=datetime.now()
                )
                
                if self.on_tick_callback:
                    self.on_tick_callback(tick)
            
            elif msg_type == 4:  # Quote data
                # More fields available in quote
                pass
            
            elif msg_type == 50:  # Server disconnection
                logger.warning("Server disconnection message received")
                
        except Exception as e:
            print(f"[WS BINARY ERROR] {e}")
    
    def _parse_tick_data(self, data: Dict) -> TickData:
        """Parse ticker data"""
        return TickData(
            security_id=data.get('security_id', ''),
            exchange_segment=data.get('exchange_segment', 0),
            ltp=float(data.get('LTP', 0.0)),
            ltt=datetime.fromtimestamp(data.get('LTT', 0)) if 'LTT' in data else None,
            ltq=data.get('LTQ'),
            volume=data.get('volume'),
            bid=data.get('bestBidPrice'),
            ask=data.get('bestAskPrice'),
            oi=data.get('openInterest'),
            oi_change=data.get('OIChange'),
            timestamp=datetime.now()
        )
    
    def _parse_quote_data(self, data: Dict) -> TickData:
        """Parse quote data"""
        return TickData(
            security_id=data.get('security_id', ''),
            exchange_segment=data.get('exchange_segment', 0),
            ltp=float(data.get('LTP', 0.0)),
            ltt=datetime.fromtimestamp(data.get('LTT', 0)) if 'LTT' in data else None,
            ltq=data.get('LTQ'),
            volume=data.get('volume'),
            bid=float(data.get('bestBidPrice', 0.0)),
            ask=float(data.get('bestAskPrice', 0.0)),
            oi=data.get('openInterest'),
            oi_change=data.get('OIChange'),
            timestamp=datetime.now()
        )
    
    def _parse_depth_data(self, data: Dict) -> MarketDepth:
        """Parse market depth data"""
        bids = []
        asks = []
        
        # Parse bid levels
        if 'bids' in data:
            for bid in data['bids']:
                bids.append({
                    'price': float(bid.get('price', 0.0)),
                    'qty': int(bid.get('quantity', 0)),
                    'orders': int(bid.get('orders', 0))
                })
        
        # Parse ask levels
        if 'asks' in data:
            for ask in data['asks']:
                asks.append({
                    'price': float(ask.get('price', 0.0)),
                    'qty': int(ask.get('quantity', 0)),
                    'orders': int(ask.get('orders', 0))
                })
        
        return MarketDepth(
            security_id=data.get('security_id', ''),
            exchange_segment=data.get('exchange_segment', 0),
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    def on_tick(self, callback: Callable[[TickData], None]):
        """Register callback for tick data"""
        self.on_tick_callback = callback
    
    def on_depth(self, callback: Callable[[MarketDepth], None]):
        """Register callback for market depth"""
        self.on_depth_callback = callback
    
    def on_error(self, callback: Callable[[str], None]):
        """Register callback for errors"""
        self.on_error_callback = callback


# Example usage
async def example_usage():
    """Example: Subscribe to NIFTY real-time feed"""
    
    # Initialize
    ws = DhanWebSocket(
        access_token="YOUR_ACCESS_TOKEN",
        client_id="YOUR_CLIENT_ID"
    )
    
    # Define callbacks
    def on_tick(tick: TickData):
        logger.info(f"NIFTY LTP: ₹{tick.ltp:.2f} | Volume: {tick.volume} | OI: {tick.oi}")
    
    def on_depth(depth: MarketDepth):
        best_bid = depth.bids[0] if depth.bids else None
        best_ask = depth.asks[0] if depth.asks else None
        logger.info(f"Best Bid: {best_bid} | Best Ask: {best_ask}")
    
    def on_error(error: str):
        logger.error(f"WebSocket error: {error}")
    
    # Register callbacks
    ws.on_tick(on_tick)
    ws.on_depth(on_depth)
    ws.on_error(on_error)
    
    # Connect
    await ws.connect()
    
    # Subscribe to NIFTY ticker
    await ws.subscribe_ticker(
        security_id='13',  # NIFTY
        exchange_segment=ExchangeSegment.IDX_I,
        instrument_type=InstrumentType.INDEX
    )
    
    # Subscribe to NIFTY option (example: 25300 CE)
    await ws.subscribe_quote(
        security_id='STRIKE_SECURITY_ID',  # Get from option chain API
        exchange_segment=ExchangeSegment.NSE_FNO,
        instrument_type=InstrumentType.OPTIDX
    )
    
    # Keep connection alive
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        await ws.disconnect()


if __name__ == "__main__":
    asyncio.run(example_usage())
