"""
Signal generation module for options trading
Analyzes technical indicators and generates buy/sell signals for calls and puts
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from indicators.technical import TechnicalIndicators
from config.settings import TradingConfig

class SignalGenerator:
    """Main class for generating trading signals"""
    
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.indicators = TechnicalIndicators()
    
    def calculate_trade_setup(self, data: pd.DataFrame, signal_action: str, signal_strength: float, option_type: str = 'call', timeframe: str = 'daily') -> Dict:
        """
        Calculate entry/exit/stop-loss levels based on ATR
        
        Args:
            data: DataFrame with OHLCV data (must have ATR column)
            signal_action: 'buy' or 'sell'
            signal_strength: Signal strength (0-1)
            option_type: 'call' or 'put' (determines direction)
            timeframe: 'intraday' (5-15min scalps) or 'daily' (day trades)
        
        Returns:
            Dictionary with trade setup (entry, SL, target1, target2, risk/reward)
        """
        if 'ATR' not in data.columns or pd.isna(data['ATR'].iloc[-1]):
            logger.warning("ATR not available for trade setup calculation")
            return {}
        
        current_price = data['Close'].iloc[-1]
        atr = data['ATR'].iloc[-1]
        
        if atr == 0 or pd.isna(atr):
            return {}
        
        # Choose multipliers based on timeframe
        if timeframe.lower() == 'scalp':
            # ULTRA-TIGHT multipliers for 5-15 min scalping
            # Produces: SL 20-25pts, T1 50-65pts, T2 100-125pts
            sl_mult = self.config.ATR_MULTIPLIER_SL_SCALP
            t1_mult = self.config.ATR_MULTIPLIER_T1_SCALP
            t2_mult = self.config.ATR_MULTIPLIER_T2_SCALP
        elif timeframe.lower() == 'intraday':
            # Standard intraday for 2-4 hour holds
            sl_mult = self.config.ATR_MULTIPLIER_SL_INTRADAY
            t1_mult = self.config.ATR_MULTIPLIER_T1_INTRADAY
            t2_mult = self.config.ATR_MULTIPLIER_T2_INTRADAY
        else:
            # Daily trading multipliers
            sl_mult = self.config.ATR_MULTIPLIER_SL_DAILY
            t1_mult = self.config.ATR_MULTIPLIER_T1_DAILY
            t2_mult = self.config.ATR_MULTIPLIER_T2_DAILY
        
        # Calculate setup levels
        setup = {
            'entry': round(current_price, 2),
            'atr_value': round(atr, 2),
            'signal_strength': signal_strength,
            'signal_type': signal_action.upper(),
            'option_type': option_type.upper(),
            'timeframe': timeframe.upper()
        }
        
        # For CALL options: go UP
        if option_type.lower() == 'call':
            setup['stop_loss'] = round(current_price - (sl_mult * atr), 2)
            setup['target_1'] = round(current_price + (t1_mult * atr), 2)
            setup['target_2'] = round(current_price + (t2_mult * atr), 2)
            
        # For PUT options: go DOWN
        elif option_type.lower() == 'put':
            setup['stop_loss'] = round(current_price + (sl_mult * atr), 2)
            setup['target_1'] = round(current_price - (t1_mult * atr), 2)
            setup['target_2'] = round(current_price - (t2_mult * atr), 2)
        
        # Risk/Reward calculation
        if option_type.lower() == 'call':
            risk = setup['entry'] - setup['stop_loss']
            reward = setup['target_1'] - setup['entry']
        else:  # PUT
            risk = setup['stop_loss'] - setup['entry']
            reward = setup['entry'] - setup['target_1']
        
        if risk > 0:
            setup['risk_amount'] = round(risk, 2)
            setup['reward_amount'] = round(reward, 2)
            setup['risk_reward_ratio'] = round(reward / risk, 2)
        else:
            setup['risk_amount'] = 0
            setup['reward_amount'] = 0
            setup['risk_reward_ratio'] = 0
        
        return setup
    
    def analyze_trend(self, data: pd.DataFrame) -> Dict[str, str]:
        """
        Analyze overall trend using multiple EMAs with proper alignment check
        
        Args:
            data: DataFrame with technical indicators
        
        Returns:
            Dictionary with trend analysis
        """
        latest = data.iloc[-1]
        
        # EMA trend analysis
        ema_trends = {}
        price = latest['Close']
        ema_values = {}
        
        # Get EMA values
        for period in self.config.EMA_PERIODS:
            ema_col = f'EMA_{period}'
            if ema_col in data.columns and not pd.isna(latest[ema_col]):
                ema_value = latest[ema_col]
                ema_values[period] = ema_value
                
                if price > ema_value:
                    ema_trends[period] = 'bullish'
                elif price < ema_value:
                    ema_trends[period] = 'bearish'
                else:
                    ema_trends[period] = 'neutral'
        
        # Check EMA alignment (shorter EMAs should be above longer EMAs for bullish trend)
        ema_alignment_bullish = True
        ema_alignment_bearish = True
        
        available_periods = sorted([p for p in self.config.EMA_PERIODS if p in ema_values])
        
        if len(available_periods) >= 3:
            for i in range(len(available_periods) - 1):
                shorter_period = available_periods[i]
                longer_period = available_periods[i + 1]
                
                if ema_values[shorter_period] <= ema_values[longer_period]:
                    ema_alignment_bullish = False
                if ema_values[shorter_period] >= ema_values[longer_period]:
                    ema_alignment_bearish = False
        else:
            ema_alignment_bullish = False
            ema_alignment_bearish = False
        
        # Price position analysis
        short_term_bullish = all(
            ema_trends.get(p, 'neutral') == 'bullish' 
            for p in [5, 12, 20] if p in ema_trends
        )
        long_term_bullish = all(
            ema_trends.get(p, 'neutral') == 'bullish' 
            for p in [50, 200] if p in ema_trends
        )
        
        short_term_bearish = all(
            ema_trends.get(p, 'neutral') == 'bearish' 
            for p in [5, 12, 20] if p in ema_trends
        )
        
        # Overall trend determination
        if ema_alignment_bullish and short_term_bullish and long_term_bullish:
            overall_trend = 'strong_bullish'
        elif ema_alignment_bullish and short_term_bullish:
            overall_trend = 'bullish'
        elif ema_alignment_bearish and short_term_bearish:
            overall_trend = 'strong_bearish'
        elif short_term_bearish:
            overall_trend = 'bearish'
        else:
            overall_trend = 'neutral'
        
        return {
            'overall_trend': overall_trend,
            'ema_trends': ema_trends,
            'ema_values': ema_values,
            'ema_alignment_bullish': ema_alignment_bullish,
            'ema_alignment_bearish': ema_alignment_bearish,
            'price_above_vwap': price > latest.get('VWAP', price) if not pd.isna(latest.get('VWAP')) else False
        }
    
    def analyze_momentum(self, data: pd.DataFrame) -> Dict[str, any]:
        """
        Analyze momentum using RSI and MACD
        
        Args:
            data: DataFrame with technical indicators
        
        Returns:
            Dictionary with momentum analysis
        """
        latest = data.iloc[-1]
        
        # RSI analysis
        rsi = latest.get('RSI', 50)
        if rsi > self.config.RSI_OVERBOUGHT:
            rsi_signal = 'overbought'
        elif rsi < self.config.RSI_OVERSOLD:
            rsi_signal = 'oversold'
        else:
            rsi_signal = 'neutral'
        
        # MACD analysis
        macd = latest.get('MACD', 0)
        macd_signal = latest.get('MACD_Signal', 0)
        macd_histogram = latest.get('MACD_Histogram', 0)
        
        if macd > macd_signal and macd_histogram > 0:
            macd_trend = 'bullish'
        elif macd < macd_signal and macd_histogram < 0:
            macd_trend = 'bearish'
        else:
            macd_trend = 'neutral'
        
        return {
            'rsi_value': rsi,
            'rsi_signal': rsi_signal,
            'macd_trend': macd_trend,
            'macd_value': macd,
            'macd_signal_value': macd_signal,
            'macd_histogram': macd_histogram
        }
    
    def analyze_support_resistance(self, data: pd.DataFrame) -> Dict[str, any]:
        """
        Analyze current price relative to support/resistance levels
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Dictionary with S/R analysis
        """
        current_price = data['Close'].iloc[-1]
        
        # Calculate CPR levels
        cpr_levels = self.indicators.calculate_cpr(data)
        
        # Calculate dynamic S/R levels
        sr_levels = self.indicators.calculate_support_resistance(data)
        
        # Calculate previous highs/lows
        prev_levels = self.indicators.calculate_previous_high_low(data)
        
        # Determine position relative to key levels
        key_levels = []
        
        # Add CPR levels
        if cpr_levels:
            key_levels.extend([
                ('pivot', cpr_levels['pivot']),
                ('r1', cpr_levels['r1']),
                ('s1', cpr_levels['s1']),
                ('r2', cpr_levels['r2']),
                ('s2', cpr_levels['s2'])
            ])
        
        # Add dynamic levels
        key_levels.extend([('resistance', r) for r in sr_levels.get('resistance', [])])
        key_levels.extend([('support', s) for s in sr_levels.get('support', [])])
        
        # Find nearest support and resistance
        resistance_above = min([level[1] for level in key_levels if level[1] > current_price], default=None)
        support_below = max([level[1] for level in key_levels if level[1] < current_price], default=None)
        
        return {
            'current_price': current_price,
            'cpr_levels': cpr_levels,
            'dynamic_levels': sr_levels,
            'previous_levels': prev_levels,
            'nearest_resistance': resistance_above,
            'nearest_support': support_below,
            'distance_to_resistance': ((resistance_above - current_price) / current_price * 100) if resistance_above else None,
            'distance_to_support': ((current_price - support_below) / current_price * 100) if support_below else None
        }
    
    def generate_option_signals(self, data: pd.DataFrame) -> Dict[str, any]:
        """
        Generate call/put option signals based on comprehensive analysis
        
        Args:
            data: DataFrame with OHLCV data and indicators
        
        Returns:
            Dictionary with signal recommendations
        """
        # Calculate indicators if not present
        if 'EMA_5' not in data.columns:
            data = self.indicators.calculate_all_indicators(data, self.config)
        
        # Perform analysis
        trend_analysis = self.analyze_trend(data)
        momentum_analysis = self.analyze_momentum(data)
        sr_analysis = self.analyze_support_resistance(data)
        
        # Signal generation logic
        signals = {
            'timestamp': datetime.now(),
            'current_price': data['Close'].iloc[-1],
            'trend_analysis': trend_analysis,
            'momentum_analysis': momentum_analysis,
            'support_resistance': sr_analysis,
            'signals': {
                'call': {'action': 'hold', 'strength': 0, 'reasons': []},
                'put': {'action': 'hold', 'strength': 0, 'reasons': []}
            }
        }
        
        # Call option signal logic
        call_strength = 0
        call_reasons = []
        
        # Bullish trend signals (enhanced scoring)
        if trend_analysis['overall_trend'] == 'strong_bullish':
            call_strength += 0.35
            call_reasons.append('Strong bullish trend with EMA alignment')
        elif trend_analysis['overall_trend'] == 'bullish':
            call_strength += 0.25
            call_reasons.append('Bullish trend confirmed by EMAs')
        
        # EMA alignment bonus
        if trend_analysis.get('ema_alignment_bullish', False):
            call_strength += 0.15
            call_reasons.append('Perfect EMA alignment (bullish)')
        
        # Price above VWAP
        if trend_analysis['price_above_vwap']:
            call_strength += 0.1
            call_reasons.append('Price above VWAP')
        
        # RSI analysis (more nuanced)
        rsi_value = momentum_analysis['rsi_value']
        if rsi_value < 30:  # Oversold
            call_strength += 0.25
            call_reasons.append(f'RSI oversold ({rsi_value:.1f}) - bounce expected')
        elif 30 <= rsi_value <= 70:  # Neutral zone
            call_strength += 0.15
            call_reasons.append(f'RSI in neutral zone ({rsi_value:.1f}) - upside potential')
        elif rsi_value > 80:  # Very overbought
            call_strength -= 0.2
            call_reasons.append(f'RSI very overbought ({rsi_value:.1f}) - risk of pullback')
        
        # MACD bullish
        if momentum_analysis['macd_trend'] == 'bullish':
            call_strength += 0.2
            call_reasons.append('MACD showing bullish momentum')
        
        # Near support level
        if sr_analysis['distance_to_support'] and sr_analysis['distance_to_support'] < 2:
            call_strength += 0.15
            call_reasons.append('Price near support level')
        
        # Put option signal logic
        put_strength = 0
        put_reasons = []
        
        # Bearish trend signals (enhanced scoring)
        if trend_analysis['overall_trend'] == 'strong_bearish':
            put_strength += 0.35
            put_reasons.append('Strong bearish trend with EMA alignment')
        elif trend_analysis['overall_trend'] == 'bearish':
            put_strength += 0.25
            put_reasons.append('Bearish trend confirmed by EMAs')
        
        # EMA alignment bonus
        if trend_analysis.get('ema_alignment_bearish', False):
            put_strength += 0.15
            put_reasons.append('Perfect EMA alignment (bearish)')
        
        # Price below VWAP
        if not trend_analysis['price_above_vwap']:
            put_strength += 0.1
            put_reasons.append('Price below VWAP')
        
        # RSI analysis (more nuanced)
        if rsi_value > 70:  # Overbought
            put_strength += 0.25
            put_reasons.append(f'RSI overbought ({rsi_value:.1f}) - correction expected')
        elif 30 <= rsi_value <= 70:  # Neutral zone
            put_strength += 0.1
            put_reasons.append(f'RSI in neutral zone ({rsi_value:.1f}) - downside possible')
        elif rsi_value < 20:  # Very oversold
            put_strength -= 0.2
            put_reasons.append(f'RSI very oversold ({rsi_value:.1f}) - bounce likely')
        
        # MACD bearish
        if momentum_analysis['macd_trend'] == 'bearish':
            put_strength += 0.2
            put_reasons.append('MACD showing bearish momentum')
        
        # Near resistance level
        if sr_analysis['distance_to_resistance'] and sr_analysis['distance_to_resistance'] < 2:
            put_strength += 0.15
            put_reasons.append('Price near resistance level')
        
        # Determine actions based on strength
        # Note: Action is always 'buy' (we buy call or put options)
        # Option type (call/put) is determined by signal direction
        if call_strength >= self.config.MIN_SIGNAL_STRENGTH:
            signals['signals']['call']['action'] = 'buy'
        elif call_strength <= -self.config.MIN_SIGNAL_STRENGTH:
            signals['signals']['call']['action'] = 'sell'  # Sell call (bearish call spread)
        
        if put_strength >= self.config.MIN_SIGNAL_STRENGTH:
            signals['signals']['put']['action'] = 'buy'  # Buy put (bearish)
        elif put_strength <= -self.config.MIN_SIGNAL_STRENGTH:
            signals['signals']['put']['action'] = 'sell'  # Sell put (bullish)
        
        signals['signals']['call']['strength'] = call_strength
        signals['signals']['call']['reasons'] = call_reasons
        signals['signals']['put']['strength'] = put_strength
        signals['signals']['put']['reasons'] = put_reasons
        
        # Calculate trade setups (entry/SL/target) for active signals
        # Use INTRADAY multipliers (tight stops for 5-15 min scalping)
        if signals['signals']['call']['action'] in ['buy', 'sell']:
            signals['signals']['call']['setup'] = self.calculate_trade_setup(
                data, 
                signals['signals']['call']['action'],
                call_strength,
                option_type='call',
                timeframe='intraday'  # Tight multipliers for scalping
            )
        
        if signals['signals']['put']['action'] in ['buy', 'sell']:
            signals['signals']['put']['setup'] = self.calculate_trade_setup(
                data, 
                signals['signals']['put']['action'],
                put_strength,
                option_type='put',
                timeframe='intraday'  # Tight multipliers for scalping
            )
        
        return signals
    
    def format_signal_output(self, signals: Dict[str, any]) -> str:
        """
        Format signal output for display/notification
        
        Args:
            signals: Signal dictionary from generate_option_signals
        
        Returns:
            Formatted string with signal information
        """
        output = []
        output.append(f"🔔 Trading Signal - {signals['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"💰 Current Price: ₹{signals['current_price']:.2f}")
        output.append("")
        
        # Trend information
        trend = signals['trend_analysis']['overall_trend'].replace('_', ' ').title()
        ema_alignment = "✅" if signals['trend_analysis'].get('ema_alignment_bullish') else "❌" if signals['trend_analysis'].get('ema_alignment_bearish') else "⚪"
        output.append(f"📈 Trend: {trend} | EMA Alignment: {ema_alignment}")
        
        # Show EMA values
        ema_values = signals['trend_analysis'].get('ema_values', {})
        if ema_values:
            ema_str = " | ".join([f"EMA{p}: ₹{v:.0f}" for p, v in list(ema_values.items())[:3]])
            output.append(f"📊 EMAs: {ema_str}")
        
        # Momentum information
        rsi = signals['momentum_analysis']['rsi_value']
        rsi_status = "🔴 Overbought" if rsi > 70 else "🟢 Oversold" if rsi < 30 else "🟡 Neutral"
        output.append(f"📊 RSI: {rsi:.1f} ({rsi_status})")
        
        # Support/Resistance
        if signals['support_resistance']['nearest_support']:
            support = signals['support_resistance']['nearest_support']
            output.append(f"🔻 Nearest Support: ₹{support:.2f}")
        
        if signals['support_resistance']['nearest_resistance']:
            resistance = signals['support_resistance']['nearest_resistance']
            output.append(f"🔺 Nearest Resistance: ₹{resistance:.2f}")
        
        output.append("")
        output.append("📋 SIGNALS:")
        
        # Call signals
        call_signal = signals['signals']['call']
        if call_signal['action'] != 'hold':
            action_emoji = "🟢 BUY" if call_signal['action'] == 'buy' else "🔴 SELL"
            output.append(f"📞 CALL: {action_emoji} (Strength: {call_signal['strength']:.2f})")
            
            # Display trade setup if available
            if 'setup' in call_signal and call_signal['setup']:
                setup = call_signal['setup']
                output.append(f"   ├─ Entry: ₹{setup['entry']:.2f}")
                output.append(f"   ├─ Stop Loss: ₹{setup['stop_loss']:.2f} (Risk: ₹{setup['risk_amount']:.2f})")
                output.append(f"   ├─ Target 1: ₹{setup['target_1']:.2f}")
                output.append(f"   ├─ Target 2: ₹{setup['target_2']:.2f} (Reward: ₹{setup['reward_amount']:.2f})")
                output.append(f"   ├─ Risk/Reward: 1:{setup['risk_reward_ratio']:.2f}")
                output.append(f"   └─ ATR: ₹{setup['atr_value']:.2f}")
            
            for reason in call_signal['reasons'][:2]:  # Show top 2 reasons
                output.append(f"   • {reason}")
        
        # Put signals
        put_signal = signals['signals']['put']
        if put_signal['action'] != 'hold':
            action_emoji = "🟢 BUY" if put_signal['action'] == 'buy' else "🔴 SELL"
            output.append(f"📉 PUT: {action_emoji} (Strength: {put_signal['strength']:.2f})")
            
            # Display trade setup if available
            if 'setup' in put_signal and put_signal['setup']:
                setup = put_signal['setup']
                output.append(f"   ├─ Entry: ₹{setup['entry']:.2f}")
                output.append(f"   ├─ Stop Loss: ₹{setup['stop_loss']:.2f} (Risk: ₹{setup['risk_amount']:.2f})")
                output.append(f"   ├─ Target 1: ₹{setup['target_1']:.2f}")
                output.append(f"   ├─ Target 2: ₹{setup['target_2']:.2f} (Reward: ₹{setup['reward_amount']:.2f})")
                output.append(f"   ├─ Risk/Reward: 1:{setup['risk_reward_ratio']:.2f}")
                output.append(f"   └─ ATR: ₹{setup['atr_value']:.2f}")
            
            for reason in put_signal['reasons'][:2]:  # Show top 2 reasons
                output.append(f"   • {reason}")
        
        if call_signal['action'] == 'hold' and put_signal['action'] == 'hold':
            output.append("⏳ No clear signals - HOLD position")
        
        return "\n".join(output)