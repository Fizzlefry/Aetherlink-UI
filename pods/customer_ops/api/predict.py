"""
Real-time conversion prediction using trained model.
Loads model.json and computes pred_prob for incoming leads.
"""
import json
import time
from pathlib import Path
from typing import Any

from prometheus_client import Gauge

from .logger import logger

# Model metrics
MODEL_AUC = Gauge("lead_model_auc", "Model AUC score from training")
MODEL_VERSION = Gauge("lead_model_version", "Model version timestamp")
MODEL_N_TRAIN = Gauge("lead_model_n_train", "Number of training samples")
MODEL_DRIFT_SCORE = Gauge("lead_model_drift_score", "Feature drift score (std deviations from training)")
MODEL_LAST_RELOAD = Gauge("lead_model_last_reload_ts", "Timestamp of last model reload")

# Safety thresholds
MIN_AUC_THRESHOLD = 0.65  # Refuse to load models below this AUC

_MODEL = None
_MODEL_LOAD_TIME = 0
_FEATURE_STATS = {"score": [], "details_len": [], "hour": []}  # Running stats for drift


def load_model() -> dict[str, Any] | None:
    """Load model from JSON file and update metrics."""
    global _MODEL, _MODEL_LOAD_TIME
    
    model_file = Path(__file__).parent / "model.json"
    if not model_file.exists():
        logger.warning("prediction_model_not_found", extra={"path": str(model_file)})
        return None
    
    try:
        with open(model_file) as f:
            _MODEL = json.load(f)
        _MODEL_LOAD_TIME = time.time()
        
        # Update Prometheus metrics
        metrics = _MODEL.get("metrics", {})
        if metrics.get("auc"):
            MODEL_AUC.set(metrics["auc"])
        if _MODEL.get("version"):
            MODEL_VERSION.set(_MODEL["version"])
        if metrics.get("n_train"):
            MODEL_N_TRAIN.set(metrics["n_train"])
        
        logger.info("prediction_model_loaded", extra={
            "version": _MODEL.get("version"),
            "auc": metrics.get("auc"),
            "n_train": metrics.get("n_train"),
        })
        return _MODEL
    except Exception as e:
        logger.error("prediction_model_load_failed", extra={"error": str(e)})
        return None


def reload_model(min_auc: float = MIN_AUC_THRESHOLD) -> dict[str, Any]:
    """
    Force reload model from disk with AUC validation.
    Used by /ops/reload-model endpoint.
    
    Args:
        min_auc: Minimum acceptable AUC (default 0.65). Rejects models below this.
    
    Returns:
        Model info dict or error dict with validation failure reason.
    """
    global _MODEL
    
    # Load new model from disk
    model_file = Path(__file__).parent / "model.json"
    if not model_file.exists():
        return {"ok": False, "error": "Model file not found", "path": str(model_file)}
    
    try:
        with open(model_file) as f:
            candidate_model = json.load(f)
        
        # Validate AUC threshold
        auc = candidate_model.get("metrics", {}).get("auc", 0.0)
        if auc < min_auc:
            logger.warning("model_reload_rejected_low_auc", extra={
                "auc": auc,
                "min_auc": min_auc,
                "version": candidate_model.get("version"),
            })
            return {
                "ok": False,
                "error": "Model AUC below threshold",
                "auc": auc,
                "min_auc": min_auc,
                "rejected": True,
            }
        
        # Clear cache and load validated model
        _MODEL = None
        result = load_model()
        
        if result:
            MODEL_LAST_RELOAD.set(time.time())
            logger.info("model_reloaded_success", extra={
                "version": result.get("version"),
                "auc": auc,
                "n_train": result.get("metrics", {}).get("n_train"),
            })
            return {
                "ok": True,
                "version": result.get("version"),
                "auc": auc,
                "n_train": result.get("metrics", {}).get("n_train"),
                "load_time": _MODEL_LOAD_TIME,
                "validated": True,
            }
        else:
            return {"ok": False, "error": "Model load failed after validation"}
            
    except Exception as e:
        logger.error("model_reload_failed", extra={"error": str(e)})
        return {"ok": False, "error": str(e)}


