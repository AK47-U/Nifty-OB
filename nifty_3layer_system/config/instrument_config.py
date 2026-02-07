"""
INSTRUMENT CONFIGURATION
Maps instruments to their Dhan API parameters and trading configs
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class InstrumentConfig:
    """Configuration for each tradeable instrument"""
    name: str                          # Display name (NIFTY 50, SENSEX, etc.)
    symbol: str                        # Trading symbol
    security_id: str                   # Dhan security_id
    exchange_segment: str              # Dhan exchange segment (IDX_I, NSE_FO, etc.)
    instrument_type: str               # OPTIDX, FUTIDX, etc.
    strike_rounding: float             # Round strikes to nearest (50 for NIFTY/SENSEX, 100 for BANKNIFTY)
    lot_size: int                      # Lot size for options
    spot_multiplier: float             # Multiplier for notional calculation
    capital_per_instrument: float       # Suggested capital allocation
    risk_per_trade_pct: float          # Risk % per trade
    min_stop_loss_points: float        # Minimum SL in points
    description: str                   # Human-readable description


# ═════════════════════════════════════════════════════════════════════════════════
# INSTRUMENT DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════════

INSTRUMENTS: Dict[str, InstrumentConfig] = {
    
    "NIFTY": InstrumentConfig(
        name="NIFTY 50",
        symbol="NIFTY",
        security_id="13",
        exchange_segment="IDX_I",
        instrument_type="OPTIDX",
        strike_rounding=50.0,
        lot_size=1,
        spot_multiplier=1.0,
        capital_per_instrument=15000.0,
        risk_per_trade_pct=0.01,
        min_stop_loss_points=12.0,
        description="NIFTY 50 Index Options (Primary Index)",
    ),
    
    "SENSEX": InstrumentConfig(
        name="BSE SENSEX",
        symbol="SENSEX",
        security_id="51",
        exchange_segment="IDX_I",
        instrument_type="OPTIDX",
        strike_rounding=100.0,  # SENSEX strikes in 100pt intervals (82300, 82400, 82500...)
        lot_size=1,
        spot_multiplier=1.0,
        capital_per_instrument=15000.0,
        risk_per_trade_pct=0.01,
        min_stop_loss_points=15.0,  # Slightly higher SL for SENSEX
        description="BSE SENSEX Index Options",
    ),
    
    "BANKNIFTY": InstrumentConfig(
        name="BANKNIFTY",
        symbol="BANKNIFTY",
        security_id="99926000",
        exchange_segment="NSE_FO",
        instrument_type="OPTIDX",
        strike_rounding=100.0,  # 100pt strikes
        lot_size=1,
        spot_multiplier=1.0,
        capital_per_instrument=20000.0,
        risk_per_trade_pct=0.01,
        min_stop_loss_points=15.0,
        description="BANKNIFTY Index Options (Banking Sector)",
    ),
}


class InstrumentManager:
    """Manage instrument selection and configuration"""
    
    @staticmethod
    def get_instrument(key: str) -> Optional[InstrumentConfig]:
        """Get instrument config by key"""
        return INSTRUMENTS.get(key.upper())
    
    @staticmethod
    def list_instruments() -> Dict[int, tuple]:
        """Return numbered list of instruments for CLI"""
        instruments_list = []
        for i, (key, config) in enumerate(INSTRUMENTS.items(), 1):
            instruments_list.append((i, key, config.name, config.description))
        return {item[0]: item[1:] for item in instruments_list}
    
    @staticmethod
    def display_menu() -> str:
        """Generate formatted menu for CLI selection"""
        instruments = InstrumentManager.list_instruments()
        menu = "\n╔════════════════════════════════════════════════════╗\n"
        menu += "║  SELECT INSTRUMENT FOR ANALYSIS                   ║\n"
        menu += "╠════════════════════════════════════════════════════╣\n"
        
        for idx, (key, name, desc) in instruments.items():
            menu += f"║  {idx}. {name:12} → {desc:28} ║\n"
        
        menu += "╚════════════════════════════════════════════════════╝\n"
        return menu
    
    @staticmethod
    def select_from_cli() -> str:
        """Prompt user to select instrument via CLI"""
        while True:
            print(InstrumentManager.display_menu())
            try:
                choice = input("Enter your choice [1-{}]: ".format(len(INSTRUMENTS)))
                instruments = InstrumentManager.list_instruments()
                
                if int(choice) in instruments:
                    selected_key = instruments[int(choice)][0]
                    selected_config = InstrumentManager.get_instrument(selected_key)
                    print(f"\n✓ Selected: {selected_config.name}")
                    print(f"  Symbol: {selected_config.symbol} | Strike Rounding: {selected_config.strike_rounding}pts")
                    print("─"*60 + "\n")
                    return selected_key
                else:
                    print("❌ Invalid choice. Please try again.\n")
            except ValueError:
                print("❌ Please enter a valid number.\n")


# Export for easy import
__all__ = ['INSTRUMENTS', 'InstrumentConfig', 'InstrumentManager']
