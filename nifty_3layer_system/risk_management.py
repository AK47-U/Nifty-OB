"""
RISK MANAGEMENT & POSITION SIZING
Optimizes entry, SL, targets based on:
- Trade strength (confluence score)
- Capital available (15000)
- Risk per trade (1% = 150)
"""

from dataclasses import dataclass
from typing import Dict, Tuple
from enum import Enum


class TradeStrength(Enum):
    """Trade strength based on confluence"""
    VERY_WEAK = (0, 3)      # <3 - Don't trade
    WEAK = (3, 5)           # 3-5 - Skip
    MEDIUM = (5, 7)         # 5-7 - Conservative
    STRONG = (7, 8.5)       # 7-8.5 - Aggressive
    VERY_STRONG = (8.5, 10) # 8.5-10 - Maximum conviction


@dataclass
class RiskProfile:
    """Risk parameters for a trade"""
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    
    risk_points: float  # Entry - SL
    reward_1_points: float  # T1 - Entry
    reward_2_points: float  # T2 - Entry
    
    rr_ratio_1: float  # T1 RR
    rr_ratio_2: float  # T2 RR
    
    quantity: int
    risk_capital: float
    max_profit_1: float
    max_profit_2: float
    
    position_value: float  # Entry * Quantity
    risk_pct: float  # Risk as % of capital


