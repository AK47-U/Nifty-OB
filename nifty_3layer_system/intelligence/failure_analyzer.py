"""
Failure pattern analyzer - detects why signals fail and identifies root causes.
Uses real-time query of level_signals database to identify recurring failure patterns.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
from collections import Counter


class FailureAnalyzer:
    """Analyzes signal failures to identify patterns and root causes."""

    def __init__(self, db_path: str = 'data/trading_metrics.db'):
        self.db_path = db_path
        self.failure_types = [
            'counter_trend_entry',
            'poor_entry_quality',
            'market_hour_disadvantage',
            'low_confidence',
            'high_volatility',
            'early_market_chop'
        ]
        
    def get_recent_failures(self, hours: int = 2) -> List[Dict]:
        """
        Query database for signals that hit SL in the last N hours.
        
        Returns:
        [
            {
                'signal_id': int,
                'direction': 'UP|DOWN',
                'timestamp': str,
                'entry': float,
                'sl': float,
                'confidence': float,
                'market_hour': int,
                'sl_reason': str,
                'risk_points': float,
                'reward_points': float,
                'rr_ratio': float
            }
        ]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query for failed signals (where sl_hit = True)
            cursor.execute("""
                SELECT 
                    id, direction, timestamp, entry, sl, confidence,
                    market_hour, sl_reason, risk_points, reward_points, rr_ratio
                FROM level_signals
                WHERE sl_hit = 1
                AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            """, (hours,))
            
            failures = []
            for row in cursor.fetchall():
                failures.append({
                    'signal_id': row[0],
                    'direction': row[1],
                    'timestamp': row[2],
                    'entry': row[3],
                    'sl': row[4],
                    'confidence': row[5],
                    'market_hour': row[6],
                    'sl_reason': row[7],
                    'risk_points': row[8],
                    'reward_points': row[9],
                    'rr_ratio': row[10]
                })
            
            conn.close()
            return failures
            
        except Exception as e:
            print(f"Error querying failures: {e}")
            return []
    
    def identify_failure_patterns(self, failures: List[Dict]) -> Dict:
        """
        Analyze failures and categorize them by root cause.
        
        Returns:
        {
            'total_failures': int,
            'failure_rate': float (0.0-1.0),
            'primary_reason': str,
            'reason_distribution': {
                'counter_trend': int,
                'low_quality': int,
                'low_confidence': int,
                'volatility': int,
                'market_hour': int,
                'chop': int
            },
            'worst_hour': int,
            'best_hour': int,
            'low_rr_ratio_failures': int
        }
    """
        if not failures:
            return {
                'total_failures': 0,
                'failure_rate': 0.0,
                'primary_reason': 'No failures',
                'reason_distribution': {
                    'counter_trend': 0,
                    'low_quality': 0,
                    'low_confidence': 0,
                    'volatility': 0,
                    'market_hour': 0,
                    'chop': 0
                },
                'worst_hour': None,
                'best_hour': None,
                'low_rr_ratio_failures': 0
            }
        
        reasons = []
        hours_list = []
        low_rr_count = 0
        
        for failure in failures:
            reason = failure.get('sl_reason', 'unknown')
            
            # Map to failure categories
            if 'counter' in reason.lower() or 'trend' in reason.lower():
                reasons.append('counter_trend')
            elif 'quality' in reason.lower() or 'entry' in reason.lower():
                reasons.append('low_quality')
            elif 'confidence' in reason.lower():
                reasons.append('low_confidence')
            elif 'volatility' in reason.lower():
                reasons.append('volatility')
            elif 'hour' in reason.lower():
                reasons.append('market_hour')
            elif 'chop' in reason.lower():
                reasons.append('chop')
            else:
                reasons.append('chop')
            
            hours_list.append(failure.get('market_hour', 10))
            
            # Count low R:R failures
            if failure.get('rr_ratio', 1.0) < 1.5:
                low_rr_count += 1
        
        # Calculate distributions
        reason_counter = Counter(reasons)
        hour_counter = Counter(hours_list)
        
        primary_reason = reason_counter.most_common(1)[0][0] if reason_counter else 'unknown'
        
        return {
            'total_failures': len(failures),
            'failure_rate': len(failures) / max(1, len(failures)),  # Will be updated with total trades
            'primary_reason': primary_reason,
            'reason_distribution': {
                'counter_trend': reason_counter.get('counter_trend', 0),
                'low_quality': reason_counter.get('low_quality', 0),
                'low_confidence': reason_counter.get('low_confidence', 0),
                'volatility': reason_counter.get('volatility', 0),
                'market_hour': reason_counter.get('market_hour', 0),
                'chop': reason_counter.get('chop', 0)
            },
            'worst_hour': max(hour_counter, key=hour_counter.get) if hour_counter else None,
            'best_hour': min(hour_counter, key=hour_counter.get) if hour_counter else None,
            'low_rr_ratio_failures': low_rr_count
        }
    
    def get_failure_recommendations(self, failure_analysis: Dict) -> List[str]:
        """
        Generate recommendations based on failure pattern analysis.
        
        Returns:
        ['recommendation1', 'recommendation2', ...]
        """
        recommendations = []
        
        distribution = failure_analysis.get('reason_distribution', {})
        primary = failure_analysis.get('primary_reason', '')
        
        # Counter-trend recommendations
        if distribution.get('counter_trend', 0) > 2:
            recommendations.append(
                '⚠️ COUNTER-TREND: Activate 15-min trend filter - block trades against trend'
            )
        
        # Low quality recommendations
        if distribution.get('low_quality', 0) > 2:
            recommendations.append(
                '⚠️ ENTRY QUALITY: Increase entry quality threshold - wait for better S/R proximity'
            )
        
        # Low confidence recommendations
        if distribution.get('low_confidence', 0) > 2:
            recommendations.append(
                '⚠️ LOW CONFIDENCE: Increase minimum confidence threshold from 0.6 to 0.75'
            )
        
        # Volatility recommendations
        if distribution.get('volatility', 0) > 2:
            recommendations.append(
                '⚠️ VOLATILITY: Widen SL during high volatility periods - use ATR-based sizing'
            )
        
        # Market hour recommendations
        worst_hour = failure_analysis.get('worst_hour')
        if worst_hour and distribution.get('market_hour', 0) > 1:
            recommendations.append(
                f'⚠️ MARKET HOUR: Avoid trades around {worst_hour}:00 IST (chop zone)'
            )
        
        # Low R:R ratio recommendations
        if failure_analysis.get('low_rr_ratio_failures', 0) > 2:
            recommendations.append(
                '⚠️ RISK-REWARD: Reject signals with R:R < 1.5 - requires better target placement'
            )
        
        if not recommendations:
            recommendations.append('✅ No major failure patterns detected - system performing well')
        
        return recommendations
