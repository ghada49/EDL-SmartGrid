from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db import Base, engine
from backend.routers.manager_scheduling import router as manager_sched_router
from backend.routers import manager_reports
from backend.routers import feedback
from backend.routers.auth import router as auth_router 
# backend/main.py
from backend.routers import inspector as inspector_router


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
app.include_router(inspector_router.router, prefix="/inspector", tags=["Inspector"])