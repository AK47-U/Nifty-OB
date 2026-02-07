"""
Parameter learner - automatically adjusts trading parameters based on real-time failure analysis.
Stores all adjustments in database for audit trail and continuous improvement.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List


class ParameterLearner:
    """Learns from failures and auto-adjusts trading parameters."""

    def __init__(self, db_path: str = 'data/trading_metrics.db'):
        self.db_path = db_path
        self.parameter_history = []
        
        # Default parameters
        self.default_params = {
            'min_confidence': 0.60,
            'min_rr_ratio': 1.5,
            'trend_alignment_required': False,
            'entry_quality_required': False,
            'min_atr': 0.5,
            'block_hours': [],  # Hours to block trading
            'max_trades_per_day': 2
        }
        
    def get_current_parameters(self) -> Dict:
        """
        Fetch current active parameters from database.
        Returns default if no adjustments have been made.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT parameter_name, parameter_value, timestamp
                FROM parameter_adjustments
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Parse stored JSON parameters
                import json
                return json.loads(result[1])
            else:
                return self.default_params.copy()
                
        except Exception as e:
            print(f"Error fetching parameters: {e}")
            return self.default_params.copy()
    
    def learn_and_adjust(self, failure_analysis: Dict, recommendations: List[str]) -> Dict:
        """
        Apply recommendations and update parameters accordingly.
        
        Returns:
        {
            'adjusted_params': dict,
            'changes_made': list,
            'adjustment_timestamp': str
        }
        """
        current_params = self.get_current_parameters()
        adjusted_params = current_params.copy()
        changes_made = []
        
        distribution = failure_analysis.get('reason_distribution', {})
        
        # Adjust confidence threshold
        if distribution.get('low_confidence', 0) > 2:
            old_conf = adjusted_params['min_confidence']
            adjusted_params['min_confidence'] = min(0.75, old_conf + 0.05)
            if adjusted_params['min_confidence'] != old_conf:
                changes_made.append(
                    f"min_confidence: {old_conf} → {adjusted_params['min_confidence']}"
                )
        
        # Activate trend alignment
        if distribution.get('counter_trend', 0) > 2:
            if not adjusted_params['trend_alignment_required']:
                adjusted_params['trend_alignment_required'] = True
                changes_made.append("trend_alignment_required: False → True")
        
        # Activate entry quality filter
        if distribution.get('low_quality', 0) > 2:
            if not adjusted_params['entry_quality_required']:
                adjusted_params['entry_quality_required'] = True
                changes_made.append("entry_quality_required: False → True")
        
        # Adjust R:R ratio
        if failure_analysis.get('low_rr_ratio_failures', 0) > 2:
            old_rr = adjusted_params['min_rr_ratio']
            adjusted_params['min_rr_ratio'] = min(2.0, old_rr + 0.25)
            if adjusted_params['min_rr_ratio'] != old_rr:
                changes_made.append(
                    f"min_rr_ratio: {old_rr} → {adjusted_params['min_rr_ratio']}"
                )
        
        # Block worst market hours
        worst_hour = failure_analysis.get('worst_hour')
        if worst_hour and distribution.get('market_hour', 0) > 1:
            if worst_hour not in adjusted_params['block_hours']:
                adjusted_params['block_hours'].append(worst_hour)
                changes_made.append(f"block_hours: Added {worst_hour}:00 IST")
        
        # Store adjustment in database
        if changes_made:
            self._save_adjustment(adjusted_params, changes_made)
        
        return {
            'adjusted_params': adjusted_params,
            'changes_made': changes_made,
            'adjustment_timestamp': datetime.now().isoformat()
        }
    
    def _save_adjustment(self, params: Dict, changes: List[str]):
        """Store parameter adjustment in database for audit trail."""
        try:
            import json
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parameter_adjustments (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    parameter_name TEXT NOT NULL,
                    parameter_value TEXT NOT NULL,
                    changes_log TEXT NOT NULL
                )
            """)
            
            # Insert adjustment record
            cursor.execute("""
                INSERT INTO parameter_adjustments (timestamp, parameter_name, parameter_value, changes_log)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                'trading_parameters',
                json.dumps(params),
                '|'.join(changes)
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Parameters adjusted: {len(changes)} changes")
            for change in changes:
                print(f"   - {change}")
            
        except Exception as e:
            print(f"Error saving adjustment: {e}")
    
    def get_parameter_history(self, limit: int = 10) -> List[Dict]:
        """Retrieve history of parameter adjustments."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, parameter_name, parameter_value, changes_log
                FROM parameter_adjustments
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'parameter_name': row[1],
                    'parameter_value': row[2],
                    'changes_log': row[3]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []
    
    def should_pause_trading(self, failure_analysis: Dict) -> tuple[bool, str]:
        """
        Determine if trading should be paused due to excessive failures.
        
        Returns:
            (should_pause: bool, reason: str)
        """
        total_failures = failure_analysis.get('total_failures', 0)
        
        # Pause if 3+ failures in last 2 hours
        if total_failures >= 3:
            return True, f"⛔ PAUSE: {total_failures} failures in last 2 hours - circuit breaker activated"
        
        # Check specific failure patterns
        distribution = failure_analysis.get('reason_distribution', {})
        
        if distribution.get('counter_trend', 0) >= 2:
            return True, "⛔ PAUSE: Repeated counter-trend failures - wait for trend confirmation"
        
        if distribution.get('low_quality', 0) >= 2:
            return True, "⛔ PAUSE: Repeated poor entry quality - wait for better levels"
        
        return False, ""
