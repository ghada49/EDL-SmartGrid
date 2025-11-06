from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import cases as cases_router
from .routers import inspections as inspections_router
from .routers import reports as reports_router
from .routers import ml_buildings as ml_router
from .routers import data_ops as ops_router
from . import models  # ensure package exists
from .models import user as user_model  # import to register
from .models import ops as ops_models  # import to register


def create_app() -> FastAPI:
    app = FastAPI(title="EECE-490 Backend", version="0.1.0")

    # CORS (allow Vite dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure DB tables exist after models are imported
    Base.metadata.create_all(bind=engine)

    app.include_router(auth_router.router)
    app.include_router(users_router.router)
    app.include_router(cases_router.router)
    app.include_router(inspections_router.router)
    app.include_router(reports_router.router)
    app.include_router(ml_router.router, prefix="/ml", tags=["Model Scoring"])
    app.include_router(ops_router.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
