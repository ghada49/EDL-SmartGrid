import json, shutil
from pathlib import Path
from datetime import datetime

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
REGISTRY_FILE = Path(__file__).resolve().parent / "model_registry.json"
ACTIVE_MODEL = MODEL_DIR / "current_model.pkl"

def save_new_model_version(model_path: str):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    version = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dst = MODEL_DIR / f"model_{version}.pkl"

    shutil.copy(model_path, dst)
    shutil.copy(dst, ACTIVE_MODEL)

    entry = {
        "version": version,
        "path": str(dst),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }

    if REGISTRY_FILE.exists():
        registry = json.loads(REGISTRY_FILE.read_text())
    else:
        registry = []

    registry.append(entry)
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2))
    return version
