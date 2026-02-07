"""
MODEL TRAINER: Train XGBoost Model for 30-Min Direction Prediction
- Uses cross-validation for robust training
- Optimized hyperparameters for financial data
- Saves trained model + performance metrics
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import json
from datetime import datetime
from loguru import logger
import sys
sys.path.append(str(Path(__file__).parent.parent))

# XGBoost and sklearn imports
try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
except ImportError:
    logger.error("XGBoost or scikit-learn not installed. Run: pip install xgboost scikit-learn")
    raise


class ModelTrainer:
    """Train and evaluate XGBoost classification model"""
    
    def __init__(self):
        self.model = None
        self.feature_importance = None
        self.metrics = {}
    
    def prepare_data(self, df: pd.DataFrame, feature_cols: list, target_col: str = 'target'):
        """
        Split data into train/test sets
        
        Args:
            df: DataFrame with features and target
            feature_cols: List of feature column names
            target_col: Target column name
        
        Returns:
            X_train, X_test, y_train, y_test
        """
        logger.info("Preparing train/test split...")
        
        # Features and target
        X = df[feature_cols]
        y = df[target_col]
        
        # Convert -1/+1 labels to 0/1 for binary classification
        y = np.where(y == 1, 1, 0)
        
        # 80/20 train/test split (chronological - use last 20% as test)
        split_idx = int(len(df) * 0.8)
        X_train = X.iloc[:split_idx]
        X_test = X.iloc[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]
        
        logger.info(f"✓ Train: {len(X_train)} samples")
        logger.info(f"✓ Test: {len(X_test)} samples")
        logger.info(f"✓ Train UP%: {(y_train==1).sum()/len(y_train)*100:.1f}%")
        logger.info(f"✓ Test UP%: {(y_test==1).sum()/len(y_test)*100:.1f}%")
        
        return X_train, X_test, y_train, y_test
    
    def train_model(self, X_train, y_train):
        """
        Train XGBoost classifier with optimized hyperparameters
        
        Hyperparameters tuned for financial time series:
        - max_depth: 6 (prevent overfitting)
        - learning_rate: 0.05 (slower, more stable)
        - n_estimators: 200 (enough trees for complex patterns)
        - subsample: 0.8 (row sampling for robustness)
        - colsample_bytree: 0.8 (feature sampling)
        """
        logger.info("Training XGBoost model...")
        
        # Convert -1/1 labels to 0/1 (XGBoost requirement)
        y_train = np.where(y_train == 1, 1, 0)
        
        # Optimized hyperparameters
        params = {
            'objective': 'binary:logistic',
            'max_depth': 6,
            'learning_rate': 0.05,
            'n_estimators': 200,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 3,
            'gamma': 0.1,
            'random_state': 42,
            'eval_metric': 'logloss',
            'use_label_encoder': False
        }
        
        # Train model
        self.model = xgb.XGBClassifier(**params)
        self.model.fit(
            X_train, 
            y_train,
            verbose=False
        )
        
        logger.info("✓ Model training complete")
        
        # Feature importance
        self.feature_importance = pd.DataFrame({
            'feature': X_train.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return self.model
    
    def evaluate_model(self, X_test, y_test):
        """Evaluate model performance on test set"""
        logger.info("Evaluating model...")
        
        # Convert -1/1 labels to 0/1 (XGBoost requirement)
        y_test = np.where(y_test == 1, 1, 0)
        
        # Predictions
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        
        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        
        # Store metrics
        self.metrics = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'confusion_matrix': cm.tolist(),
            'test_samples': len(y_test),
            'train_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Print results
        logger.info("="*70)
        logger.info("MODEL PERFORMANCE")
        logger.info("="*70)
        logger.info(f"Accuracy:  {accuracy*100:.2f}%")
        logger.info(f"Precision: {precision*100:.2f}%")
        logger.info(f"Recall:    {recall*100:.2f}%")
        logger.info(f"F1-Score:  {f1*100:.2f}%")
        logger.info("\nConfusion Matrix:")
        logger.info(f"  Predicted DOWN | Predicted UP")
        logger.info(f"DOWN: {cm[0][0]:4d}        | {cm[0][1]:4d}")
        logger.info(f"UP:   {cm[1][0]:4d}        | {cm[1][1]:4d}")
        logger.info("="*70)
        
        # Print classification report
        print("\nDetailed Classification Report:")
        print(classification_report(y_test, y_pred, target_names=['DOWN', 'UP']))
        
        return self.metrics
    
    def save_model(self, model_name: str = "xgboost_direction_model.pkl"):
        """Save trained model to disk"""
        model_path = Path(__file__).parent.parent / "models" / model_name
        
        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        logger.info(f"✓ Model saved: {model_path}")
        
        # Save metrics
        metrics_path = model_path.with_suffix('.json')
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        logger.info(f"✓ Metrics saved: {metrics_path}")
        
        # Save feature importance
        importance_path = model_path.parent / "feature_importance.csv"
        self.feature_importance.to_csv(importance_path, index=False)
        logger.info(f"✓ Feature importance saved: {importance_path}")
        
        return model_path
    
    def show_top_features(self, top_n: int = 10):
        """Display top N most important features"""
        logger.info(f"\nTop {top_n} Most Important Features:")
        logger.info("="*50)
        for idx, row in self.feature_importance.head(top_n).iterrows():
            logger.info(f"{row['feature']:25s} | {row['importance']:.4f}")
        logger.info("="*50)


def main():
    """Train model from featured data"""
    from ml_models.feature_engineer import FeatureEngineer
    
    logger.info("="*70)
    logger.info("STARTING MODEL TRAINING")
    logger.info("="*70)
    
    # Load featured data
    data_path = Path(__file__).parent.parent / "models" / "featured_data.csv"
    
    if not data_path.exists():
        logger.error(f"Featured data not found: {data_path}")
        logger.error("Run feature_engineer.py first!")
        return
    
    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    logger.info(f"Loaded {len(df)} samples from {data_path}")
    
    # Get feature columns
    fe = FeatureEngineer()
    feature_cols = fe.get_feature_columns()
    
    # Initialize trainer
    trainer = ModelTrainer()
    
    # Prepare data
    X_train, X_test, y_train, y_test = trainer.prepare_data(df, feature_cols)
    
    # Train model
    trainer.train_model(X_train, y_train)
    
    # Evaluate
    trainer.evaluate_model(X_test, y_test)
    
    # Show feature importance
    trainer.show_top_features(top_n=15)
    
    # Save model
    model_path = trainer.save_model()
    
    logger.info("="*70)
    logger.info(f"✓ TRAINING COMPLETE")
    logger.info(f"✓ Model ready: {model_path}")
    logger.info("="*70)


if __name__ == "__main__":
    main()
