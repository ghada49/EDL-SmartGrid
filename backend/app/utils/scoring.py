# utils/scoring.py
import numpy as np
import pandas as pd
import joblib
import os
from .preprocess import add_derived

# Try to import TensorFlow/Keras
try:
    import tensorflow as tf
except ImportError:
    tf = None

# ------------------------------------------------------------------
# Load model + scaler once when the API starts
# ------------------------------------------------------------------
MODEL_PATH = "app/saved_models/ae_model.h5"
SCALER_PATH = "app/saved_models/scaler.joblib"

ae_model, scaler = None, None
if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH) and tf is not None:
    try:
        ae_model = tf.keras.models.load_model(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        print("[OK] Autoencoder and scaler loaded successfully.")
    except Exception as e:
        print("[WARN] Error loading model/scaler:", e)
else:
    print("[WARN] Autoencoder or scaler not found. Using dummy mode.")

# ------------------------------------------------------------------
# Fraud scoring function
# ------------------------------------------------------------------
def score_row(row: pd.Series, threshold: float = 0.65):
    """
    Compute fraud score using a trained Autoencoder.
    If model/scaler are missing, fall back to dummy logic.
    """
    # Step 1: prepare features
    df = add_derived(pd.DataFrame([row]))

    # Step 2: select same features used during training
    FEATURES = ["kwh_per_m2", "kwh_per_apartment", "kwh_per_floor", "age"]
    X = df[FEATURES].values

    # Step 3: if model not available, fallback
    if ae_model is None or scaler is None:
        score = 0.5
        return {
            "score": score,
            "is_fraud": False,
            "components": {"note": "Autoencoder not loaded (dummy mode)"},
            "peer_group": {"function": row.get("function")}
        }

    # Step 4: scale input
    X_scaled = scaler.transform(X)

    # Step 5: predict reconstruction
    X_pred = ae_model.predict(X_scaled)

    # Step 6: compute reconstruction error (MSE)
    mse = np.mean(np.square(X_scaled - X_pred))

    # Step 7: normalize to 0–1 (optional)
    score = float(np.tanh(mse * 10))

    # Step 8: compare to threshold
    is_fraud = score >= threshold

    return {
        "score": round(score, 3),
        "is_fraud": bool(is_fraud),
        "components": {"reconstruction_error": round(mse, 6)},
        "peer_group": {"function": row.get("function")}
    }
