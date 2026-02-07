"""
ML PIPELINE: Complete Training Pipeline
Runs all steps: data extraction → feature engineering → model training
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from ml_models.data_extractor import DataExtractor
from ml_models.feature_engineer import FeatureEngineer
from ml_models.model_trainer import ModelTrainer


def run_complete_pipeline(days: int = 90):
    """
    Run complete ML training pipeline
    
    Steps:
    1. Extract 90 days of historical data from Dhan API
    2. Create UP/DOWN labels for 30-min predictions
    3. Generate 30 technical features
    4. Train XGBoost model
    5. Evaluate performance
    6. Save model for live trading
    
    Args:
        days: Number of days to fetch (max 90)
    """
    logger.info("="*70)
    logger.info("ML PIPELINE - COMPLETE TRAINING")
    logger.info("="*70)
    
    # Step 1: Extract data
    logger.info("\n[STEP 1/4] DATA EXTRACTION")
    logger.info("-"*70)
    extractor = DataExtractor()
    csv_path = extractor.extract_and_save(days=days)
    
    # Step 2: Feature engineering
    logger.info("\n[STEP 2/4] FEATURE ENGINEERING")
    logger.info("-"*70)
    import pandas as pd
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    
    fe = FeatureEngineer()
    df_features = fe.generate_all_features(df)
    
    # Save featured data
    featured_path = Path(__file__).parent.parent / "models" / "featured_data.csv"
    df_features.to_csv(featured_path)
    logger.info(f"✓ Featured data saved: {featured_path}")
    
    # Step 3: Model training
    logger.info("\n[STEP 3/4] MODEL TRAINING")
    logger.info("-"*70)
    
    feature_cols = fe.get_feature_columns()
    trainer = ModelTrainer()
    
    X_train, X_test, y_train, y_test = trainer.prepare_data(df_features, feature_cols)
    trainer.train_model(X_train, y_train)
    
    # Step 4: Evaluation
    logger.info("\n[STEP 4/4] MODEL EVALUATION")
    logger.info("-"*70)
    
    trainer.evaluate_model(X_test, y_test)
    trainer.show_top_features(top_n=15)
    
    # Save model
    model_path = trainer.save_model()
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("✓ PIPELINE COMPLETE")
    logger.info("="*70)
    logger.info(f"Training samples: {len(X_train)}")
    logger.info(f"Test samples: {len(X_test)}")
    logger.info(f"Accuracy: {trainer.metrics['accuracy']*100:.2f}%")
    logger.info(f"Model saved: {model_path}")
    logger.info("\nNext step: Run live_predictor.py for real-time predictions")
    logger.info("="*70)


if __name__ == "__main__":
    # Run pipeline with 90 days of data
    run_complete_pipeline(days=90)
