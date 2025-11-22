# backend/ml/registry.py
import json
from pathlib import Path
from datetime import datetime, timezone
from .plots import generate_model_plots

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
REGISTRY_DIR = REPO_ROOT / "data" / "model_registry"
CURRENT_CARD = REGISTRY_DIR / "current_model_card.json"
HISTORY_FILE = REGISTRY_DIR / "history.json"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def save_new_model_version(
    scores_csv: Path,
    mode: str,
    duration_sec: float | None = None,
    source_path: str | None = None,
) -> dict:
    """
    Build a compact model card from the meta + stability JSON and persist:
      - data/model_registry/current_model_card.json
      - append to data/model_registry/history.json
    """
    scores_csv = Path(scores_csv).resolve()
    base = scores_csv.with_suffix("")  # .../anomaly_scores
    meta_path = Path(str(base) + "_meta.json")
    stab_path = Path(str(base) + "_stability.json")

    if not meta_path.exists():
        raise FileNotFoundError(f"Meta JSON not found at {meta_path}")
    if not stab_path.exists():
        raise FileNotFoundError(f"Stability JSON not found at {stab_path}")

    with open(meta_path, "r") as f:
        meta = json.load(f)
    with open(stab_path, "r") as f:
        stab = json.load(f)

    # Extract fused metrics
    evals = meta.get("evals", {})
    fused = evals.get("FUSED", {})
    sil = fused.get("silhouette")
    dunn = fused.get("dunn")
    dbi = fused.get("dbi")

    # Extract stability summary
    boot = stab.get("bootstrap", {})
    seed_sens = stab.get("seed_sensitivity", {})
    noise = stab.get("noise_robustness", {})

    # Infer simple data summary (optional)
    try:
        import pandas as pd
        df = pd.read_csv(scores_csv)
        n_samples = int(len(df))
        n_features = len(meta["feature_columns"])
    except Exception:
        n_samples = None
        n_features = None

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    # Use true training feature set, not all numeric columns in anomaly_scores.csv
    feat_cols = meta.get("feature_columns", [])
    n_features = len(feat_cols) if feat_cols else None

    # Determine version (history length + 1)
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            hist = json.load(f)
    else:
        hist = []

    # mark existing entries as inactive
    for entry in hist:
        entry["is_active"] = False

    version = len(hist) + 1

    card = {
        "model_id": "fused_if_lof_ae_ocsvm_copula",
        "version": version,
        "trained_at": _now_iso(),
        "mode": mode,
        "duration_sec": duration_sec,
        "data": {
            "n_samples": n_samples,
            "n_features": n_features,
            "source": source_path or "data/latest_ingested.csv",
        },
        "metrics": {
            "silhouette": sil,
            "dunn": dunn,
            "dbi": dbi,
        },
        "stability": {
            "bootstrap_spearman_rho": boot.get("spearman_rho_mean"),
            "bootstrap_jaccard_at_k": boot.get("jaccard_at_k_mean"),
            "bootstrap_ari": boot.get("ari_mean"),
            "noise_rho": noise.get("spearman_rho_mean"),
            "seed_rho": seed_sens.get("spearman_rho_mean"),
        },
        "hyperparams": {
            "contamination": meta.get("contamination"),
            "use_pca": meta.get("use_pca"),
            "use_fa": meta.get("use_fa"),
            "pca_components": meta.get("pca_components"),
        },
        "files": {
            "scores_csv": str(scores_csv.relative_to(REPO_ROOT)),
            "meta_json": str(meta_path.relative_to(REPO_ROOT)),
            "stability_json": str(stab_path.relative_to(REPO_ROOT)),
            "scaler": str(Path(str(base) + "_scaler.joblib").relative_to(REPO_ROOT)),
            "pca": str(Path(str(base) + "_pca.joblib").relative_to(REPO_ROOT))
                     if Path(str(base) + "_pca.joblib").exists()
                     else None,
            "residual_model": str(Path(str(base) + "_resid.joblib").relative_to(REPO_ROOT)),
        },
        "meta":meta,
    }
    card["is_active"] = True
    card["activated_at"] = _now_iso()
    generate_model_plots(scores_csv, REGISTRY_DIR)


    # Save current card
    with open(CURRENT_CARD, "w") as f:
        json.dump(card, f, indent=2)

    # Append to history
    hist.append(card)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)

    return card


def get_current_model_card() -> dict | None:
    if not CURRENT_CARD.exists():
        return None
    with open(CURRENT_CARD, "r") as f:
        return json.load(f)


def get_model_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def set_active_model_version(version: int) -> dict:
    """
    Re-point the active model card to a specific historical version.
    """
    if not HISTORY_FILE.exists():
        raise ValueError("No models have been registered yet")

    with open(HISTORY_FILE, "r") as f:
        hist = json.load(f)

    target = None
    for entry in hist:
        if entry.get("version") == version:
            entry["is_active"] = True
            entry["activated_at"] = _now_iso()
            target = entry
        else:
            entry["is_active"] = False

    if target is None:
        raise ValueError(f"Model version {version} not found")

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    with open(CURRENT_CARD, "w") as f:
        json.dump(target, f, indent=2)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)

    return target
