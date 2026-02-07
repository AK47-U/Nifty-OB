"""
Automated Model Retraining Pipeline
Fetches fresh 90-day data, retrains XGBoost, compares performance
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
import json
import pickle
from ml_models.data_extractor import DataExtractor
from ml_models.feature_engineer import FeatureEngineer
from ml_models.model_trainer import ModelTrainer


class ModelRetrainingPipeline:
    """Automated retraining with performance comparison"""
    
    def __init__(self):
        self.extractor = DataExtractor()
        self.engineer = FeatureEngineer()
        self.trainer = ModelTrainer()
        self.models_dir = Path(__file__).parent.parent / "models"
        self.models_dir.mkdir(exist_ok=True)
    
    def backup_old_model(self):
        """Backup existing model before retraining"""
        old_model_path = self.models_dir / "xgboost_direction_model.pkl"
        old_metrics_path = self.models_dir / "model_metrics.json"
        
        if old_model_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_model = self.models_dir / f"xgboost_direction_model_backup_{timestamp}.pkl"
            backup_metrics = self.models_dir / f"model_metrics_backup_{timestamp}.json"
            
            import shutil
            shutil.copy(old_model_path, backup_model)
            if old_metrics_path.exists():
                shutil.copy(old_metrics_path, backup_metrics)
            
            logger.info(f"✓ Backed up old model: {backup_model.name}")
            logger.info(f"✓ Backed up metrics: {backup_metrics.name}")
            
            return backup_metrics
        return None
    
    def fetch_fresh_data(self, days: int = 90) -> pd.DataFrame:
        """Fetch latest data from Dhan API"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 STEP 1: FETCHING FRESH DATA ({days} days)")
        logger.info(f"{'='*70}")
        
        df = self.extractor.fetch_historical_data(days=days)
        
        logger.info(f"\n✓ Fetched {len(df)} candles")
        logger.info(f"  Date Range: {df.index[0]} to {df.index[-1]}")
        logger.info(f"  OHLCV available: {df.shape[1]} columns")
        
        return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate 35 features for training"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🧠 STEP 2: ENGINEERING 35 FEATURES")
        logger.info(f"{'='*70}")
        
        features_df = self.engineer.generate_all_features(df)
        
        logger.info(f"\n✓ Generated {features_df.shape[1]} total columns")
        logger.info(f"✓ After NaN removal: {features_df.shape[0]} rows")
        
        feature_cols = self.engineer.get_feature_columns()
        logger.info(f"✓ {len(feature_cols)} features ready for model:")
        
        for i, col in enumerate(feature_cols, 1):
            if i % 5 == 0:
                logger.info(f"  {i:2d}. {col}")
            elif i == len(feature_cols):
                logger.info(f"  {i:2d}. {col}")
        
        return features_df
    
    def prepare_training_data(self, features_df: pd.DataFrame) -> tuple:
        """Prepare X, y for training"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📋 STEP 3: PREPARING TRAINING DATA")
        logger.info(f"{'='*70}")
        
        feature_cols = self.engineer.get_feature_columns()
        
        X = features_df[feature_cols].copy()
        y = features_df['label'].copy()
        
        # Check class balance
        class_counts = y.value_counts()
        up_pct = (class_counts[1] / len(y)) * 100
        down_pct = (class_counts[-1] / len(y)) * 100
        
        logger.info(f"\n✓ Training samples: {len(X)}")
        logger.info(f"✓ Features: {X.shape[1]}")
        logger.info(f"✓ Class distribution:")
        logger.info(f"    UP (+1):    {class_counts[1]:,} ({up_pct:.1f}%)")
        logger.info(f"    DOWN (-1):  {class_counts[-1]:,} ({down_pct:.1f}%)")
        
        if abs(up_pct - 50) > 10:
            logger.warning(f"⚠️  Class imbalance detected: {up_pct:.1f}% UP")
        else:
            logger.info(f"✓ Classes well-balanced")
        
        return X, y
    
    def train_new_model(self, X: pd.DataFrame, y: pd.Series) -> dict:
        """Train fresh XGBoost model"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🤖 STEP 4: TRAINING XGBOOST MODEL")
        logger.info(f"{'='*70}")
        
        metrics = self.trainer.train_and_evaluate(X, y)
        
        logger.info(f"\n✓ Model trained successfully")
        logger.info(f"✓ Test accuracy: {metrics['accuracy']:.2%}")
        logger.info(f"✓ Precision: {metrics['precision']:.2%}")
        logger.info(f"✓ Recall: {metrics['recall']:.2%}")
        logger.info(f"✓ F1-Score: {metrics['f1']:.4f}")
        
        return metrics
    
    def compare_performance(self, old_metrics_path: Path, new_metrics: dict) -> dict:
        """Compare old vs new model performance"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 STEP 5: PERFORMANCE COMPARISON")
        logger.info(f"{'='*70}")
        
        comparison = {
            'improved': {},
            'degraded': {},
            'unchanged': {}
        }
        
        # Load old metrics
        old_metrics = {}
        if old_metrics_path and old_metrics_path.exists():
            with open(old_metrics_path) as f:
                old_metrics = json.load(f)
        
        # Compare key metrics
        metrics_to_compare = ['accuracy', 'precision', 'recall', 'f1']
        
        logger.info(f"\n{'Metric':<15} {'Old':<12} {'New':<12} {'Change':<10}")
        logger.info("-" * 50)
        
        for metric in metrics_to_compare:
            old_val = old_metrics.get(metric, 0)
            new_val = new_metrics.get(metric, 0)
            change = new_val - old_val
            change_pct = (change / old_val * 100) if old_val > 0 else 0
            
            status = "↑" if change > 0 else "↓" if change < 0 else "→"
            
            logger.info(f"{metric:<15} {old_val:<12.4f} {new_val:<12.4f} {status} {change_pct:+.2f}%")
            
            if change > 0:
                comparison['improved'][metric] = change_pct
            elif change < 0:
                comparison['degraded'][metric] = change_pct
            else:
                comparison['unchanged'][metric] = change_pct
        
        return comparison
    
    def save_new_model(self, X: pd.DataFrame):
        """Save retrained model and metadata"""
        logger.info(f"\n{'='*70}")
        logger.info(f"💾 STEP 6: SAVING NEW MODEL")
        logger.info(f"{'='*70}")
        
        # Model already saved by trainer, just log it
        model_path = self.models_dir / "xgboost_direction_model.pkl"
        metrics_path = self.models_dir / "model_metrics.json"
        importance_path = self.models_dir / "feature_importance.csv"
        
        logger.info(f"\n✓ Model saved: {model_path}")
        logger.info(f"✓ Metrics saved: {metrics_path}")
        logger.info(f"✓ Feature importance: {importance_path}")
        logger.info(f"\n✓ Ready for live trading!")
    
    def run_full_pipeline(self) -> dict:
        """Execute complete retraining pipeline"""
        logger.info("\n" + "="*70)
        logger.info("🔄 MODEL RETRAINING PIPELINE STARTED")
        logger.info("="*70)
        
        start_time = datetime.now()
        
        try:
            # Step 1: Backup old model
            old_metrics_path = self.backup_old_model()
            
            # Step 2: Fetch fresh data
            df = self.fetch_fresh_data(days=90)
            
            # Step 3: Engineer features
            features_df = self.engineer_features(df)
            
            # Step 4: Prepare data
            X, y = self.prepare_training_data(features_df)
            
            # Step 5: Train model
            new_metrics = self.train_new_model(X, y)
            
            # Step 6: Compare performance
            comparison = self.compare_performance(old_metrics_path, new_metrics)
            
            # Step 7: Save model
            self.save_new_model(X)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"\n{'='*70}")
            logger.info(f"✅ RETRAINING COMPLETED SUCCESSFULLY")
            logger.info(f"{'='*70}")
            logger.info(f"Total time: {duration:.1f} seconds")
            logger.info(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
            logger.info(f"\nModel is ready for live trading!")
            
            return {
                'success': True,
                'metrics': new_metrics,
                'comparison': comparison,
                'duration': duration
            }
        
        except Exception as e:
            logger.error(f"\n❌ RETRAINING FAILED")
            logger.error(f"Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def format_summary(self, result: dict) -> str:
        """Format retraining summary for display"""
        
        if not result['success']:
            return f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                        RETRAINING FAILED                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝

❌ Error: {result['error']}

Reverting to previous model...
"""
        
        metrics = result['metrics']
        comparison = result['comparison']
        
        summary = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                   ✅ RETRAINING SUCCESSFUL                               ║
