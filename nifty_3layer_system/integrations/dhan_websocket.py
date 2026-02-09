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
    """Exchange segments"""
    NSE_EQ = 0
    NSE_FNO = 1
    BSE_EQ = 3
    MCX_COMM = 4
    NSE_CURRENCY = 7
    BSE_CURRENCY = 13
    IDX_I = 16  # Index segment


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
        """Establish WebSocket connection"""
        try:
            logger.info(f"Connecting to Dhan WebSocket Feed...")
            
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
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
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
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError:
                    # Binary data (market depth)
                    await self._process_binary_message(message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_connected = False
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
        """Process binary message (market depth)"""
        # TODO: Implement binary parsing based on Dhan protocol
        pass
    
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