def _update_drift_stats(score: float, details_len: int, hour: int) -> None:
    """
    Track feature statistics for drift detection.
    Maintains rolling window of last 1000 predictions.
    """
    global _FEATURE_STATS
    
    _FEATURE_STATS["score"].append(score)
    _FEATURE_STATS["details_len"].append(details_len)
    _FEATURE_STATS["hour"].append(hour)
    
    # Keep rolling window
    max_window = 1000
    for key in _FEATURE_STATS:
        if len(_FEATURE_STATS[key]) > max_window:
            _FEATURE_STATS[key] = _FEATURE_STATS[key][-max_window:]


def calculate_drift_score() -> float:
    """
    Calculate feature drift as max z-score vs training distribution.
    Returns number of standard deviations from training mean.
    """
    global _MODEL, _FEATURE_STATS
    
    if not _MODEL or not any(_FEATURE_STATS.values()):
        return 0.0
    
    try:
        import statistics
        
        train_stats = _MODEL.get("feature_stats", {})
        if not train_stats:
            return 0.0
        
        z_scores = []
        
        # Calculate z-score for each tracked feature
        for feat_name in ["score", "details_len", "hour"]:
            if feat_name not in train_stats or not _FEATURE_STATS[feat_name]:
                continue
            
            train_mean = train_stats[feat_name].get("mean", 0)
            train_std = train_stats[feat_name].get("std", 1)
            
            if train_std == 0:
                continue
            
            # Current production mean
            prod_mean = statistics.mean(_FEATURE_STATS[feat_name])
            z_score = abs((prod_mean - train_mean) / train_std)
            z_scores.append(z_score)
        
        # Return max drift (worst feature)
        drift = max(z_scores) if z_scores else 0.0
        MODEL_DRIFT_SCORE.set(drift)
        
        return drift
        
    except Exception as e:
        logger.error("drift_calculation_failed", extra={"error": str(e)})
        return 0.0


def predict(
    score: float,
    intent: str,
    sentiment: str,
    urgency: str,
    details: str,
    tenant: str,
    created_at: int,
) -> float | None:
    """
    Predict conversion probability for a lead.
    Tracks features for drift detection.
    Returns float in [0, 1] or None if model not available.
    """
    global _MODEL
    
    if _MODEL is None:
        _MODEL = load_model()
        if _MODEL is None:
            return None
    
    try:
        from datetime import datetime
        
        # Feature engineering
        details_len = len(details)
        hour_of_day = datetime.fromtimestamp(created_at).hour if created_at > 0 else 12
        tenant_hash = hash(tenant) % 10000
        
        # Track features for drift detection
        _update_drift_stats(score, details_len, hour_of_day)
        
        # Encode categoricals
        encoders = _MODEL.get('encoders', {})
        intent_enc = encoders.get('intent', {}).get(intent, 0)
        sentiment_enc = encoders.get('sentiment', {}).get(sentiment, 0)
        urgency_enc = encoders.get('urgency', {}).get(urgency, 0)
        
        # Build feature vector (must match training order)
        features = [
            score,
            details_len,
            hour_of_day,
            tenant_hash,
            intent_enc,
            sentiment_enc,
            urgency_enc,
        ]
        
        # Compute logistic regression prediction
        coeffs = _MODEL.get('coefficients', [])
        intercept = _MODEL.get('intercept', 0.0)
        
        if not coeffs:
            return None
        
        # Dot product + intercept
        z = intercept + sum(f * c for f, c in zip(features, coeffs))
        
        # Sigmoid
        pred_prob = 1.0 / (1.0 + (2.71828 ** (-z)))
        
        return max(0.0, min(1.0, pred_prob))  # Clamp to [0, 1]
        
    except Exception as e:
        logger.error("prediction_failed", extra={"error": str(e)})
        return None


def get_model_info() -> dict[str, Any]:
    """Get model metadata for monitoring."""
    global _MODEL, _MODEL_LOAD_TIME
    
    if _MODEL is None:
        return {"loaded": False}
    
    return {
        "loaded": True,
        "version": _MODEL.get("version"),
        "load_time": _MODEL_LOAD_TIME,
        "metrics": _MODEL.get("metrics", {}),
    }
