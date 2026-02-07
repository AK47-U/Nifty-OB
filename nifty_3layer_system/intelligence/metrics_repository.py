#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRICS REPOSITORY
SQLite-based storage for complete market metrics accountability + auditability
Stores all 67 metrics + decisions every 15 minutes for pattern analysis
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd


class MetricsRepository:
    """
    Manages SQLite database for market metrics and trading decisions.
    Two tables: market_snapshots (every 15min) + daily_summary (aggregates)
    """
    
    def __init__(self, db_path: str = "data/trading_metrics.db"):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
    
    def _initialize_database(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # TABLE 1: MARKET SNAPSHOTS (Every 15 minutes)
        # Stores complete 67 metrics + classification + decision
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            instrument TEXT NOT NULL,
            
            -- PRICE & VOLATILITY
            ltp REAL NOT NULL,
            atr REAL,
            atr_ratio REAL,
            current_range REAL,
            volume REAL,
            volume_ratio REAL,
            
            -- L1: STRUCTURE (11 metrics - 30%)
            l1_market_structure_score REAL,
            l1_current_level REAL,
            l1_previous_support REAL,
            l1_previous_resistance REAL,
            l1_weekly_high REAL,
            l1_weekly_low REAL,
            l1_session_high REAL,
            l1_session_low REAL,
            l1_open_price REAL,
            l1_breakout_confirmed INTEGER,
            l1_structure_quality REAL,
            
            -- L2: INSTITUTIONAL (12 metrics - 30%)
            l2_institutional_strength REAL,
            l2_volume_profile_confluence REAL,
            l2_order_flow_direction REAL,
            l2_large_order_clustering REAL,
            l2_bid_ask_imbalance REAL,
            l2_market_microstructure REAL,
            l2_smart_money_activity REAL,
            l2_retail_flow REAL,
            l2_accumulation_detected INTEGER,
            l2_distribution_detected INTEGER,
            l2_smart_money_entry REAL,
            l2_institutional_conviction REAL,
            
            -- L3: TECHNICAL (14 metrics - 20%)
            l3_ema_alignment REAL,
            l3_ema_9 REAL,
            l3_ema_20 REAL,
            l3_ema_50 REAL,
            l3_rsi REAL,
            l3_rsi_strength REAL,
            l3_macd REAL,
            l3_macd_signal REAL,
            l3_macd_histogram REAL,
            l3_momentum_direction REAL,
            l3_momentum_strength REAL,
            l3_trend_confirmation INTEGER,
            l3_candle_pattern TEXT,
            l3_technical_score REAL,
            
            -- L4: BLOCKING (12 metrics - 15%)
            l4_support_level REAL,
            l4_resistance_level REAL,
            l4_previous_trend_line REAL,
            l4_fibonacci_support REAL,
            l4_fibonacci_resistance REAL,
            l4_pivot_level REAL,
            l4_volume_profile_support REAL,
            l4_volume_profile_resistance REAL,
            l4_supply_demand_balance REAL,
            l4_trendline_proximity REAL,
            l4_barrier_strength REAL,
            l4_blocking_score REAL,
            
            -- L5: MULTI-TIMEFRAME (8 metrics - 5%)
            l5_4h_trend TEXT,
            l5_1h_trend TEXT,
            l5_15m_trend TEXT,
            l5_4h_ma_alignment INTEGER,
            l5_1h_ma_alignment INTEGER,
            l5_mtf_confluence REAL,
            l5_higher_tf_confirmation INTEGER,
            l5_mtf_score REAL,
            
            -- AGGREGATE SCORES
            score_structure REAL,
            score_institutional REAL,
            score_technical REAL,
            score_blocking REAL,
            score_mtf REAL,
            score_overall_confidence REAL,
            
            -- MARKET CLASSIFICATION
            market_condition TEXT,
            market_volatility_pct REAL,
            setup_quality TEXT,
            
            -- DYNAMIC TARGETS (Based on Market Condition)
            dynamic_entry_precision REAL,
            dynamic_stop_loss REAL,
            dynamic_target1 REAL,
            dynamic_target2 REAL,
            position_size_multiplier REAL,
            
            -- FINAL DECISION
            final_decision TEXT,  -- CALL, PUT, WAIT
            decision_confidence REAL,
            
            -- METADATA
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # TABLE 2: DAILY SUMMARY (Daily aggregates)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            instrument TEXT NOT NULL,
            
            -- CONDITION DISTRIBUTION
            quiet_count INTEGER,
            normal_count INTEGER,
            high_count INTEGER,
            extreme_count INTEGER,
            dominant_condition TEXT,
            
            -- QUALITY DISTRIBUTION
            weak_count INTEGER,
            moderate_count INTEGER,
            strong_count INTEGER,
            excellent_count INTEGER,
            dominant_quality TEXT,
            
            -- DECISION DISTRIBUTION
            call_count INTEGER,
            put_count INTEGER,
            wait_count INTEGER,
            
            -- PERFORMANCE METRICS
            average_condition_volatility REAL,
            average_setup_quality REAL,
            best_condition TEXT,
            worst_condition TEXT,
            average_confidence REAL,
            
            -- METADATA
            total_snapshots INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
    
    def save_snapshot(
        self,
        timestamp: str,
        instrument: str,
        metrics: Dict,
        market_condition: str,
        setup_quality: str,
        dynamic_params: Dict,
        final_decision: str,
        confidence: float
    ) -> bool:
        """
        Save complete market snapshot to database.
        
        Args:
            timestamp: ISO format timestamp
            instrument: NIFTY/SENSEX/BANKNIFTY
            metrics: Dict with all 67 metrics (keys match column names)
            market_condition: QUIET/NORMAL/HIGH/EXTREME
            setup_quality: WEAK/MODERATE/STRONG/EXCELLENT
            dynamic_params: Dict with SL/T1/T2/multiplier
            final_decision: CALL/PUT/WAIT
            confidence: Overall confidence (0-100)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Prepare data - only include metrics that exist as columns
            data = {
                'timestamp': timestamp,
                'instrument': instrument,
                'market_condition': market_condition,
                'setup_quality': setup_quality,
                'dynamic_entry_precision': dynamic_params.get('entry_precision', 0),
                'dynamic_stop_loss': dynamic_params.get('stop_loss_points', 0),
                'dynamic_target1': dynamic_params.get('target1_points', 0),
                'dynamic_target2': dynamic_params.get('target2_points', 0),
                'position_size_multiplier': dynamic_params.get('position_size_multiplier', 0),
                'final_decision': final_decision,
                'decision_confidence': confidence,
                'market_volatility_pct': dynamic_params.get('market_volatility_pct', 0),
                'atr_ratio': dynamic_params.get('atr_ratio', 0)
            }
            
            # Add all provided metrics
            data.update(metrics)
            
            # Build INSERT statement
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data.keys()])
            sql = f"INSERT INTO market_snapshots ({columns}) VALUES ({placeholders})"
            
            cursor.execute(sql, tuple(data.values()))
            conn.commit()
            conn.close()
            
            return True
        
        except Exception as e:
            print(f"❌ Error saving snapshot: {e}")
            return False
    
    def update_daily_summary(self, instrument: str, date: str = None) -> bool:
        """
        Aggregate today's snapshots into daily summary.
        
        Args:
            instrument: NIFTY/SENSEX/BANKNIFTY
            date: Date to summarize (default: today)
        
        Returns:
            True if successful
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all snapshots for the day
            cursor.execute("""
            SELECT 
                market_condition, setup_quality, final_decision, 
                market_volatility_pct, decision_confidence
            FROM market_snapshots
            WHERE instrument = ? AND DATE(timestamp) = ?
            """, (instrument, date))
            
            snapshots = cursor.fetchall()
            
            if not snapshots:
                conn.close()
                return False
            
            # Aggregate
            condition_counts = {'QUIET': 0, 'NORMAL': 0, 'HIGH': 0, 'EXTREME': 0}
            quality_counts = {'WEAK': 0, 'MODERATE': 0, 'STRONG': 0, 'EXCELLENT': 0}
            decision_counts = {'CALL': 0, 'PUT': 0, 'WAIT': 0}
            total_volatility = 0
            total_quality = 0
            total_confidence = 0
            
            for snap in snapshots:
                condition_counts[snap[0]] = condition_counts.get(snap[0], 0) + 1
                quality_counts[snap[1]] = quality_counts.get(snap[1], 0) + 1
                decision_counts[snap[2]] = decision_counts.get(snap[2], 0) + 1
                total_volatility += snap[3] or 0
                total_quality += (self._quality_to_score(snap[1]) or 0)
                total_confidence += snap[4] or 0
            
            total_snapshots = len(snapshots)
            dominant_condition = max(condition_counts, key=condition_counts.get)
            dominant_quality = max(quality_counts, key=quality_counts.get)
            
            # Upsert into daily_summary
            cursor.execute("""
            INSERT OR REPLACE INTO daily_summary 
            (date, instrument, quiet_count, normal_count, high_count, extreme_count,
             dominant_condition, weak_count, moderate_count, strong_count, excellent_count,
             dominant_quality, call_count, put_count, wait_count,
             average_condition_volatility, average_setup_quality, average_confidence,
             total_snapshots)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, instrument,
                condition_counts['QUIET'], condition_counts['NORMAL'],
                condition_counts['HIGH'], condition_counts['EXTREME'],
                dominant_condition,
                quality_counts['WEAK'], quality_counts['MODERATE'],
                quality_counts['STRONG'], quality_counts['EXCELLENT'],
                dominant_quality,
                decision_counts['CALL'], decision_counts['PUT'], decision_counts['WAIT'],
                round(total_volatility / total_snapshots, 4),
                round(total_quality / total_snapshots, 2),
                round(total_confidence / total_snapshots, 2),
                total_snapshots
            ))
            
            conn.commit()
            conn.close()
            
            return True
        
        except Exception as e:
            print(f"❌ Error updating daily summary: {e}")
            return False
    
    def get_today_analysis(self, instrument: str) -> Dict:
        """Get today's complete analysis from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.now().strftime('%Y-%m-%d')
            
            summary = pd.read_sql_query(
                "SELECT * FROM daily_summary WHERE date = ? AND instrument = ?",
                conn, params=(today, instrument)
            )
            
            conn.close()
            
            if len(summary) == 0:
                return {"error": "No data for today"}
            
            return summary.to_dict('records')[0]
        
        except Exception as e:
            return {"error": str(e)}
    
    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """
        Delete snapshots older than retention days.
        
        Args:
            retention_days: Days to keep (default: 30)
        
        Returns:
            Number of records deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            cursor.execute(
                "DELETE FROM market_snapshots WHERE created_at < ?",
                (cutoff_date,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted_count
        
        except Exception as e:
            print(f"❌ Error cleaning up old data: {e}")
            return 0
    
    @staticmethod
    def _quality_to_score(quality_str: str) -> float:
        """Convert quality string to numeric score"""
        mapping = {
            'WEAK': 25,
            'MODERATE': 52.5,
            'STRONG': 75,
            'EXCELLENT': 92.5
        }
        return mapping.get(quality_str, 0)


# Helper functions for querying
def get_database_stats(db_path: str = "data/trading_metrics.db") -> Dict:
    """Get basic database statistics"""
    try:
        conn = sqlite3.connect(db_path)
        
        stats = {}
        stats['snapshots'] = pd.read_sql_query(
            "SELECT COUNT(*) as count, instrument FROM market_snapshots GROUP BY instrument",
            conn
        ).to_dict('records')
        
        stats['daily_summaries'] = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM daily_summary",
            conn
        ).iloc[0]['count']
        
        conn.close()
        return stats
    
    except Exception as e:
        return {"error": str(e)}


def query_best_conditions(db_path: str = "data/trading_metrics.db", days: int = 7) -> pd.DataFrame:
    """Query best performing market conditions from last N days"""
    try:
        conn = sqlite3.connect(db_path)
        
        sql = """
        SELECT 
            DATE(timestamp) as date,
            instrument,
            market_condition,
            COUNT(*) as count,
            ROUND(AVG(decision_confidence), 2) as avg_confidence,
            SUM(CASE WHEN final_decision='CALL' THEN 1 ELSE 0 END) as call_count,
            SUM(CASE WHEN final_decision='PUT' THEN 1 ELSE 0 END) as put_count,
            SUM(CASE WHEN final_decision='WAIT' THEN 1 ELSE 0 END) as wait_count
        FROM market_snapshots
        WHERE DATE(timestamp) >= DATE('now', '-' || ? || ' days')
        GROUP BY DATE(timestamp), instrument, market_condition
        ORDER BY date DESC, avg_confidence DESC
        """
        
        result = pd.read_sql_query(sql, conn, params=(days,))
        conn.close()
        
        return result
    
    except Exception as e:
        print(f"Error querying conditions: {e}")
        return pd.DataFrame()
