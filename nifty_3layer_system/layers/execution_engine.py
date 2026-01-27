"""
LAYER 3: Execution & Greeks Engine
WHAT TO TRADE - Strike Selection, Risk Management, and Dynamic Targets

Input: Confirmed signal from Layer 2
Tasks:
1. Scan option chain for best strikes (Delta 0.50-0.60)
2. Monitor IV for abnormal spikes
3. Calculate ATR-based SL (1.5 × ATR)
4. Set R1-R4 trailing targets
5. Implement risk cap (daily loss limit)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from config.settings import TradingConfig


@dataclass
class OptionStrike:
    """Represents an option contract"""
    strike: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float
    bid: float
    ask: float
    volume: int
    oi: int
    liquidity_score: float = 0.0


@dataclass
class ExecutionSetup:
    """Complete trade setup with entry, exit, risk parameters"""
    signal_type: str  # 'CALL' or 'PUT'
    entry_price: float
    strike: float
    contract_type: str  # 'CE' or 'PE'
    
    stop_loss: float
    risk_points: float
    
    target_1: float  # R1/S1
    target_2: float  # R2/S2
    target_3: float  # R3/S3
    
    delta: float
    iv: float
    liquidity_score: float
    
    quantity: int = 1
    capital_required: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    risk_reward_1: float = 0.0
    risk_reward_2: float = 0.0
    
    status: str = "pending"  # pending, active, closed
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0


class ExecutionGreeksEngine:
    """
    Layer 3: Execution & Risk Management
    Selects best option strike and manages dynamic risk
    """
    
    def __init__(self, capital: float = 15000.0):
        self.config = TradingConfig()
        self.capital = capital
        self.daily_loss_limit = capital * 0.06  # 6% daily loss cap
        self.max_trades_per_day = 3
        self.daily_pnl = 0.0
        self.trades_today = 0
        
        logger.info(f"Layer 3 initialized: Execution Engine | Capital: ₹{capital}")
    
    def select_best_strike(
        self,
        option_chain: pd.DataFrame,
        signal_type: str,
        delta_range: Tuple[float, float] = (0.50, 0.60)
    ) -> Optional[Dict]:
        """
        Select best option strike based on Greeks
        
        Args:
            option_chain: DataFrame with strikes and Greeks
            signal_type: 'CALL' or 'PUT'
            delta_range: Preferred delta range (default 0.50-0.60)
        
        Returns:
            Best strike information
        """
        contract_type = 'CE' if signal_type == 'CALL' else 'PE'
        
        # Filter by contract type
        chain = option_chain[option_chain['type'] == contract_type].copy()
        
        if len(chain) == 0:
            logger.warning(f"No {contract_type} contracts found in option chain")
            return None
        
        # Filter by delta range
        chain['delta_diff'] = abs(chain['delta'] - 0.55)  # Target delta 0.55 (middle of range)
        chain = chain[
            (chain['delta'] >= delta_range[0]) &
            (chain['delta'] <= delta_range[1])
        ]
        
        if len(chain) == 0:
            logger.warning(f"No contracts found in delta range {delta_range}")
            # Fallback to closest delta
            chain = option_chain[option_chain['type'] == contract_type].copy()
            chain['delta_diff'] = abs(chain['delta'] - 0.55)
        
        # Score based on: delta accuracy, volume, OI, IV
        chain['liquidity_score'] = (
            (1 - (chain['delta_diff'] / 0.15)) * 0.3 +  # Delta accuracy (30%)
            (chain['volume'] / chain['volume'].max()) * 0.3 +  # Volume (30%)
            (chain['oi'] / chain['oi'].max()) * 0.4  # OI (40%)
        )
        
        best_strike = chain.loc[chain['liquidity_score'].idxmax()]
        
        logger.info(f"Selected {contract_type} Strike: {best_strike['strike']:.0f} | "
                   f"Delta: {best_strike['delta']:.2f} | "
                   f"Score: {best_strike['liquidity_score']:.2f}")
        
        return best_strike.to_dict()
    
    def calculate_execution_setup(
        self,
        signal_type: str,
        entry_price: float,
        atr: float,
        best_strike: Dict,
        cpr_levels: Dict,
        r_levels: Dict,
        s_levels: Dict
    ) -> ExecutionSetup:
        """
        Calculate complete trade setup with targets and risk
        
        Args:
            signal_type: 'CALL' or 'PUT'
            entry_price: Current market price
            atr: ATR value for SL calculation
            best_strike: Selected option strike details
            cpr_levels: CPR (pivot, tc, bc)
            r_levels: R1, R2, R3, R4 levels
            s_levels: S1, S2, S3, S4 levels
        
        Returns:
            ExecutionSetup with all parameters
        """
        
        # Calculate SL: 1.5 × ATR or nearest level (whichever is tighter)
        sl_atr = 1.5 * atr
        
        if signal_type == 'CALL':
            sl_price = entry_price - sl_atr
            # Use nearest support as backup SL
            nearest_support = max([v for k, v in s_levels.items() if v < entry_price], 
                                 default=entry_price - sl_atr)
            sl_price = max(sl_price, nearest_support)
            
            # Targets: R1, R2, R3
            t1 = r_levels.get('r1', entry_price + atr)
            t2 = r_levels.get('r2', entry_price + 2 * atr)
            t3 = r_levels.get('r3', entry_price + 3 * atr)
            
        else:  # PUT
            sl_price = entry_price + sl_atr
            # Use nearest resistance as backup SL
            nearest_resistance = min([v for k, v in r_levels.items() if v > entry_price],
                                   default=entry_price + sl_atr)
            sl_price = min(sl_price, nearest_resistance)
            
            # Targets: S1, S2, S3
            t1 = s_levels.get('s1', entry_price - atr)
            t2 = s_levels.get('s2', entry_price - 2 * atr)
            t3 = s_levels.get('s3', entry_price - 3 * atr)
        
        # Risk calculation
        risk_points = abs(sl_price - entry_price)
        reward_1 = abs(t1 - entry_price)
        reward_2 = abs(t2 - entry_price)
        reward_3 = abs(t3 - entry_price)
        
        rr1 = reward_1 / risk_points if risk_points > 0 else 0
        rr2 = reward_2 / risk_points if risk_points > 0 else 0
        
        # Position sizing based on capital and risk
        max_risk_per_trade = self.capital * 0.02  # 2% risk per trade
        quantity = max(1, int(max_risk_per_trade / (risk_points * 50)))  # 50 points = 1 lot assumption
        
        setup = ExecutionSetup(
            signal_type=signal_type,
            entry_price=entry_price,
            strike=best_strike.get('strike', entry_price),
            contract_type='CE' if signal_type == 'CALL' else 'PE',
            
            stop_loss=sl_price,
            risk_points=risk_points,
            
            target_1=t1,
            target_2=t2,
            target_3=t3,
            
            delta=best_strike.get('delta', 0.55),
            iv=best_strike.get('iv', 0.0),
            liquidity_score=best_strike.get('liquidity_score', 0.0),
            
            quantity=quantity,
            capital_required=quantity * best_strike.get('ask', entry_price) * 50,  # Rough estimate
            max_loss=quantity * risk_points * 50,
            max_profit=quantity * reward_3 * 50,
            risk_reward_1=rr1,
            risk_reward_2=rr2
        )
        
        logger.info(f"Execution Setup: {setup.contract_type} | "
                   f"Entry:{setup.entry_price:.0f} | "
                   f"SL:{setup.stop_loss:.0f} ({setup.risk_points:.0f}pts) | "
                   f"T1:{setup.target_1:.0f} ({reward_1:.0f}pts) | "
                   f"R:R T1: 1:{setup.risk_reward_1:.2f}")
        
        return setup
    
    def check_iv_spike(
        self,
        current_iv: float,
        iv_5day_avg: float,
        spike_threshold: float = 0.20
    ) -> Tuple[bool, float]:
        """
        Check for abnormal IV spikes
        
        Args:
            current_iv: Current implied volatility
            iv_5day_avg: 5-day average IV
            spike_threshold: Spike threshold (default 20%)
        
        Returns:
            (is_spike, spike_percentage)
        """
        if iv_5day_avg == 0:
            return False, 0.0
        
        spike_pct = (current_iv - iv_5day_avg) / iv_5day_avg
        is_spike = spike_pct > spike_threshold
        
        if is_spike:
            logger.warning(f"IV Spike Detected: {current_iv:.2f} (+{spike_pct*100:.1f}%) "
                          f"vs 5-day avg: {iv_5day_avg:.2f}")
        
        return is_spike, spike_pct
    
    def check_risk_limits(self) -> Dict:
        """Check if daily risk limits exceeded"""
        limits = {
            'daily_loss_limit': self.daily_loss_limit,
            'current_daily_pnl': self.daily_pnl,
            'remaining_loss_buffer': self.daily_loss_limit - abs(self.daily_pnl),
            'trades_today': self.trades_today,
            'max_trades_allowed': self.max_trades_per_day,
            'can_trade': (abs(self.daily_pnl) < self.daily_loss_limit) and 
                         (self.trades_today < self.max_trades_per_day)
        }
        
        return limits
    
    def record_trade_exit(self, setup: ExecutionSetup, exit_price: float, pnl: float):
        """Record completed trade"""
        setup.exit_time = datetime.now()
        setup.pnl = pnl
        setup.status = 'closed'
        
        self.daily_pnl += pnl
        self.trades_today += 1
        
        logger.info(f"Trade Closed: {setup.contract_type} | "
                   f"Entry:{setup.entry_price:.0f} Exit:{exit_price:.0f} | "
                   f"PnL: ₹{pnl:.0f}")


# Test
if __name__ == "__main__":
    engine = ExecutionGreeksEngine(capital=15000.0)
    
    print("\n" + "="*80)
    print("LAYER 3: EXECUTION & GREEKS ENGINE TEST")
    print("="*80)
    
    # Mock option chain
    option_chain = pd.DataFrame({
        'strike': [25600, 25650, 25700, 25750, 25800],
        'type': ['CE', 'CE', 'CE', 'CE', 'CE'],
        'delta': [0.45, 0.55, 0.65, 0.75, 0.85],
        'iv': [0.25, 0.24, 0.26, 0.27, 0.28],
        'bid': [100, 80, 65, 50, 38],
        'ask': [110, 90, 75, 60, 48],
        'volume': [500, 2000, 3000, 1500, 200],
        'oi': [10000, 50000, 75000, 45000, 5000]
    })
    
    # Select best strike
    best = engine.select_best_strike(option_chain, 'CALL')
    print(f"\nBest Strike Selected: {best['strike']:.0f}")
    print(f"  Delta: {best['delta']:.2f}")
    print(f"  IV: {best['iv']:.2f}")
    print(f"  Volume: {best['volume']}")
    print(f"  OI: {best['oi']}")
    print(f"  Liquidity Score: {best['liquidity_score']:.2f}")
    
    # Calculate execution setup
    setup = engine.calculate_execution_setup(
        signal_type='CALL',
        entry_price=25700.0,
        atr=220.0,
        best_strike=best,
        cpr_levels={'pivot': 25650, 'tc': 25700, 'bc': 25600},
        r_levels={'r1': 25800, 'r2': 25900, 'r3': 26000, 'r4': 26100},
        s_levels={'s1': 25600, 's2': 25500, 's3': 25400, 's4': 25300}
    )
    
    print(f"\nExecution Setup:")
    print(f"  Entry: {setup.entry_price:.0f}")
    print(f"  SL: {setup.stop_loss:.0f} ({setup.risk_points:.0f}pts)")
    print(f"  T1: {setup.target_1:.0f} ({abs(setup.target_1 - setup.entry_price):.0f}pts)")
    print(f"  T2: {setup.target_2:.0f} ({abs(setup.target_2 - setup.entry_price):.0f}pts)")
    print(f"  T3: {setup.target_3:.0f} ({abs(setup.target_3 - setup.entry_price):.0f}pts)")
    print(f"  R:R (T1): 1:{setup.risk_reward_1:.2f}")
    print(f"  R:R (T2): 1:{setup.risk_reward_2:.2f}")
    
    # Check IV spike
    is_spike, spike_pct = engine.check_iv_spike(0.30, 0.25, 0.20)
    print(f"\nIV Spike Check: {is_spike} ({spike_pct*100:.1f}% increase)")
    
    # Check risk limits
    limits = engine.check_risk_limits()
    print(f"\nRisk Limits:")
    print(f"  Daily Loss Limit: ₹{limits['daily_loss_limit']:.0f}")
    print(f"  Current Daily PnL: ₹{limits['current_daily_pnl']:.0f}")
    print(f"  Can Trade: {limits['can_trade']}")
    
    print("\n" + "="*80)
