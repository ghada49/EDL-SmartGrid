# backend/app.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine

# Core routers
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import cases as cases_router
from .routers import inspections as inspections_router
from .routers import reports as reports_router
from .routers import data_ops as ops_router
from .routers import ops_train as ops_train_router
# Extra routers (tickets, scheduling, feedback, inspector)
from .routers import tickets
from .routers import tickets_admin
from .routers import manager_scheduling as manager_router
from .routers import inspector as inspector_router
from .routers.feedback import router as feedback_router

# Import models so SQLAlchemy registers them
from . import models  # ensure package exists
from .models import user as user_model   # noqa: F401
from .models import ops as ops_models    # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]
PLOTS_DIR = REPO_ROOT / "data" / "plots"


def create_app() -> FastAPI:
    app = FastAPI(title="EECE-490 Backend", version="0.1.0")

    # CORS (allow Vite dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure DB tables exist after models are imported
    Base.metadata.create_all(bind=engine)

    # --- Routers ---
    app.include_router(auth_router.router)
    app.include_router(users_router.router)
    app.include_router(cases_router.router)
    app.include_router(inspections_router.router)
    app.include_router(reports_router.router)

    # ML endpoints (no prefix for maximum compatibility with existing frontend)
    app.include_router(ops_train_router.router) 
    # Data ops / backoffice
    app.include_router(ops_router.router)

    # Tickets (citizen + admin)
    app.include_router(tickets.router)
    app.include_router(tickets_admin.router)

    # Manager scheduling dashboard
    app.include_router(manager_router.router)

    # Feedback routes
    app.include_router(feedback_router)

    # Inspector-facing routes
    app.include_router(
        inspector_router.router,
        prefix="/inspector",
        tags=["Inspector"],
    )

    app.mount("/static", StaticFiles(directory=PLOTS_DIR), name="plots")
    app.mount("/model_plots", StaticFiles(directory=PLOTS_DIR), name="model_plots")
    
    # Serve ticket attachments
    UPLOADS_DIR = REPO_ROOT / "data" / "uploads"
    app.mount("/data/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
