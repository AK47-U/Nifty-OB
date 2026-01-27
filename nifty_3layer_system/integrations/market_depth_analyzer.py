"""
MARKET DEPTH ANALYZER
Analyzes 20-level market depth to detect liquidity zones and institutional activity

Key Metrics:
- Cumulative Bid/Ask Volume
- Weighted Average Bid/Ask Price
- Support/Resistance from depth
- Iceberg orders detection
- Liquidity imbalance
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


@dataclass
class DepthLevel:
    """Single depth level (bid or ask)"""
    price: float
    quantity: int
    orders: int


@dataclass
class DepthAnalysis:
    """Complete depth analysis"""
    timestamp: datetime
    
    # Bid side
    total_bid_volume: int
    total_bid_orders: int
    weighted_bid_price: float
    bid_levels: List[DepthLevel]
    
    # Ask side
    total_ask_volume: int
    total_ask_orders: int
    weighted_ask_price: float
    ask_levels: List[DepthLevel]
    
    # Spread
    best_bid: float
    best_ask: float
    spread: float
    spread_pct: float
    
    # Liquidity metrics
    liquidity_score: float  # 0-1 (1 = high liquidity)
    bid_ask_imbalance: float  # -1 to 1 (positive = bid heavy, negative = ask heavy)
    
    # Institutional signals
    large_orders_bid: int  # Orders > avg size
    large_orders_ask: int
    iceberg_detected: bool  # Multiple small orders at same price
    
    # Support/Resistance from depth
    support_zone: Optional[float]  # Price level with heavy bid buildup
    resistance_zone: Optional[float]  # Price level with heavy ask buildup


class MarketDepthAnalyzer:
    """
    Analyzes 20-level market depth for trading insights
    """
    
    def __init__(self, iceberg_threshold: int = 5):
        """
        Args:
            iceberg_threshold: Min orders at same price to flag iceberg
        """
        self.iceberg_threshold = iceberg_threshold
        logger.info("Market Depth Analyzer initialized")
    
    def analyze(
        self,
        bids: List[Dict[str, float]],
        asks: List[Dict[str, float]]
    ) -> DepthAnalysis:
        """
        Analyze 20-level depth
        
        Args:
            bids: List of {'price': x, 'qty': y, 'orders': z}
            asks: List of {'price': x, 'qty': y, 'orders': z}
        
        Returns:
            DepthAnalysis with complete metrics
        """
        # Parse levels
        bid_levels = [
            DepthLevel(
                price=float(b['price']),
                quantity=int(b['qty']),
                orders=int(b['orders'])
            )
            for b in bids if b['price'] > 0
        ]
        
        ask_levels = [
            DepthLevel(
                price=float(a['price']),
                quantity=int(a['qty']),
                orders=int(a['orders'])
            )
            for a in asks if a['price'] > 0
        ]
        
        # Sort
        bid_levels.sort(key=lambda x: x.price, reverse=True)
        ask_levels.sort(key=lambda x: x.price)
        
        # Best bid/ask
        best_bid = bid_levels[0].price if bid_levels else 0.0
        best_ask = ask_levels[0].price if ask_levels else 0.0
        
        # Spread
        spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0.0
        spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0.0
        
        # Volume metrics
        total_bid_volume = sum(lvl.quantity for lvl in bid_levels)
        total_ask_volume = sum(lvl.quantity for lvl in ask_levels)
        total_bid_orders = sum(lvl.orders for lvl in bid_levels)
        total_ask_orders = sum(lvl.orders for lvl in ask_levels)
        
        # Weighted average prices
        weighted_bid = self._calculate_weighted_price(bid_levels)
        weighted_ask = self._calculate_weighted_price(ask_levels)
        
        # Bid-ask imbalance
        total_volume = total_bid_volume + total_ask_volume
        if total_volume > 0:
            imbalance = (total_bid_volume - total_ask_volume) / total_volume
        else:
            imbalance = 0.0
        
        # Liquidity score (based on volume + tight spread)
        liquidity_score = self._calculate_liquidity_score(
            total_bid_volume,
            total_ask_volume,
            spread_pct
        )
        
        # Detect large orders
        avg_bid_qty = total_bid_volume / len(bid_levels) if bid_levels else 0
        avg_ask_qty = total_ask_volume / len(ask_levels) if ask_levels else 0
        
        large_bid_orders = sum(1 for lvl in bid_levels if lvl.quantity > avg_bid_qty * 2)
        large_ask_orders = sum(1 for lvl in ask_levels if lvl.quantity > avg_ask_qty * 2)
        
        # Iceberg detection
        iceberg_detected = self._detect_iceberg_orders(bid_levels, ask_levels)
        
        # Support/Resistance zones
        support_zone = self._find_support_zone(bid_levels)
        resistance_zone = self._find_resistance_zone(ask_levels)
        
        return DepthAnalysis(
            timestamp=datetime.now(),
            total_bid_volume=total_bid_volume,
            total_bid_orders=total_bid_orders,
            weighted_bid_price=weighted_bid,
            bid_levels=bid_levels,
            total_ask_volume=total_ask_volume,
            total_ask_orders=total_ask_orders,
            weighted_ask_price=weighted_ask,
            ask_levels=ask_levels,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_pct=spread_pct,
            liquidity_score=liquidity_score,
            bid_ask_imbalance=imbalance,
            large_orders_bid=large_bid_orders,
            large_orders_ask=large_ask_orders,
            iceberg_detected=iceberg_detected,
            support_zone=support_zone,
            resistance_zone=resistance_zone
        )
    
    def _calculate_weighted_price(self, levels: List[DepthLevel]) -> float:
        """Calculate volume-weighted average price"""
        if not levels:
            return 0.0
        
        total_value = sum(lvl.price * lvl.quantity for lvl in levels)
        total_quantity = sum(lvl.quantity for lvl in levels)
        
        return total_value / total_quantity if total_quantity > 0 else 0.0
    
    def _calculate_liquidity_score(
        self,
        bid_volume: int,
        ask_volume: int,
        spread_pct: float
    ) -> float:
        """
        Calculate liquidity score (0-1)
        
        High liquidity = high volume + tight spread
        """
        # Volume score (normalize to 0-1)
        total_volume = bid_volume + ask_volume
        volume_score = min(total_volume / 10000, 1.0)  # Assume 10k is excellent
        
        # Spread score (tighter = better)
        if spread_pct < 0.05:
            spread_score = 1.0
        elif spread_pct < 0.1:
            spread_score = 0.8
        elif spread_pct < 0.2:
            spread_score = 0.6
        else:
            spread_score = 0.4
        
        # Combined score
        return (volume_score * 0.6 + spread_score * 0.4)
    
    def _detect_iceberg_orders(
        self,
        bid_levels: List[DepthLevel],
        ask_levels: List[DepthLevel]
    ) -> bool:
        """
        Detect iceberg orders (multiple small orders at same price)
        
        Pattern: High order count but small individual quantities
        """
        for lvl in bid_levels[:5]:  # Check top 5 levels
            if lvl.orders >= self.iceberg_threshold:
                avg_order_size = lvl.quantity / lvl.orders
                if avg_order_size < 50:  # Small order sizes
                    return True
        
        for lvl in ask_levels[:5]:
            if lvl.orders >= self.iceberg_threshold:
                avg_order_size = lvl.quantity / lvl.orders
                if avg_order_size < 50:
                    return True
        
        return False
    
    def _find_support_zone(self, bid_levels: List[DepthLevel]) -> Optional[float]:
        """
        Find strongest support zone from bid depth
        
        Returns price level with highest cumulative volume
        """
        if not bid_levels:
            return None
        
        # Find level with max volume
        max_level = max(bid_levels, key=lambda x: x.quantity)
        
        # Only return if volume is significant
        avg_volume = sum(lvl.quantity for lvl in bid_levels) / len(bid_levels)
        if max_level.quantity > avg_volume * 1.5:
            return max_level.price
        
        return None
    
    def _find_resistance_zone(self, ask_levels: List[DepthLevel]) -> Optional[float]:
        """
        Find strongest resistance zone from ask depth
        
        Returns price level with highest cumulative volume
        """
        if not ask_levels:
            return None
        
        # Find level with max volume
        max_level = max(ask_levels, key=lambda x: x.quantity)
        
        # Only return if volume is significant
        avg_volume = sum(lvl.quantity for lvl in ask_levels) / len(ask_levels)
        if max_level.quantity > avg_volume * 1.5:
            return max_level.price
        
        return None
    
    def get_liquidity_summary(self, analysis: DepthAnalysis) -> str:
        """Generate human-readable liquidity summary"""
        lines = []
        lines.append("="*60)
        lines.append("MARKET DEPTH ANALYSIS")
        lines.append("="*60)
        
        # Spread
        lines.append(f"\n[SPREAD]")
        lines.append(f"Best Bid: ₹{analysis.best_bid:.2f}")
        lines.append(f"Best Ask: ₹{analysis.best_ask:.2f}")
        lines.append(f"Spread: ₹{analysis.spread:.2f} ({analysis.spread_pct:.3f}%)")
        
        # Volume
        lines.append(f"\n[VOLUME]")
        lines.append(f"Total Bid Volume: {analysis.total_bid_volume:,} ({analysis.total_bid_orders} orders)")
        lines.append(f"Total Ask Volume: {analysis.total_ask_volume:,} ({analysis.total_ask_orders} orders)")
        lines.append(f"Bid/Ask Imbalance: {analysis.bid_ask_imbalance:+.2f}")
        
        if analysis.bid_ask_imbalance > 0.2:
            lines.append("  → BID HEAVY (Bullish)")
        elif analysis.bid_ask_imbalance < -0.2:
            lines.append("  → ASK HEAVY (Bearish)")
        else:
            lines.append("  → BALANCED")
        
        # Liquidity
        lines.append(f"\n[LIQUIDITY]")
        lines.append(f"Liquidity Score: {analysis.liquidity_score:.2f}/1.00")
        
        if analysis.liquidity_score > 0.7:
            lines.append("  → HIGH LIQUIDITY (Good for execution)")
        elif analysis.liquidity_score > 0.5:
            lines.append("  → MODERATE LIQUIDITY")
        else:
            lines.append("  → LOW LIQUIDITY (Slippage risk)")
        
        # Institutional signals
        lines.append(f"\n[INSTITUTIONAL SIGNALS]")
        lines.append(f"Large Bid Orders: {analysis.large_orders_bid}")
        lines.append(f"Large Ask Orders: {analysis.large_orders_ask}")
        lines.append(f"Iceberg Orders: {'YES' if analysis.iceberg_detected else 'NO'}")
        
        # Support/Resistance
        if analysis.support_zone or analysis.resistance_zone:
            lines.append(f"\n[KEY ZONES FROM DEPTH]")
            if analysis.support_zone:
                lines.append(f"Support Zone: ₹{analysis.support_zone:.2f}")
            if analysis.resistance_zone:
                lines.append(f"Resistance Zone: ₹{analysis.resistance_zone:.2f}")
        
        lines.append("="*60)
        
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    # Sample 20-level depth data
    sample_bids = [
        {'price': 25310.0, 'qty': 500, 'orders': 10},
        {'price': 25309.5, 'qty': 800, 'orders': 15},
        {'price': 25309.0, 'qty': 1200, 'orders': 20},
        {'price': 25308.5, 'qty': 600, 'orders': 12},
        {'price': 25308.0, 'qty': 900, 'orders': 18},
        {'price': 25307.5, 'qty': 400, 'orders': 8},
        {'price': 25307.0, 'qty': 700, 'orders': 14},
        {'price': 25306.5, 'qty': 550, 'orders': 11},
        {'price': 25306.0, 'qty': 850, 'orders': 17},
        {'price': 25305.5, 'qty': 1000, 'orders': 25},  # Support zone
    ]
    
    sample_asks = [
        {'price': 25310.5, 'qty': 450, 'orders': 9},
        {'price': 25311.0, 'qty': 750, 'orders': 14},
        {'price': 25311.5, 'qty': 600, 'orders': 12},
        {'price': 25312.0, 'qty': 1500, 'orders': 30},  # Resistance zone
        {'price': 25312.5, 'qty': 550, 'orders': 11},
        {'price': 25313.0, 'qty': 800, 'orders': 16},
        {'price': 25313.5, 'qty': 400, 'orders': 8},
        {'price': 25314.0, 'qty': 700, 'orders': 14},
        {'price': 25314.5, 'qty': 500, 'orders': 10},
        {'price': 25315.0, 'qty': 650, 'orders': 13},
    ]
    
    analyzer = MarketDepthAnalyzer()
    analysis = analyzer.analyze(sample_bids, sample_asks)
    
    print(analyzer.get_liquidity_summary(analysis))
