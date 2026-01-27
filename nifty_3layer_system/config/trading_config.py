"""
Trading Configuration
All configurable parameters and constants for the trading system
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TradingConfig:
    """Main trading configuration"""
    
    # Capital & Risk Management
    CAPITAL: float = 15000.0
    RISK_PER_TRADE_PCT: float = 0.01  # 1% risk per trade
    MIN_STOP_LOSS_POINTS: float = 12.0
    MAX_QUANTITY_LOTS: int = 6
    REWARD_RISK_RATIO: float = 1.5
    
    # Market Hours (IST)
    MARKET_START_HOUR: int = 9
    MARKET_START_MINUTE: int = 15
    MARKET_END_HOUR: int = 15
    MARKET_END_MINUTE: int = 30
    
    # Data Fetch Parameters
    INTRADAY_CANDLE_INTERVAL: int = 5  # minutes
    INTRADAY_LOOKBACK_DAYS: int = 10
    DAILY_LOOKBACK_DAYS: int = 365
    DAILY_RECENT_DAYS: int = 10  # fetch recent days then slice for PDH/PDL
    SECONDARY_INTERVAL: int = 15  # minutes
    SECONDARY_LOOKBACK_DAYS: int = 5
    HIGHER_INTERVAL: int = 60  # minutes (1 hour)
    HIGHER_LOOKBACK_DAYS: int = 15
    
    # Technical Indicators
    EMA_PERIODS: list = None
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    ATR_PERIOD: int = 14
    VOLUME_MA_PERIOD: int = 20
    VWAP_PERIOD: int = 20
    
    # Options Parameters
    STRIKE_ROUNDING: float = 50.0  # Round strikes to nearest 50
    DEFAULT_RISK_FREE_RATE: float = 0.06  # 6% annual
    DEFAULT_IV_ESTIMATE: float = 0.22  # 22% fallback IV
    IV_52W_HIGH_ESTIMATE: float = 0.35  # 35%
    IV_52W_LOW_ESTIMATE: float = 0.12  # 12%

    # Execution & Liquidity (tuned for 15–30 minute 50-pt captures)
    SPREAD_MAX_PCT: float = 0.006          # Max bid-ask spread as % of premium (e.g., 0.6%)
    SPREAD_MAX_ABS: float = 4.0            # Max absolute spread in INR
    DEPTH_MIN_LOTS: int = 10               # Minimum top-of-book lots to allow entry
    LTT_MAX_AGE_SEC: int = 20              # Last traded tick must be recent (avoid stale quotes)

    # Slippage / impact modeling
    SLIPPAGE_K: float = 0.35               # Fraction of spread paid on entry (0.35 ~ mid + 35% spread)
    IMPACT_BPS: float = 8.0                # Impact cost in basis points of notional for larger sizes

    # Live refresh cadence
    REFRESH_INTERVAL_SEC: int = 60         # Recompute signals every 60s
    HEARTBEAT_MAX_AGE_SEC: int = 15        # If data older than this, block trades

    # Order-risk governor
    DAILY_MAX_LOSS_PCT: float = 0.015      # Stop trading after 1.5% capital drawdown
    MAX_CONSEC_SL: int = 2                 # Stop after 2 consecutive stop-loss hits
    MAX_CONSEC_WAIT: int = 4               # Optional freeze after too many WAITs (chop filter)
    
    # Yearly Level Analysis
    LEVEL_PROXIMITY_THRESHOLD_PCT: float = 0.005  # 0.5% proximity threshold
    
    def __post_init__(self):
        """Initialize derived attributes"""
        if self.EMA_PERIODS is None:
            self.EMA_PERIODS = [5, 12, 20, 50, 100, 200]
    
    @property
    def risk_amount(self) -> float:
        """Calculate risk amount based on capital"""
        return self.CAPITAL * self.RISK_PER_TRADE_PCT
    
    def to_dict(self) -> Dict:
        """Export config as dictionary"""
        return {
            'capital': self.CAPITAL,
            'risk_per_trade': f"{self.RISK_PER_TRADE_PCT*100}%",
            'risk_amount': f"₹{self.risk_amount:.2f}",
            'max_quantity': self.MAX_QUANTITY_LOTS,
            'reward_risk_ratio': self.REWARD_RISK_RATIO,
            'ema_periods': self.EMA_PERIODS,
            'rsi_period': self.RSI_PERIOD,
            'atr_period': self.ATR_PERIOD
        }


# Singleton instance
CONFIG = TradingConfig()
