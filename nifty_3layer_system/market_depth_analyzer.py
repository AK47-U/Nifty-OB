"""
MARKET DEPTH ANALYZER
Analyzes bid-ask liquidity and order flow
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MarketDepthLevel:
    """Single level in market depth"""
    price: float
    bid_qty: int
    ask_qty: int
    bid_orders: int
    ask_orders: int


@dataclass
class DepthAnalysis:
    """Market depth analysis result"""
    bid_ask_spread: float              # Ask - Bid
    spread_pct: float                  # Spread as % of price
    total_bid_qty: int                 # Sum of all bid quantities
    total_ask_qty: int                 # Sum of all ask quantities
    bid_ask_ratio: float               # Bid Qty / Ask Qty
    imbalance_direction: str            # BID, ASK, BALANCED
    imbalance_strength: float           # 0-1 scale
    liquidity_score: float              # 0-10 (higher = better)
    dominant_order_size: str            # SMALL, MEDIUM, LARGE
    resistance_at: Dict[float, int]    # Price -> Qty map
    support_at: Dict[float, int]       # Price -> Qty map


class MarketDepthAnalyzer:
    """Analyze market microstructure"""
    
    def analyze_depth(self, 
                     bid_levels: List[MarketDepthLevel],
                     ask_levels: List[MarketDepthLevel],
                     current_price: float) -> DepthAnalysis:
        """
        Analyze market depth
        
        Args:
            bid_levels: List of bid levels (best to worst)
            ask_levels: List of ask levels (best to worst)
            current_price: Current market price
        """
        if not bid_levels or not ask_levels:
            return self._empty_analysis()
        
        # Get best bid/ask
        best_bid = bid_levels[0].price if bid_levels else current_price
        best_ask = ask_levels[0].price if ask_levels else current_price
        
        # Calculate spread
        spread = best_ask - best_bid
        spread_pct = (spread / current_price) * 100 if current_price else 0
        
        # Calculate total quantities
        total_bid_qty = sum(level.bid_qty for level in bid_levels)
        total_ask_qty = sum(level.ask_qty for level in ask_levels)
        
        # Bid-Ask ratio
        bid_ask_ratio = (total_bid_qty / total_ask_qty) if total_ask_qty > 0 else 0
        
        # Imbalance analysis
        if bid_ask_ratio > 1.1:
            imbalance = "BID"
            strength = min(0.99, (bid_ask_ratio - 1) / bid_ask_ratio)
        elif bid_ask_ratio < 0.9:
            imbalance = "ASK"
            strength = min(0.99, (1 - bid_ask_ratio))
        else:
            imbalance = "BALANCED"
            strength = 0.0
        
        # Liquidity score (0-10)
        # Higher spread = lower liquidity
        # Wider order book = better liquidity
        total_book = total_bid_qty + total_ask_qty
        depth_score = min(10, total_book / 10000) if total_book > 0 else 0
        spread_penalty = max(0, spread_pct * 10)  # 1% spread = -10 points
        liquidity = max(0, depth_score - spread_penalty)
        
        # Dominant order size
        avg_bid_size = (total_bid_qty / len(bid_levels)) if bid_levels else 0
        avg_ask_size = (total_ask_qty / len(ask_levels)) if ask_levels else 0
        avg_size = (avg_bid_size + avg_ask_size) / 2
        
        if avg_size < 100:
            order_type = "SMALL"
        elif avg_size < 500:
            order_type = "MEDIUM"
        else:
            order_type = "LARGE"
        
        # Support and Resistance from depth
        resistance = self._calculate_levels(ask_levels, depth=5)
        support = self._calculate_levels(bid_levels, depth=5)
        
        return DepthAnalysis(
            bid_ask_spread=spread,
            spread_pct=spread_pct,
            total_bid_qty=total_bid_qty,
            total_ask_qty=total_ask_qty,
            bid_ask_ratio=bid_ask_ratio,
            imbalance_direction=imbalance,
            imbalance_strength=strength,
            liquidity_score=liquidity,
            dominant_order_size=order_type,
            resistance_at=resistance,
            support_at=support
        )
    
    def _calculate_levels(self, 
                         levels: List[MarketDepthLevel],
                         depth: int = 5) -> Dict[float, int]:
        """Calculate price levels from depth"""
        result = {}
        for i, level in enumerate(levels[:depth]):
            result[level.price] = level.bid_qty if i >= 0 else level.ask_qty
        return result
    
    def _empty_analysis(self) -> DepthAnalysis:
        """Return empty analysis"""
        return DepthAnalysis(
            bid_ask_spread=0.0,
            spread_pct=0.0,
            total_bid_qty=0,
            total_ask_qty=0,
            bid_ask_ratio=0.0,
            imbalance_direction="BALANCED",
            imbalance_strength=0.0,
            liquidity_score=0.0,
            dominant_order_size="UNKNOWN",
            resistance_at={},
            support_at={}
        )
    
    def detect_order_flow(self,
                         prev_bid_qty: int,
                         prev_ask_qty: int,
                         curr_bid_qty: int,
                         curr_ask_qty: int,
                         price_direction: str) -> dict:
        """
        Detect order flow direction
        
        Args:
            prev_bid_qty: Previous bid quantity
            prev_ask_qty: Previous ask quantity
            curr_bid_qty: Current bid quantity
            curr_ask_qty: Current ask quantity
            price_direction: UP, DOWN, FLAT
        
        Returns:
            {
                'flow_direction': 'BUYING' | 'SELLING' | 'NEUTRAL',
                'strength': 0-1 scale,
                'signal': str
            }
        """
        bid_change = curr_bid_qty - prev_bid_qty
        ask_change = curr_ask_qty - prev_ask_qty
        
        # Aggressive buying: Ask qty decreasing + Price up
        if ask_change < -100 and price_direction == "UP":
            return {
                'flow_direction': 'BUYING',
                'strength': min(0.99, abs(ask_change) / 1000),
                'signal': 'Aggressive buying (ask reduction)'
            }
        
        # Aggressive selling: Bid qty decreasing + Price down
        if bid_change < -100 and price_direction == "DOWN":
            return {
                'flow_direction': 'SELLING',
                'strength': min(0.99, abs(bid_change) / 1000),
                'signal': 'Aggressive selling (bid reduction)'
            }
        
        # Bid building: Bid qty increasing
        if bid_change > 200 and ask_change < 100:
            return {
                'flow_direction': 'BUYING',
                'strength': 0.6,
                'signal': 'Bid building (support accumulation)'
            }
        
        # Ask building: Ask qty increasing
        if ask_change > 200 and bid_change < 100:
            return {
                'flow_direction': 'SELLING',
                'strength': 0.6,
                'signal': 'Ask building (resistance formation)'
            }
        
        return {
            'flow_direction': 'NEUTRAL',
            'strength': 0.0,
            'signal': 'No clear order flow'
        }
