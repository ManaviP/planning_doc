"""Random Forest model alternative for workload behavior prediction.

This module provides an easy, scikit-learn based alternative to the LSTM model.
It integrates seamlessly by reusing the same feature engineering logic from dl_model,
but trains significantly faster and is highly interpretable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib  # type: ignore[import]
import torch

from backend.models import WorkloadRequest
from backend.prediction.dl_model import (
    ARTIFACT_DIR,
    WINDOW,
    DLPrediction,
    _to_feature_row,
    build_training_dataset,
)

RF_CHECKPOINT_PATH = ARTIFACT_DIR / "rf_predictor.joblib"

_RF_MODEL_CACHE = None


def _ensure_artifact_dir() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def train_rf_model(metrics_rows: list[dict]) -> dict[str, float]:
    """Train a RandomForestRegressor using the existing PyTorch feature dataset."""
    from sklearn.ensemble import RandomForestRegressor  # type: ignore[import]

    x_seq, x_work, y = build_training_dataset(metrics_rows)
    
    # Flatten the sequence window and concatenate with workload features
    samples = x_seq.shape[0]
    x_flat = torch.cat([x_seq.reshape(samples, -1), x_work], dim=1).numpy()
    y_flat = y.numpy()

    # Train a fast Random Forest with 50 trees
    model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(x_flat, y_flat)

    _ensure_artifact_dir()
    joblib.dump(model, RF_CHECKPOINT_PATH)

    global _RF_MODEL_CACHE
    _RF_MODEL_CACHE = model

    # Calculate basic training R^2 score for logging
    score = float(model.score(x_flat, y_flat))
    return {"samples": float(samples), "r2_score": score, "model": "RandomForest"}


def load_rf_model(force_reload: bool = False):
    global _RF_MODEL_CACHE
    if _RF_MODEL_CACHE is not None and not force_reload:
        return _RF_MODEL_CACHE

    if not RF_CHECKPOINT_PATH.exists():
        return None

    try:
        model = joblib.load(RF_CHECKPOINT_PATH)
        _RF_MODEL_CACHE = model
        return model
    except Exception:
        return None


def rf_infer(
    history_window: Iterable[dict],
    workload_features: dict,
    model=None,
) -> DLPrediction | None:
    """Predict outcomes using the trained Random Forest model."""
    rows = list(history_window)
    if len(rows) < WINDOW:
        return None

    model = model or load_rf_model()
    if model is None:
        return None

    sequence_rows = rows[-WINDOW:]
    seq_tensor = torch.tensor([[_to_feature_row(r) for r in sequence_rows]], dtype=torch.float32)

    w_tensor = torch.tensor(
        [[
            float(workload_features.get("cpu_cores", 0.0)),
            float(workload_features.get("memory_gb", 0.0)),
            float(workload_features.get("gpu_units", 0.0) or 0.0),
            float(workload_features.get("priority", 1.0)),
        ]],
        dtype=torch.float32,
    )

    # Flatten for RF
    samples = seq_tensor.shape[0]
    x_flat = torch.cat([seq_tensor.reshape(samples, -1), w_tensor], dim=1).numpy()

    out = model.predict(x_flat)[0].tolist()

    latency = max(float(out[0]), 1.0)
    failure = min(max(float(out[1]), 0.0), 0.99)
    demand = min(max(float(out[2]), 0.0), 2.0)
    congestion = min(max(float(out[3]), 0.0), 100.0)

    return DLPrediction(
        predicted_latency_ms=latency,
        predicted_failure_probability=failure,
        predicted_resource_demand=demand,
        predicted_congestion=congestion,
    )
