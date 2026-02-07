"""
Continuous Trading Levels Monitor with Adaptive Learning System
Fetches levels, applies real-time filters, and sends alerts to Telegram
All failures analyzed and parameters auto-tuned
"""
import time
import sys
import asyncio
import json
from datetime import datetime
import pytz
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ml_models.trading_levels_generator import TradingLevelsGenerator
from ml_models.data_extractor import DataExtractor
from ml_models.real_option_fetcher import RealTimeOptionFetcher
from ml_models.level_tracker import LevelTracker
from intelligence.trend_analyzer import TrendAnalyzer
from intelligence.entry_quality_filter import EntryQualityFilter
from intelligence.failure_analyzer import FailureAnalyzer
from intelligence.parameter_learner import ParameterLearner
from intelligence.position_sizer import PositionSizer
from dhan_api_client import DhanAPIClient
from telegram_notifier import TelegramNotifier
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")

# IST Timezone
IST = pytz.timezone('Asia/Kolkata')


def is_market_hours():
    """Check if current time is during market hours (9:15 AM - 3:30 PM IST)"""
    now = datetime.now(IST)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Market is closed on weekends
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    return market_open <= now <= market_close


def display_levels_loop():
    """Continuously fetch levels with all filters applied"""
    
    # Initialize all components
    generator = TradingLevelsGenerator()
    extractor = DataExtractor()
    option_fetcher = RealTimeOptionFetcher()
    
    # Initialize tracking & analysis
    tracker = LevelTracker()  # Uses trading_metrics.db
    trend_analyzer = TrendAnalyzer()
    entry_filter = EntryQualityFilter()
    failure_analyzer = FailureAnalyzer()
    parameter_learner = ParameterLearner()
    position_sizer = PositionSizer()
    
    # Initialize Telegram
    from telegram_config import BOT_TOKEN, CHAT_ID
    telegram = TelegramNotifier(BOT_TOKEN, CHAT_ID)
    
    logger.info("🚀 Starting Trading Levels Monitor with Adaptive Learning")
    logger.info("📊 Updates every 15 minutes during market hours (9:15 AM - 3:30 PM IST)")
    logger.info(f"📱 Telegram: {'✅ ENABLED' if telegram.enabled else '❌ DISABLED'}")
    logger.info("🤖 Real-time Filters: Trend + Entry Quality + Failure Detection + Parameter Learning")
    logger.info("💰 Capital Protection: ₹15K budget, ₹900 daily loss limit, 2 max trades/day")
    logger.info("Press Ctrl+C to stop\n")
    
    iteration = 0
    
    while True:
        iteration += 1
        
        try:
            # Check if market is open
            if not is_market_hours():
                now = datetime.now(IST)
                logger.warning(f"⏰ Market closed. Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
                logger.info("⏳ Waiting for market hours (9:15 AM - 3:30 PM IST)...")
                time.sleep(60)
                continue
            
            logger.info(f"\n{'='*100}")
            logger.info(f"📡 ITERATION #{iteration} - {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
            logger.info(f"{'='*100}\n")
            
            # ==================== DATA FETCH ====================
            logger.info("🔄 Fetching 5 days of 5-min NIFTY candles...")
            df = extractor.fetch_historical_data(days=5)
            if df is None or len(df) < 100:
                logger.error("❌ Insufficient data. Retrying in 30s...")
                time.sleep(30)
                continue
            logger.info(f"✓ Got {len(df)} candles\n")
            
            # ==================== ML PREDICTION ====================
            logger.info("🧠 Running ML prediction (78.4% accuracy - profitable moves)...")
            levels = generator.calculate_levels(df)
            logger.info(f"✓ Prediction: {levels['direction']} @ {levels['confidence']:.1f}% confidence | Action: {levels['action']}\n")
            
            # ==================== POSITION SIZING CHECK ====================
            logger.info("💰 Checking position sizing & capital constraints...")
            can_trade, size_reason = position_sizer.can_take_trade()
            logger.info(f"   {size_reason}")
            
            if not can_trade:
                logger.warning(f"❌ BLOCKED: Position sizing constraint")
                levels['action'] = 'WAIT'
                levels['block_reason'] = size_reason
                logger.info(f"\n{'='*100}\n")
                time.sleep(900)
                continue
            
            # Validate calculated SL
            sl_valid, sl_reason = position_sizer.validate_position_sizing(levels['risk_per_trade'])
            logger.info(f"   {sl_reason}")
            
            if not sl_valid:
                logger.warning(f"❌ BLOCKED: SL exceeds capital limits")
                levels['action'] = 'WAIT'
                levels['block_reason'] = sl_reason
                logger.info(f"\n{'='*100}\n")
                time.sleep(900)
                continue
            
            logger.info("")
            
            # ==================== TREND FILTER ====================
            logger.info("📈 Analyzing 15-min trend (UP/DOWN/NEUTRAL)...")
            trend_data = trend_analyzer.get_15min_trend(df)
            logger.info(f"   Trend: {trend_data['trend']} (strength: {trend_data['strength']:.1%})")
            if trend_data['fast_ema'] and trend_data['slow_ema']:
                logger.info(f"   Last close: {trend_data['last_close']:.2f}, Fast EMA: {trend_data['fast_ema']:.2f}, Slow EMA: {trend_data['slow_ema']:.2f}")
            
            # Check alignment
            is_aligned = trend_analyzer.is_aligned_with_trend(levels['direction'], trend_data)
            if is_aligned:
                logger.info(f"   ✅ {levels['direction']} signal aligned with {trend_data['trend']} trend")
            else:
                logger.warning(f"   ⚠️ {levels['direction']} signal AGAINST {trend_data['trend']} trend - HIGH RISK")
            
            trend_multiplier = trend_analyzer.get_trend_strength_multiplier(trend_data)
            
            logger.info("")
            
            # ==================== ENTRY QUALITY FILTER ====================
            logger.info("🎯 Checking entry quality (Support/Resistance proximity)...")
            sr_levels = entry_filter.get_support_resistance_levels(df.to_dict('records'))
            if sr_levels:
                logger.info(f"   Support: {sr_levels['support']:.2f}, Resistance: {sr_levels['resistance']:.2f}, Range: {sr_levels['range']:.2f}")
            
            entry_quality = entry_filter.evaluate_entry_quality(
                levels['entry'],
                levels['direction'],
                sr_levels
            )
            logger.info(f"   Entry Quality: {entry_quality['quality']} - {entry_quality['reason']}")
            is_quality_ok = entry_filter.is_quality_acceptable(entry_quality)
            
            logger.info("")
            
            # ==================== FAILURE ANALYSIS & PATTERN DETECTION ====================
            logger.info("🔍 Analyzing recent failures (last 2 hours)...")
            recent_failures = failure_analyzer.get_recent_failures(hours=2)
            failure_analysis = failure_analyzer.identify_failure_patterns(recent_failures)
            
            logger.info(f"   Total failures: {failure_analysis['total_failures']}")
            logger.info(f"   Primary pattern: {failure_analysis['primary_reason']}")
            logger.info(f"   Reason breakdown: Counter-trend={failure_analysis['reason_distribution']['counter_trend']}, " +
                       f"Low-quality={failure_analysis['reason_distribution']['low_quality']}, " +
                       f"Low-confidence={failure_analysis['reason_distribution']['low_confidence']}, " +
                       f"Volatility={failure_analysis['reason_distribution']['volatility']}")
            
            # Get recommendations
            recommendations = failure_analyzer.get_failure_recommendations(failure_analysis)
            should_pause, pause_reason = parameter_learner.should_pause_trading(failure_analysis)
            
            if should_pause:
                logger.error(f"\n❌ CIRCUIT BREAKER: {pause_reason}")
                levels['action'] = 'WAIT'
                levels['block_reason'] = pause_reason
                logger.info(f"\n{'='*100}\n")
                time.sleep(900)
                continue
            
            if recommendations:
                logger.info(f"   📋 Recommendations:")
                for rec in recommendations:
                    logger.info(f"      {rec}")
            
            # Learn and adjust parameters
            adjustment_result = parameter_learner.learn_and_adjust(failure_analysis, recommendations)
            current_params = adjustment_result['adjusted_params']
            if adjustment_result['changes_made']:
                logger.info(f"   🔧 Parameters adjusted: {len(adjustment_result['changes_made'])} changes")
            
            logger.info("")
            
            # ==================== SIGNAL DECISION ====================
            # Build decision logic based on current parameters
            confidence = levels['confidence']
            
            # Apply trend strength multiplier
            if trend_data['trend'] != 'NEUTRAL' and is_aligned:
                confidence = confidence * trend_multiplier
            elif not is_aligned:
                confidence = confidence * 0.5  # Penalize counter-trend signals
            
            # Check all filters
            filters_passed = {
                'confidence': confidence >= current_params['min_confidence'],
                'rr_ratio': levels['risk_reward_ratio'] >= current_params['min_rr_ratio'],
                'trend': not current_params['trend_alignment_required'] or is_aligned,
                'entry_quality': not current_params['entry_quality_required'] or is_quality_ok,
                'position_size': can_trade and sl_valid,
                'not_paused': not should_pause
            }
            
            # Block if in restricted market hour
            market_hour = datetime.now(IST).hour
            if market_hour in current_params['block_hours']:
                filters_passed['market_hour'] = False
                logger.info(f"⏱️  Market hour {market_hour}:00 is blocked (from pattern learning)")
            else:
                filters_passed['market_hour'] = True
            
            all_passed = all(filters_passed.values())
            
            logger.info("🔐 FILTER RESULTS:")
            for filter_name, passed in filters_passed.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                logger.info(f"   {filter_name.upper()}: {status}")
            
            logger.info("")
            
            # ==================== FINAL ACTION ====================
            if all_passed and levels['confidence'] >= 60:
                logger.info(f"✅ ALL FILTERS PASSED - SIGNAL READY TO TRADE")
                logger.info(f"   {levels['direction']} signal with {confidence:.1f}% confidence")
                action = levels['direction']
            else:
                logger.warning(f"⏸️  SIGNAL BLOCKED - One or more filters failed")
                action = 'WAIT'
            
            levels['action'] = action
            levels['filters_state'] = filters_passed
            levels['adjusted_confidence'] = confidence
            
            logger.info("")
            
            # ==================== LOG SIGNAL ====================
            tracker.log_signal(levels)
            
            # ==================== CHECK PREVIOUS OUTCOMES ====================
            logger.info("📊 Checking previous signal outcomes...")
            tracker.check_outcomes(df)
            logger.info("")
            
            # ==================== OPTION CHAIN ====================
            if action in ['BUY', 'SELL']:
                logger.info("🔍 Fetching REAL option premiums...")
                quote = option_fetcher.fetch_option_chain_real(
                    spot_price=levels['current_price'],
                    direction=levels['direction']
                )
                
                if quote:
                    option_setup = option_fetcher.calculate_option_levels(
                        quote=quote,
                        direction=levels['direction']
                    )
                    logger.info(option_fetcher.format_option_setup(option_setup))
                
                logger.info("")
            
            # ==================== TELEGRAM NOTIFICATION ====================
            if telegram.enabled:
                try:
                    signal_data = {
                        'ml': {
                            'direction': levels['direction'],
                            'confidence': levels['confidence'],
                            'adjusted_confidence': confidence,
                            'up_probability': levels.get('up_prob', 0),
                            'down_probability': levels.get('down_prob', 0)
                        },
                        'current_price': levels['current_price'],
                        'entry': levels['entry'],
                        'target': levels['exit_target'],
                        'sl': levels['stoploss'],
                        'rr': levels['risk_reward_ratio'],
                        'action': action,
                        'block_reason': levels.get('block_reason'),
                        'trend': trend_data['trend'],
                        'entry_quality': entry_quality['quality'],
                        'timestamp': datetime.now(IST)
                    }
                    
                    asyncio.run(telegram.send_trading_signal(signal_data))
                    logger.info("✅ Telegram notification sent")
                except Exception as e:
                    logger.warning(f"⚠️ Telegram send failed: {str(e)}")
            
            logger.info("")
            
            # ==================== DISPLAY FINAL SUMMARY ====================
            logger.info(f"{'━'*100}")
            logger.info(f"💼 SETUP SUMMARY:")
            logger.info(f"   Action:              {action}")
            logger.info(f"   Direction:           {levels['direction']}")
            logger.info(f"   Confidence:          {levels['confidence']:.1f}% → {confidence:.1f}% (adjusted)")
            logger.info(f"   Entry Price:         {levels['entry']:.2f}")
            logger.info(f"   Target:              {levels['exit_target']:.2f}")
            logger.info(f"   Stop Loss:           {levels['stoploss']:.2f}")
            logger.info(f"   Risk/Reward:         1:{levels['risk_reward_ratio']:.2f}")
            logger.info(f"   Trend:               {trend_data['trend']}")
            logger.info(f"   Entry Quality:       {entry_quality['quality']}")
            logger.info(f"{'━'*100}\n")
            
            # Show capital status
            pos_limits = position_sizer.get_position_limits()
            logger.info(f"💰 CAPITAL STATUS:")
            logger.info(f"   Today's Loss:        ₹{pos_limits['today_loss']:.0f} / ₹{pos_limits['max_daily_loss']:.0f}")
            logger.info(f"   Today's Trades:      {pos_limits['today_trades']} / {pos_limits['max_trades_per_day']}")
            logger.info(f"   Remaining Loss Cap:  ₹{pos_limits['remaining_loss']:.0f}")
            logger.info(f"   Remaining SL Points: {pos_limits['remaining_sl_points']:.1f}\n")
            
            # Schedule next update
            logger.info(f"⏲️  Next update in 15 minutes")
            logger.info(f"{'='*100}\n")
            
            # Wait 15 minutes
            time.sleep(900)
            
        except KeyboardInterrupt:
            logger.warning("\n\n🛑 Levels Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            logger.info("⏳ Retrying in 30 seconds...\n")
            time.sleep(30)


def main():
    """Main entry point"""
    logger.info("\n" + "="*100)
    logger.info("NIFTY TRADING LEVELS MONITOR - WITH ADAPTIVE LEARNING SYSTEM")
    logger.info("="*100 + "\n")
    
    try:
        display_levels_loop()
    except KeyboardInterrupt:
        logger.info("\n✓ Monitor stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
