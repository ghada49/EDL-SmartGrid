from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine
from app.routers import buildings, data_ops  # import both routers

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EECE490 - Electricity Fraud Detection Backend",
    version="0.2.0",
    description="Unified backend combining ML scoring and data operations."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# Register both routers
app.include_router(buildings.router, prefix="/ml", tags=["Model Scoring"])
app.include_router(data_ops.router, prefix="/ops", tags=["Data & Reporting"])

@app.get("/")
def root():
    return {"message": "EECE490 unified backend is running 🚀"}
