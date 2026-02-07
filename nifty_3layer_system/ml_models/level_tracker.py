"""
Level Tracker - Track success/failure of generated trading levels
Logs each signal and monitors whether target or SL hit first
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from loguru import logger
import pytz

IST = pytz.timezone('Asia/Kolkata')


class LevelTracker:
    """Track and analyze trading level outcomes"""
    
    def __init__(self, db_path: str = "data/trading_metrics.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
    
    def _initialize_database(self):
        """Create tracking table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence REAL NOT NULL,
            
            -- Price levels
            current_price REAL NOT NULL,
            entry_price REAL NOT NULL,
            target_price REAL NOT NULL,
            sl_price REAL NOT NULL,
            
            -- Risk metrics
            atr REAL NOT NULL,
            risk_points REAL NOT NULL,
            reward_points REAL NOT NULL,
            rr_ratio REAL NOT NULL,
            
            -- Context
            market_hour INTEGER NOT NULL,
            
            -- Outcome (filled later)
            outcome TEXT,
            outcome_price REAL,
            outcome_time TEXT,
            duration_minutes INTEGER,
            pnl_points REAL,
            
            -- Analysis
            reason_for_sl TEXT,
            market_volatility_at_exit REAL,
            
            UNIQUE(timestamp, direction)
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"✓ Level tracker database initialized: {self.db_path}")
    
    def log_signal(self, levels: Dict) -> bool:
        """
        Log a new trading signal
        
        Args:
            levels: Dict from TradingLevelsGenerator.calculate_levels()
        
        Returns:
            True if logged successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
            INSERT OR IGNORE INTO level_signals (
                timestamp, direction, action, confidence,
                current_price, entry_price, target_price, sl_price,
                atr, risk_points, reward_points, rr_ratio,
                market_hour
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                levels['direction'],
                levels['action'],
                levels['confidence'],
                levels['current_price'],
                levels['entry'],
                levels['exit_target'],
                levels['stoploss'],
                levels['atr'],
                levels['risk_per_trade'],
                levels['reward_per_trade'],
                levels['risk_reward_ratio'],
                datetime.now(IST).hour
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✓ Signal logged: {levels['direction']} @ {levels['current_price']:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log signal: {str(e)}")
            return False
    
    def check_outcomes(self, current_df: pd.DataFrame):
        """
        Check all pending signals to see if target or SL hit
        
        Args:
            current_df: DataFrame with recent OHLC data
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get all pending signals (no outcome yet)
            pending = pd.read_sql_query("""
                SELECT * FROM level_signals 
                WHERE outcome IS NULL 
                AND timestamp >= datetime('now', '-24 hours')
            """, conn)
            
            if pending.empty:
                conn.close()
                return
            
            for _, signal in pending.iterrows():
                signal_time = pd.to_datetime(signal['timestamp'])
                
                # Get candles after signal
                future_candles = current_df[current_df.index > signal_time]
                
                if future_candles.empty:
                    continue
                
                # Check if target or SL hit
                outcome = self._check_hit(signal, future_candles)
                
                if outcome:
                    self._update_outcome(conn, signal['id'], outcome)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to check outcomes: {str(e)}")
    
    def _check_hit(self, signal: pd.Series, candles: pd.DataFrame) -> Optional[Dict]:
        """Check if target or SL was hit first"""
        
        direction = signal['direction']
        target = signal['target_price']
        sl = signal['sl_price']
        entry = signal['entry_price']
        
        for idx, candle in candles.iterrows():
            # Check if target hit
            if direction == 'BUY':
                if candle['high'] >= target:
                    return {
                        'outcome': 'TARGET',
                        'price': target,
                        'time': idx,
                        'duration': (idx - pd.to_datetime(signal['timestamp'])).total_seconds() / 60,
                        'pnl': target - entry
                    }
                elif candle['low'] <= sl:
                    return {
                        'outcome': 'SL',
                        'price': sl,
                        'time': idx,
                        'duration': (idx - pd.to_datetime(signal['timestamp'])).total_seconds() / 60,
                        'pnl': sl - entry,
                        'reason': self._analyze_sl_reason(signal, candle)
                    }
            else:  # SELL
                if candle['low'] <= target:
                    return {
                        'outcome': 'TARGET',
                        'price': target,
                        'time': idx,
                        'duration': (idx - pd.to_datetime(signal['timestamp'])).total_seconds() / 60,
                        'pnl': entry - target
                    }
                elif candle['high'] >= sl:
                    return {
                        'outcome': 'SL',
                        'price': sl,
                        'time': idx,
                        'duration': (idx - pd.to_datetime(signal['timestamp'])).total_seconds() / 60,
                        'pnl': entry - sl,
                        'reason': self._analyze_sl_reason(signal, candle)
                    }
        
        return None
    
    def _analyze_sl_reason(self, signal: pd.Series, exit_candle: pd.Series) -> str:
        """Analyze why SL was hit"""
        reasons = []
        
        # Check volatility spike
        signal_atr = signal['atr']
        exit_range = exit_candle['high'] - exit_candle['low']
        
        if exit_range > signal_atr * 1.5:
            reasons.append("High volatility spike")
        
        # Check if confidence was low
        if signal['confidence'] < 65:
            reasons.append("Low confidence signal")
        
        # Check market hour
        hour = signal['market_hour']
        if hour < 10 or hour > 14:
            reasons.append("Poor timing (outside prime hours)")
        
        # Check R:R ratio
        if signal['rr_ratio'] < 1.5:
            reasons.append("Poor R:R ratio")
        
        return '; '.join(reasons) if reasons else "Normal market reversal"
    
    def _update_outcome(self, conn: sqlite3.Connection, signal_id: int, outcome: Dict):
        """Update signal with outcome"""
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE level_signals 
        SET outcome = ?,
            outcome_price = ?,
            outcome_time = ?,
            duration_minutes = ?,
            pnl_points = ?,
            reason_for_sl = ?
        WHERE id = ?
        """, (
            outcome['outcome'],
            outcome['price'],
            outcome['time'].strftime('%Y-%m-%d %H:%M:%S'),
            int(outcome['duration']),
            outcome['pnl'],
            outcome.get('reason', None),
            signal_id
        ))
        
        conn.commit()
        logger.info(f"✓ Outcome recorded: {outcome['outcome']} after {int(outcome['duration'])} min")
    
    def get_statistics(self, days: int = 7) -> Dict:
        """Get success rate statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            df = pd.read_sql_query(f"""
                SELECT * FROM level_signals 
                WHERE timestamp >= '{cutoff}'
                AND outcome IS NOT NULL
            """, conn)
            
            conn.close()
            
            if df.empty:
                return {'message': 'No completed signals yet'}
            
            total = len(df)
            wins = len(df[df['outcome'] == 'TARGET'])
            losses = len(df[df['outcome'] == 'SL'])
            
            avg_win_duration = df[df['outcome'] == 'TARGET']['duration_minutes'].mean()
            avg_loss_duration = df[df['outcome'] == 'SL']['duration_minutes'].mean()
            
            return {
                'total_signals': total,
                'wins': wins,
                'losses': losses,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'avg_win_duration_min': avg_win_duration,
                'avg_loss_duration_min': avg_loss_duration,
                'avg_pnl_per_trade': df['pnl_points'].mean(),
                'total_pnl': df['pnl_points'].sum(),
                'best_hour': df.groupby('market_hour')['pnl_points'].mean().idxmax(),
                'worst_hour': df.groupby('market_hour')['pnl_points'].mean().idxmin()
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {'error': str(e)}
    
    def get_sl_analysis(self) -> pd.DataFrame:
        """Get analysis of why SL was hit"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            df = pd.read_sql_query("""
                SELECT reason_for_sl, COUNT(*) as count,
                       AVG(confidence) as avg_confidence,
                       AVG(rr_ratio) as avg_rr
                FROM level_signals
                WHERE outcome = 'SL' AND reason_for_sl IS NOT NULL
                GROUP BY reason_for_sl
                ORDER BY count DESC
            """, conn)
            
            conn.close()
            return df
            
        except Exception as e:
            logger.error(f"Failed to get SL analysis: {str(e)}")
            return pd.DataFrame()
