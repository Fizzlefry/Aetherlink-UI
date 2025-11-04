#!/usr/bin/env python3
"""
Lightweight conversion prediction model trainer.
Trains logistic regression on outcome data and saves coefficients as JSON.

Usage:
    python scripts/train_model.py
"""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def train_model():
    """Train lightweight logistic regression model on outcome data."""
    try:
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import classification_report, roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        print("ERROR: Install sklearn and pandas: pip install scikit-learn pandas")
        sys.exit(1)

    # Load training data
    data_file = Path(__file__).parent.parent / "outcomes.csv"
    if not data_file.exists():
        print(f"ERROR: {data_file} not found. Download first:")
        print("  curl http://localhost:8000/ops/export/outcomes.csv > outcomes.csv")
        sys.exit(1)

    print(f"Loading data from {data_file}...")
    df = pd.read_csv(data_file)
    print(f"  Loaded {len(df)} samples")

    if len(df) < 10:
        print("WARNING: Less than 10 samples. Model will be weak. Collect more outcomes.")

    # Feature engineering
    # Encode categorical features
    le_intent = LabelEncoder()
    le_sentiment = LabelEncoder()
    le_urgency = LabelEncoder()

    df["intent_enc"] = le_intent.fit_transform(df["intent"])
    df["sentiment_enc"] = le_sentiment.fit_transform(df["sentiment"])
    df["urgency_enc"] = le_urgency.fit_transform(df["urgency"])

    # Select features
    feature_cols = [
        "score",
        "details_len",
        "hour_of_day",
        "tenant_hash",
        "intent_enc",
        "sentiment_enc",
        "urgency_enc",
    ]
    X = df[feature_cols].values
    y = df["label"].values

    print(f"  Features: {feature_cols}")
    print(f"  Positive class (booked): {y.sum()} ({y.mean()*100:.1f}%)")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.sum() > 1 else None
    )

    # Train model
    print("\nTraining logistic regression...")
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    print("\nModel Performance:")
    print(classification_report(y_test, y_pred, target_names=["not_booked", "booked"]))

    if len(set(y_test)) > 1:
        auc = roc_auc_score(y_test, y_pred_proba)
        print(f"AUC-ROC: {auc:.3f}")
    else:
        auc = None
        print("AUC: N/A (single class in test set)")

    # Calculate feature statistics for drift detection
    feature_stats = {
        "score": {
            "mean": float(df["score"].mean()),
            "std": float(df["score"].std()),
            "min": float(df["score"].min()),
            "max": float(df["score"].max()),
        },
        "details_len": {
            "mean": float(df["details_len"].mean()),
            "std": float(df["details_len"].std()),
            "min": int(df["details_len"].min()),
            "max": int(df["details_len"].max()),
        },
        "hour": {
            "mean": float(df["hour_of_day"].mean()),
            "std": float(df["hour_of_day"].std()),
            "min": int(df["hour_of_day"].min()),
            "max": int(df["hour_of_day"].max()),
        },
    }

    # Save model as JSON
    import time

    model_data = {
        "version": int(time.time()),  # Unix timestamp for tracking
        "features": feature_cols,
        "coefficients": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "encoders": {
            "intent": {cls: int(code) for code, cls in enumerate(le_intent.classes_)},
            "sentiment": {cls: int(code) for code, cls in enumerate(le_sentiment.classes_)},
            "urgency": {cls: int(code) for code, cls in enumerate(le_urgency.classes_)},
        },
        "feature_stats": feature_stats,
        "metrics": {
            "auc": auc,
            "n_train": len(X_train),
            "n_test": len(X_test),
            "baseline_rate": float(y.mean()),
        },
    }

    output_file = Path(__file__).parent.parent / "api" / "model.json"
    with open(output_file, "w") as f:
        json.dump(model_data, f, indent=2)

    print(f"\n✅ Model saved to {output_file}")
    print(f"   AUC: {auc:.3f if auc else 'N/A'}")
    print(f"   Baseline: {y.mean()*100:.1f}% booked")
    print("\nTo use in API:")
    print("  1. Restart API to load model")
    print("  2. pred_prob will appear in POST /v1/lead responses")


if __name__ == "__main__":
    train_model()
