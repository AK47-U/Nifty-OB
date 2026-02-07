"""
Signal Alignment Checker - Validates if trading signals are consistent
Checks: Entry price, Target price, SL price, and Risk:Reward ratios
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from typing import Dict, Tuple


class SignalAlignmentChecker:
    """Validate trading signal consistency and alignment"""
    
    def __init__(self):
        self.nifty_lot_size = 65
        self.tick_size = 0.05  # NIFTY option tick size in rupees
    
    def check_signal_alignment(self, index_setup: Dict, option_setup: Dict, 
                               spot_price: float) -> Dict:
        """
        Check if index levels and option levels are aligned
        
        Args:
            index_setup: Dict with index entry, target, SL
            option_setup: Dict with option entry premium, target premium, SL premium
            spot_price: Current spot price
        
        Returns:
            Dict with validation status and differences
        """
        
        report = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'details': {}
        }
        
        # Extract values
        index_entry = index_setup['entry']
        index_target = index_setup['exit_target']
        index_sl = index_setup['stoploss']
        index_direction = index_setup['direction']
        
        option_entry_premium = option_setup['entry_premium']
        option_target_premium = option_setup['target_premium']
        option_sl_premium = option_setup['sl_premium']
        option_strike = option_setup['strike']
        option_type = option_setup['option_type']
        
        # ========== VALIDATION 1: Entry Price Alignment ==========
        logger.info("\n" + "="*70)
        logger.info("🔍 VALIDATION 1: ENTRY PRICE ALIGNMENT")
        logger.info("="*70)
        
        entry_diff = abs(index_entry - spot_price)
        entry_pct = (entry_diff / spot_price) * 100
        
        logger.info(f"\nSpot Price:         {spot_price:.2f}")
        logger.info(f"Index Entry Level:  {index_entry:.2f}")
        logger.info(f"Difference:         {entry_diff:.2f} points ({entry_pct:.2f}%)")
        
        if entry_diff > 50:
            report['warnings'].append(f"Entry {entry_diff:.2f}pts away from spot - may miss entry")
            logger.warning(f"⚠️  Entry is {entry_diff:.2f} points away from current spot")
        else:
            logger.info(f"✅ Entry is close to spot ({entry_diff:.2f}pts)")
        
        report['details']['entry_alignment'] = {
            'spot': spot_price,
            'entry': index_entry,
            'distance_points': entry_diff,
            'distance_pct': entry_pct
        }
        
        # ========== VALIDATION 2: Target Alignment ==========
        logger.info("\n" + "="*70)
        logger.info("🎯 VALIDATION 2: TARGET PRICE ALIGNMENT")
        logger.info("="*70)
        
        # Calculate expected index points from option premium change
        index_profit_points = index_target - index_entry
        option_profit_rupees = option_target_premium - option_entry_premium
        option_profit_in_index_points = option_profit_rupees * 5  # Approx conversion (rough)
        
        logger.info(f"\nIndex Profit Target: {index_profit_points:.2f} points")
        logger.info(f"  From: {index_entry:.2f} → To: {index_target:.2f}")
        logger.info(f"\nOption Profit Target: ₹{option_profit_rupees:.2f} per contract")
        logger.info(f"  From: ₹{option_entry_premium:.2f} → To: ₹{option_target_premium:.2f}")
        logger.info(f"  In Rupees: +₹{option_profit_rupees * self.nifty_lot_size:.2f} total")
        
        # Check reasonableness
        if index_profit_points < 50:
            report['warnings'].append(f"Target profit only {index_profit_points:.2f}pts - may be too conservative")
            logger.warning(f"⚠️  Target profit is only {index_profit_points:.2f} points (conservative)")
        elif index_profit_points > 300:
            report['warnings'].append(f"Target profit {index_profit_points:.2f}pts - may be unrealistic")
            logger.warning(f"⚠️  Target profit {index_profit_points:.2f}pts seems unrealistic")
        else:
            logger.info(f"✅ Target profit {index_profit_points:.2f}pts is reasonable")
        
        report['details']['target_alignment'] = {
            'index_points': index_profit_points,
            'option_rupees': option_profit_rupees,
            'total_rupees': option_profit_rupees * self.nifty_lot_size,
            'target_price': index_target
        }
        
        # ========== VALIDATION 3: Stop Loss Alignment ==========
        logger.info("\n" + "="*70)
        logger.info("🛑 VALIDATION 3: STOP LOSS ALIGNMENT")
        logger.info("="*70)
        
        index_risk_points = index_entry - index_sl if index_direction == 'BUY' else index_sl - index_entry
        option_risk_rupees = option_entry_premium - option_sl_premium
        
        logger.info(f"\nIndex Risk (SL): {index_risk_points:.2f} points")
        logger.info(f"  Entry: {index_entry:.2f} → SL: {index_sl:.2f}")
        logger.info(f"\nOption Risk (SL): ₹{option_risk_rupees:.2f} per contract")
        logger.info(f"  Entry: ₹{option_entry_premium:.2f} → SL: ₹{option_sl_premium:.2f}")
        logger.info(f"  In Rupees: -₹{option_risk_rupees * self.nifty_lot_size:.2f} total")
        
        if index_risk_points > index_profit_points * 1.5:
            report['errors'].append(f"Risk {index_risk_points:.2f}pts > 1.5x Profit - poor R:R")
            logger.error(f"❌ Risk {index_risk_points:.2f}pts is too high vs profit {index_profit_points:.2f}pts")
        else:
            logger.info(f"✅ Risk {index_risk_points:.2f}pts is reasonable vs profit {index_profit_points:.2f}pts")
        
        report['details']['sl_alignment'] = {
            'index_risk_points': index_risk_points,
            'option_risk_rupees': option_risk_rupees,
            'total_risk_rupees': option_risk_rupees * self.nifty_lot_size,
            'sl_price': index_sl
        }
        
        # ========== VALIDATION 4: Risk:Reward Ratio ==========
        logger.info("\n" + "="*70)
        logger.info("📊 VALIDATION 4: RISK:REWARD RATIO")
        logger.info("="*70)
        
        index_rr = index_profit_points / index_risk_points if index_risk_points > 0 else 0
        option_rr = option_profit_rupees / option_risk_rupees if option_risk_rupees > 0 else 0
        
        logger.info(f"\nIndex R:R Ratio:  1:{index_rr:.2f}")
        logger.info(f"Option R:R Ratio: 1:{option_rr:.2f}")
        
        if index_rr < 1.0:
            report['errors'].append(f"Index R:R {index_rr:.2f} < 1.0 - AVOID!")
            logger.error(f"❌ Index Risk:Reward {index_rr:.2f} is unfavorable - DO NOT TRADE")
        elif index_rr < 1.2:
            report['warnings'].append(f"Index R:R {index_rr:.2f} < 1.2 - Below minimum threshold")
            logger.warning(f"⚠️  Index Risk:Reward {index_rr:.2f} is below 1.2 threshold")
        else:
            logger.info(f"✅ Index Risk:Reward {index_rr:.2f} is good")
        
        report['details']['risk_reward'] = {
            'index_ratio': index_rr,
            'option_ratio': option_rr,
            'is_acceptable': index_rr >= 1.2
        }
        
        # ========== VALIDATION 5: Direction & Strike ==========
        logger.info("\n" + "="*70)
        logger.info("📈 VALIDATION 5: DIRECTION & OPTION STRIKE")
        logger.info("="*70)
        
        logger.info(f"\nSignal Direction:    {index_direction}")
        logger.info(f"Option Type:         {option_type}")
        logger.info(f"Option Strike:       {option_strike}")
        
        # Check if direction matches option type
        direction_match = (index_direction == 'BUY' and option_type == 'CE') or \
                         (index_direction == 'SELL' and option_type == 'PE')
        
        if direction_match:
            logger.info(f"✅ Direction matches option type (BUY=CE, SELL=PE)")
        else:
            report['errors'].append(f"Direction {index_direction} doesn't match {option_type}")
            logger.error(f"❌ Direction mismatch: {index_direction} signal but {option_type} option")
        
        # Check if strike is ATM (within 50 points)
        strike_distance = abs(option_strike - spot_price)
        if strike_distance <= 50:
            logger.info(f"✅ Strike {option_strike} is ATM (within 50pts of spot {spot_price:.2f})")
        else:
            report['warnings'].append(f"Strike {option_strike} is {strike_distance:.0f}pts away from spot")
            logger.warning(f"⚠️  Strike {option_strike} is {strike_distance:.0f}pts away from ATM")
        
        report['details']['direction_strike'] = {
            'direction': index_direction,
            'option_type': option_type,
            'strike': option_strike,
            'strike_distance': strike_distance,
            'is_atm': strike_distance <= 50
        }
        
        # ========== FINAL VERDICT ==========
        logger.info("\n" + "="*70)
        logger.info("✅ FINAL VERDICT")
        logger.info("="*70)
        
        report['is_valid'] = len(report['errors']) == 0
        
        if report['is_valid']:
            logger.info("\n✅ SIGNAL IS VALID - All checks passed")
            if report['warnings']:
                logger.warning(f"\n⚠️  Warnings ({len(report['warnings'])}):")
                for w in report['warnings']:
                    logger.warning(f"   - {w}")
        else:
            logger.error(f"\n❌ SIGNAL IS INVALID - {len(report['errors'])} errors found:")
            for e in report['errors']:
                logger.error(f"   - {e}")
        
        return report
    
    def format_alignment_report(self, report: Dict, signal_action: str) -> str:
        """Format alignment report for display"""
        
        status = "✅ VALID" if report['is_valid'] else "❌ INVALID"
        
        output = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SIGNAL ALIGNMENT VALIDATION REPORT                     ║
╚═══════════════════════════════════════════════════════════════════════════╝

📊 OVERALL STATUS: {status}
Trading Action: {signal_action}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 ENTRY ALIGNMENT:
   Spot Price:           {report['details']['entry_alignment']['spot']:.2f}
   Entry Level:          {report['details']['entry_alignment']['entry']:.2f}
   Distance:             {report['details']['entry_alignment']['distance_points']:.2f}pts ({report['details']['entry_alignment']['distance_pct']:.2f}%)

🎯 TARGET ALIGNMENT:
   Target Price:         {report['details']['target_alignment']['target_price']:.2f}
   Profit (Index):       +{report['details']['target_alignment']['index_points']:.2f} points
   Profit (Option):      +₹{report['details']['target_alignment']['total_rupees']:.2f}

🛑 STOP LOSS ALIGNMENT:
   SL Price:             {report['details']['sl_alignment']['sl_price']:.2f}
   Risk (Index):         {report['details']['sl_alignment']['index_risk_points']:.2f} points
   Risk (Option):        -₹{report['details']['sl_alignment']['total_risk_rupees']:.2f}

📈 RISK:REWARD RATIO:
   Index R:R:            1:{report['details']['risk_reward']['index_ratio']:.2f}
   Option R:R:           1:{report['details']['risk_reward']['option_ratio']:.2f}
   Status:               {"✅ Good" if report['details']['risk_reward']['is_acceptable'] else "❌ Poor"}

📋 DIRECTION & OPTION:
   Signal Direction:     {report['details']['direction_strike']['direction']}
   Option Type:          {report['details']['direction_strike']['option_type']}
   Strike:               {report['details']['direction_strike']['strike']}
   Strike Distance:      {report['details']['direction_strike']['strike_distance']:.0f}pts from spot
   Status:               {"✅ ATM" if report['details']['direction_strike']['is_atm'] else "⚠️  Not ATM"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 ISSUES FOUND: {len(report['errors']) + len(report['warnings'])}
"""
        
        if report['errors']:
            output += f"\n❌ ERRORS ({len(report['errors'])}):\n"
            for e in report['errors']:
                output += f"   • {e}\n"
        
        if report['warnings']:
            output += f"\n⚠️  WARNINGS ({len(report['warnings'])}):\n"
            for w in report['warnings']:
                output += f"   • {w}\n"
        
        if report['is_valid']:
            output += "\n✅ SIGNAL IS READY TO TRADE"
        else:
            output += "\n❌ DO NOT TRADE - Fix issues first"
        
        output += "\n" + "="*77 + "\n"
        
        return output


def main():
    """Test signal alignment checker"""
    checker = SignalAlignmentChecker()
    
    # Sample data from monitor output
    spot_price = 25762.85
    
    index_setup = {
        'entry': 25775.73,
        'exit_target': 25921.99,
        'stoploss': 25666.04,
        'direction': 'BUY'
    }
    
    option_setup = {
        'strike': 25750,
        'entry_premium': 53.81,
        'target_premium': 73.81,
        'sl_premium': 38.81,
        'option_type': 'CE'
    }
    
    # Check alignment
    report = checker.check_signal_alignment(index_setup, option_setup, spot_price)
    
    # Display report
    print(checker.format_alignment_report(report, "BUY"))


if __name__ == "__main__":
    main()
