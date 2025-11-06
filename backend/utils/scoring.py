# utils/scoring.py
import numpy as np
import pandas as pd
import joblib
import os
from .preprocess import add_derived

try:
    import tensorflow as tf  # optional; falls back if missing
except ImportError:  # pragma: no cover
    tf = None


# Resolve artifact paths in repo (under models_repo)
MODEL_PATH = os.path.join("models_repo", "ae_model.h5")
SCALER_PATH = os.path.join("models_repo", "scaler.joblib")

ae_model, scaler = None, None
if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH) and tf is not None:
    try:
        ae_model = tf.keras.models.load_model(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        print("Autoencoder and scaler loaded successfully.")
    except Exception as e:  # pragma: no cover
        print("Error loading model/scaler:", e)
else:
    print("Autoencoder or scaler not found. Using dummy mode.")


def score_row(row: pd.Series, threshold: float = 0.65, medians: dict | None = None, mads: dict | None = None):
    """
    Compute fraud score using a trained Autoencoder if available.
    If model/scaler are missing, fall back to dummy logic.
    """
    df = add_derived(pd.DataFrame([row]))
    FEATURES = ["kwh_per_m2", "kwh_per_apartment", "kwh_per_floor", "age"]
    X = df[FEATURES].values

    if ae_model is None or scaler is None:
        score = 0.5
        return {
            "score": score,
            "is_fraud": False,
            "components": {"note": "Autoencoder not loaded (dummy mode)"},
            "peer_group": {"function": row.get("function")},
        }

    X_scaled = scaler.transform(X)
    X_pred = ae_model.predict(X_scaled)
    mse = np.mean(np.square(X_scaled - X_pred))
    score = float(np.tanh(mse * 10))
    is_fraud = score >= threshold

    return {
        "score": round(score, 3),
        "is_fraud": bool(is_fraud),
        "components": {"reconstruction_error": round(mse, 6)},
        "peer_group": {"function": row.get("function")},
    }