class PositionSizer:
    """
    Optimize position sizing based on:
    - Confluence score (trade strength)
    - Available capital
    - Risk per trade
    - Expected premium decay
    """
    
    def __init__(self, capital: float = 15000.0, risk_pct_per_trade: float = 1.0):
        """
        Args:
            capital: Total trading capital (₹15,000)
            risk_pct_per_trade: Risk per trade in % (1% = ₹150)
        """
        self.capital = capital
        self.risk_pct_per_trade = risk_pct_per_trade
        self.risk_per_trade = capital * (risk_pct_per_trade / 100)
        
    def calculate_position(
        self,
        confluence_score: float,
        entry_price: float,
        atm_ltp: float,
        atr: float,
        trend_bias: str = "BULLISH"
    ) -> RiskProfile:
        """
        Calculate optimized position sizing based on trade strength
        
        Args:
            confluence_score: 1-10 confluence score
            entry_price: Entry price (premium)
            atm_ltp: ATM strike LTP (for context)
            atr: ATR value for volatility
            trend_bias: BULLISH or BEARISH
        
        Returns:
            RiskProfile with optimized entry, SL, targets
        """
        
        # Determine trade strength
        strength = self._get_trade_strength(confluence_score)
        
        # Calculate stop loss based on confluence
        # Stronger confluence = tighter SL = more aggressive
        stop_loss = self._calculate_stop_loss(entry_price, confluence_score, atr)
        
        # Calculate targets based on confluence
        # Stronger confluence = higher targets
        target_1, target_2 = self._calculate_targets(
            entry_price, 
            confluence_score,
            trend_bias
        )
        
        # Calculate quantity based on risk
        risk_points = entry_price - stop_loss
        if risk_points <= 0:
            risk_points = 1  # Minimum 1 point
        
        quantity = max(1, int(self.risk_per_trade / risk_points))
        
        # Cap quantity based on confidence (less confident = smaller size)
        quantity = self._adjust_quantity_for_confidence(quantity, confluence_score)
        
        # Calculate profit/loss
        risk_capital = risk_points * quantity
        max_profit_1 = (target_1 - entry_price) * quantity
        max_profit_2 = (target_2 - entry_price) * quantity
        
        # RR ratios
        rr_ratio_1 = (target_1 - entry_price) / risk_points if risk_points > 0 else 0
        rr_ratio_2 = (target_2 - entry_price) / risk_points if risk_points > 0 else 0
        
        position_value = entry_price * quantity
        
        return RiskProfile(
            entry=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_points=risk_points,
            reward_1_points=target_1 - entry_price,
            reward_2_points=target_2 - entry_price,
            rr_ratio_1=rr_ratio_1,
            rr_ratio_2=rr_ratio_2,
            quantity=quantity,
            risk_capital=risk_capital,
            max_profit_1=max_profit_1,
            max_profit_2=max_profit_2,
            position_value=position_value,
            risk_pct=(risk_capital / self.capital) * 100
        )
    
    def _get_trade_strength(self, confluence: float) -> str:
        """Classify trade strength"""
        if confluence < 3:
            return "VERY_WEAK"
        elif confluence < 5:
            return "WEAK"
        elif confluence < 7:
            return "MEDIUM"
        elif confluence < 8.5:
            return "STRONG"
        else:
            return "VERY_STRONG"
    
    def _calculate_stop_loss(
        self,
        entry: float,
        confluence: float,
        atr: float
    ) -> float:
        """
        Calculate stop loss based on confluence
        
        Stronger confluence = tighter SL (more risk-efficient)
        Weaker confluence = wider SL (more conservative)
        
        Range: 5-15 points depending on confidence
        """
        
        if confluence < 5:
            # Weak: Don't trade (but if forced, 15 point SL)
            return entry - 15
        elif confluence < 6:
            # Medium-weak: 12 point SL
            return entry - 12
        elif confluence < 7:
            # Medium: 10 point SL
            return entry - 10
        elif confluence < 8:
            # Strong: 8 point SL
            return entry - 8
        elif confluence < 8.5:
            # Very strong: 6 point SL
            return entry - 6
        else:
            # Extreme: 5 point SL
            return entry - 5
    
    def _calculate_targets(
        self,
        entry: float,
        confluence: float,
        trend_bias: str
    ) -> Tuple[float, float]:
        """
        Calculate targets based on confluence score
        
        Confluence 8+ (SNIPER):
          - Realistic targets: +12-15 points (T1), +20-25 points (T2)
          - Example: Entry 118 → T1: 130 (12 points) → T2: 140 (22 points)
        
        Confluence 6-7 (CAUTIONARY):
          - Conservative: +8-10 points (T1), +12-15 points (T2)
          - Example: Entry 118 → T1: 126 (8 points) → T2: 130 (12 points)
        
        Confluence <6 (WAIT):
          - Don't trade, but if forced: +5-8 points only
        """
        
        if confluence < 5:
            # Weak - minimal targets
            target_1 = entry + 5
            target_2 = entry + 8
        
        elif confluence < 6:
            # Medium-weak - conservative
            target_1 = entry + 8
            target_2 = entry + 12
        
        elif confluence < 7:
            # Medium - moderate
            target_1 = entry + 10
            target_2 = entry + 15
        
        elif confluence < 8:
            # Strong - optimistic
            target_1 = entry + 12
            target_2 = entry + 20
        
        elif confluence < 8.5:
            # Very strong - aggressive
            target_1 = entry + 14
            target_2 = entry + 24
        
        else:
            # Extreme (8.5+) - maximum conviction
            target_1 = entry + 15
            target_2 = entry + 28
        
        return target_1, target_2
    
    def _adjust_quantity_for_confidence(self, quantity: int, confluence: float) -> int:
        """
        Adjust quantity based on confidence
        
        Stronger confluence = more aggressive sizing
        Weaker confluence = smaller position
        
        Max quantity capped at 15 lots to preserve capital
        """
        
        if confluence < 5:
            # Very weak - risk-off
            return max(1, quantity // 4)
        elif confluence < 6:
            # Medium-weak - conservative
            return max(1, quantity // 2)
        elif confluence < 7:
            # Medium - normal sizing
            return quantity
        elif confluence < 8:
            # Strong - 1.2x sizing
            return int(quantity * 1.2)
        elif confluence < 8.5:
            # Very strong - 1.3x sizing
            return int(quantity * 1.3)
        else:
            # Extreme - 1.5x sizing (cap at 15 to preserve capital)
            return min(int(quantity * 1.5), 15)
    
    def format_risk_profile(self, profile: RiskProfile) -> str:
        """Generate human-readable risk profile"""
        lines = []
        
        strength = self._get_trade_strength(profile.risk_points)
        
        lines.append("\n" + "="*70)
        lines.append("POSITION SIZING & RISK PROFILE")
        lines.append("="*70)
        
        lines.append(f"\n[ENTRY SETUP]")
        lines.append(f"Entry Price:        Rs.{profile.entry:.2f}")
        lines.append(f"Stop Loss:          Rs.{profile.stop_loss:.2f}")
        lines.append(f"Risk Per Share:     Rs.{profile.risk_points:.2f}")
        
        lines.append(f"\n[TARGETS]")
        lines.append(f"Target 1 (70%):     Rs.{profile.target_1:.2f} (+{profile.reward_1_points:.2f})")
        lines.append(f"  RR Ratio:         1:{profile.rr_ratio_1:.2f}")
        lines.append(f"  Profit on 70%:    Rs.{profile.max_profit_1 * 0.7:.0f}")
        
        lines.append(f"\nTarget 2 (30%):     Rs.{profile.target_2:.2f} (+{profile.reward_2_points:.2f})")
        lines.append(f"  RR Ratio:         1:{profile.rr_ratio_2:.2f}")
        lines.append(f"  Profit on 30%:    Rs.{profile.max_profit_2 * 0.3:.0f}")
        
        lines.append(f"\n[POSITION SIZE]")
        lines.append(f"Quantity:           {profile.quantity} lot(s)")
        lines.append(f"Position Value:     Rs.{profile.position_value:.0f}")
        lines.append(f"Risk Capital:       Rs.{profile.risk_capital:.0f}")
        lines.append(f"Risk % of Capital:  {profile.risk_pct:.2f}%")
        
        lines.append(f"\n[PROFIT/LOSS]")
        lines.append(f"Max Profit T1:      Rs.{profile.max_profit_1:.0f}")
        lines.append(f"Max Profit T2:      Rs.{profile.max_profit_2:.0f}")
        lines.append(f"Max Loss (SL):      Rs.{profile.risk_capital:.0f}")
        
        lines.append(f"\n[RECOMMENDATION]")
        if profile.rr_ratio_1 >= 1.5:
            lines.append("✅ EXCELLENT risk/reward - Execute with confidence")
        elif profile.rr_ratio_1 >= 1:
            lines.append("✅ GOOD risk/reward - Execute normally")
        elif profile.rr_ratio_1 >= 0.5:
            lines.append("⚠️  FAIR risk/reward - Consider smaller position")
        else:
            lines.append("❌ POOR risk/reward - Skip this trade")
        
        lines.append("="*70)
        
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    sizer = PositionSizer(capital=15000, risk_pct_per_trade=1.0)
    
    # Test Case 1: High confluence (8.5+)
    print("\n" + "#"*70)
    print("TEST 1: HIGH CONVICTION SNIPER (Confluence: 8.8)")
    print("#"*70)
    
    profile_high = sizer.calculate_position(
        confluence_score=8.8,
        entry_price=118.0,
        atm_ltp=100.0,
        atr=85.0,
        trend_bias="BULLISH"
    )
    
    print(sizer.format_risk_profile(profile_high))
    print(f"\nQuantity Breakdown:")
    print(f"  Risk per trade: Rs.{sizer.risk_per_trade:.0f}")
    print(f"  Risk per point: Rs.{profile_high.risk_points:.2f}")
    print(f"  Calculated qty: {int(sizer.risk_per_trade / profile_high.risk_points)} lots")
    print(f"  Adjusted qty: {profile_high.quantity} lots (after confidence adjustment)")
    
    # Test Case 2: Medium confluence (6.5)
    print("\n" + "#"*70)
    print("TEST 2: MEDIUM CONVICTION (Confluence: 6.5)")
    print("#"*70)
    
    profile_med = sizer.calculate_position(
        confluence_score=6.5,
        entry_price=118.0,
        atm_ltp=100.0,
        atr=85.0,
        trend_bias="BULLISH"
    )
    
    print(sizer.format_risk_profile(profile_med))
    
    # Test Case 3: Weak confluence (4.5)
    print("\n" + "#"*70)
    print("TEST 3: WEAK CONVICTION (Confluence: 4.5)")
    print("#"*70)
    
    profile_weak = sizer.calculate_position(
        confluence_score=4.5,
        entry_price=118.0,
        atm_ltp=100.0,
        atr=85.0,
        trend_bias="BULLISH"
    )
    
    print(sizer.format_risk_profile(profile_weak))