╚═══════════════════════════════════════════════════════════════════════════╝

⏱️  Time Taken: {result['duration']:.1f} seconds
📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 NEW MODEL PERFORMANCE:

   Accuracy:       {metrics['accuracy']:.2%}
   Precision:      {metrics['precision']:.2%}
   Recall:         {metrics['recall']:.2%}
   F1-Score:       {metrics['f1']:.4f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 IMPROVEMENTS vs OLD MODEL:
"""
        
        if comparison['improved']:
            summary += f"\n   ✅ Improved ({len(comparison['improved'])}):\n"
            for metric, change in comparison['improved'].items():
                summary += f"      • {metric:<12} +{change:>6.2f}%\n"
        
        if comparison['degraded']:
            summary += f"\n   ⚠️  Degraded ({len(comparison['degraded'])}):\n"
            for metric, change in comparison['degraded'].items():
                summary += f"      • {metric:<12} {change:>6.2f}%\n"
        
        summary += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Model saved and ready for live trading!
   Levels Monitor will use new model next startup.
"""
        
        return summary


def main():
    """Execute retraining pipeline"""
    pipeline = ModelRetrainingPipeline()
    result = pipeline.run_full_pipeline()
    print(pipeline.format_summary(result))


if __name__ == "__main__":
    main()
