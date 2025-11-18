from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db import Base, engine
from backend.routers.manager_scheduling import router as manager_sched_router
from backend.routers import reports as manager_reports
from backend.routers import feedback
from backend.routers.auth import router as auth_router 
# backend/main.py
from backend.routers import inspector as inspector_router
from backend.routers.users import router as users_router

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routers import ops_train  
from .ml.registry import get_current_model_card
from pathlib import Path

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EECE490 – Clean Backend (no app/)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(manager_sched_router)
app.include_router(manager_reports.router)
app.include_router(feedback.router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(inspector_router.router, prefix="/inspector", tags=["Inspector"])
app.include_router(ops_train.router)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
PLOTS_DIR = DATA_DIR / "plots"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(PLOTS_DIR)),
    name="plots",
)

app.mount(
    "/model_plots",
    StaticFiles(directory=str(PLOTS_DIR)),
    name="model_plots",
)

app.mount(
    "/data",
    StaticFiles(directory=str(DATA_DIR)),
    name="data",
)


@app.get("/debug/plots")
def debug_plots():
    """Return the plots directory and a short listing so we can debug 404s for /static/* files."""
    try:
        exists = PLOTS_DIR.exists()
        files = [p.name for p in PLOTS_DIR.iterdir()] if exists else []
    except Exception as e:
        return {"plots_dir": str(PLOTS_DIR), "error": str(e)}
    return {"plots_dir": str(PLOTS_DIR), "exists": exists, "files": files, "current_pca_fused": (PLOTS_DIR / "current_pca_fused.png").exists()}


@app.get("/plots/current_pca_fused.png")
def serve_current_pca_fused():
    """Serve the current_pca_fused.png directly (bypasses StaticFiles mount) for debugging."""
    p = PLOTS_DIR / "current_pca_fused.png"
    if not p.exists():
        return {"detail": "Not Found"}
    return FileResponse(path=str(p), media_type="image/png", filename=p.name)
