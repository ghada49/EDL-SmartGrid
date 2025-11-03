from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import cases as cases_router
from .routers import inspections as inspections_router
from .routers import reports as reports_router


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

    app.include_router(auth_router.router)
    app.include_router(users_router.router)
    app.include_router(cases_router.router)
    app.include_router(inspections_router.router)
    app.include_router(reports_router.router)

    return app


app = create_app()
