"""FinPulse ML Model Module

Handles ML feature extraction, training an ensemble model (RandomForest + XGBoost),
saving/loading the model pickle, and predicting the next-day price movement direction.
Includes a rule-based fallback if the ML model is not trained yet.
"""

import os
import pickle
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

from finpulse.analysis.indicators import compute_all
from finpulse.logger import get_logger

logger = get_logger("analysis.ml_model")

# Paths
MODEL_DIR = Path(__file__).parent.parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "signal_model.pkl"


class MLEnsembleModel:
    """Soft voting ensemble combining RandomForest and XGBoost classifiers."""

    def __init__(self) -> None:
        self.rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42,
            n_jobs=-1,
        )
        self.xgb = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            random_state=42,
            n_jobs=-1,
            eval_metric="logloss",
        )
        self.is_trained = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit both models to the training data."""
        logger.info(f"Training ensemble model on {len(X)} samples...")
        self.rf.fit(X, y)
        self.xgb.fit(X, y)
        self.is_trained = True

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict soft-voting probabilities (class 1)."""
        if not self.is_trained:
            raise ValueError("Ensemble model is not trained yet.")
            
        rf_probs = self.rf.predict_proba(X)[:, 1]
        xgb_probs = self.xgb.predict_proba(X)[:, 1]
        
        # Soft voting average
        return (rf_probs + xgb_probs) / 2.0

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict binary class (0 or 1)."""
        probs = self.predict_proba(X)
        return (probs >= 0.5).astype(int)


def prepare_features(df: pd.DataFrame, include_target: bool = True) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
    """Compute indicators and build the feature matrix for ML model.

    Features:
        - rsi: RSI value
        - macd_hist: MACD Histogram
        - bb_pct_b: Bollinger Bands %B (percent B)
        - ema_ratio_9_21: Ratio of EMA_9 / EMA_21
        - ema_ratio_50_200: Ratio of EMA_50 / EMA_200
        - price_to_ema_9: Ratio of Close / EMA_9
        - vol_ratio: Volume / 5-day SMA Volume
    """
    ti = compute_all(df)
    
    # Feature DF
    features = pd.DataFrame(index=df.index)
    features["rsi"] = ti["rsi"]
    features["macd_hist"] = ti["macd"]["histogram"]
    
    # Bollinger %B
    denom = ti["bollinger"]["upper"] - ti["bollinger"]["lower"]
    features["bb_pct_b"] = (df["Close"] - ti["bollinger"]["lower"]) / denom.replace(0, 1e-6)
    
    # EMA ratios
    emas = ti["ema"]
    features["ema_ratio_9_21"] = emas[9] / emas[21].replace(0, 1e-6)
    features["ema_ratio_50_200"] = emas[50] / emas[200].replace(0, 1e-6)
    features["price_to_ema_9"] = df["Close"] / emas[9].replace(0, 1e-6)
    
    # Volume SMA ratio
    features["vol_ratio"] = df["Volume"] / df["Volume"].rolling(5).mean().replace(0, 1e-6)
    
    if include_target:
        # Target label: 1 if next-day close > today's close, else 0
        target = (df["Close"].shift(-1) > df["Close"]).astype(int)
        
        # Drop rows with NaNs (due to lagging indicators or missing shifted target)
        valid_mask = features.notna().all(axis=1) & target.notna()
        return features[valid_mask], target[valid_mask]
    else:
        # For prediction, we just need the last row or non-NaN rows
        valid_mask = features.notna().all(axis=1)
        return features[valid_mask], None


def train_model(tickers: Optional[List[str]] = None, years: int = 3) -> Dict[str, float]:
    """Download historical data for specified tickers, train model, and save to disk."""
    if not tickers:
        # Curated list of high-liquidity Nifty 50 tickers to train on
        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS", "LT.NS"]
        
    logger.info(f"Downloading historical data for training: {tickers} ({years} years)...")
    
    all_features = []
    all_targets = []
    
    for ticker_sym in tickers:
        try:
            ticker = yf.Ticker(ticker_sym)
            df = ticker.history(period=f"{years}y")
            if len(df) < 100:
                continue
                
            X, y = prepare_features(df, include_target=True)
            all_features.append(X)
            all_targets.append(y)
        except Exception as e:
            logger.error(f"Failed to process training data for {ticker_sym}: {e}")
            
    if not all_features:
        raise ValueError("No training data could be fetched.")
        
    X_all = pd.concat(all_features)
    y_all = pd.concat(all_targets)
    
    # Chronological split to avoid lookahead bias (80% train, 20% test)
    split_idx = int(len(X_all) * 0.8)
    X_train, X_test = X_all.iloc[:split_idx], X_all.iloc[split_idx:]
    y_train, y_test = y_all.iloc[:split_idx], y_all.iloc[split_idx:]
    
    # Train model
    model = MLEnsembleModel()
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
    }
    
    logger.info(f"Model trained successfully. Test Metrics: {metrics}")
    
    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
        
    logger.info(f"Saved trained model to {MODEL_PATH}")
    return metrics


def load_model() -> Optional[MLEnsembleModel]:
    """Load the trained ensemble model from disk."""
    if not MODEL_PATH.exists():
        logger.warning(f"No model found at {MODEL_PATH}. Call train_model() first.")
        return None
        
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
            
        # Check model age and suggest retrain if > 30 days
        mtime = datetime.fromtimestamp(MODEL_PATH.stat().st_mtime)
        age_days = (datetime.now() - mtime).days
        if age_days > 30:
            logger.warning(f"Trained model is {age_days} days old. Suggest retraining.")
            
        return model
    except Exception as e:
        logger.error(f"Failed to load model from disk: {e}")
        return None


def predict_signal(df: pd.DataFrame) -> Tuple[str, float]:
    """Predict price movement direction using the loaded model.

    If model is not found, falls back to a rule-based indicator vote.

    Returns:
        Tuple[str, float]: ("BUY"/"SELL"/"HOLD", confidence percentage)
    """
    model = load_model()
    
    # Prepare features for the last row
    X, _ = prepare_features(df, include_target=False)
    if X.empty:
        logger.warning("Not enough data to extract features for prediction.")
        return "HOLD", 50.0
        
    last_row_features = X.tail(1)
    
    # 1. ML-based Prediction
    if model is not None:
        try:
            prob = float(model.predict_proba(last_row_features)[0])
            if prob >= 0.55:
                # Class 1 is UP -> BUY
                confidence = prob * 100
                return "BUY", confidence
            elif prob <= 0.45:
                # Class 0 is DOWN -> SELL
                confidence = (1 - prob) * 100
                return "SELL", confidence
            else:
                return "HOLD", 50.0
        except Exception as e:
            logger.error(f"Error predicting with ML model: {e}")
            # Fall through to rule-based fallback
            
    # 2. Rule-based Fallback (Technical Indicator Vote)
    logger.info("Using indicator-based rule vote fallback...")
    
    ti = compute_all(df)
    last_idx = df.index[-1]
    
    rsi = float(ti["rsi"].loc[last_idx])
    macd_hist = float(ti["macd"]["histogram"].loc[last_idx])
    bb_upper = float(ti["bollinger"]["upper"].loc[last_idx])
    bb_lower = float(ti["bollinger"]["lower"].loc[last_idx])
    close = float(df["Close"].loc[last_idx])
    
    # Rule points
    votes = 0
    total_checks = 0
    
    # RSI
    if not np.isnan(rsi):
        total_checks += 1
        if rsi < 35:
            votes += 1
        elif rsi > 65:
            votes -= 1
            
    # MACD
    if not np.isnan(macd_hist):
        total_checks += 1
        if macd_hist > 0:
            votes += 1
        else:
            votes -= 1
            
    # Bollinger Bands
    if not np.isnan(bb_upper) and not np.isnan(bb_lower):
        total_checks += 1
        bb_width = bb_upper - bb_lower
        if bb_width > 0:
            pct_b = (close - bb_lower) / bb_width
            if pct_b < 0.15:
                votes += 1
            elif pct_b > 0.85:
                votes -= 1
                
    if total_checks == 0:
        return "HOLD", 50.0
        
    vote_ratio = votes / total_checks
    
    if vote_ratio >= 0.33:
        confidence = 50 + (vote_ratio * 50)
        return "BUY", float(confidence)
    elif vote_ratio <= -0.33:
        confidence = 50 + (abs(vote_ratio) * 50)
        return "SELL", float(confidence)
    else:
        return "HOLD", 50.0
