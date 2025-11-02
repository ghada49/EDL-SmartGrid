from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models as dbmodels
from app.utils.validation import validate_csv, df_to_buildings
from app.utils.pdf import create_inspection_report
from app.utils.drift import simple_drift_report
import os, shutil, time

router = APIRouter(prefix="/ops", tags=["Data & Reporting"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/upload_dataset")
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        tmp_path = f"data/_upload_{int(time.time())}_{file.filename}"
        with open(tmp_path, "wb") as f:
            f.write(content)
        df = validate_csv(tmp_path)
        n = df_to_buildings(df, db)
        # save a copy as "latest_ingested.csv" for drift reference
        ingested_path = "data/latest_ingested.csv"
        shutil.copyfile(tmp_path, ingested_path)
        return {"status": "ok", "rows_ingested": n, "saved_as": ingested_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)):
    # Simple aggregates
    total_buildings = db.query(dbmodels.Building).count()
    total_cases = db.query(dbmodels.Case).count()
    total_tickets = db.query(dbmodels.Ticket).count()
    # mock anomaly count as 10% of buildings for now
    anomalies = int(total_buildings * 0.1)
    return {
        "total_buildings": total_buildings,
        "total_cases": total_cases,
        "total_tickets": total_tickets,
        "flagged_anomalies_estimate": anomalies
    }

@router.post("/models/upload")
async def upload_model(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save artifact
    repo_dir = "models_repo"
    os.makedirs(repo_dir, exist_ok=True)
    artifact_path = os.path.join(repo_dir, file.filename)
    content = await file.read()
    with open(artifact_path, "wb") as f:
        f.write(content)
    # Create metadata row
    mv = dbmodels.ModelVersion(filename=file.filename, is_active=False)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return {"status": "ok", "model_id": mv.id, "filename": file.filename}

@router.post("/model/activate")
def activate_model(model_id: int = Form(...), db: Session = Depends(get_db)):
    mv = db.query(dbmodels.ModelVersion).filter_by(id=model_id).first()
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    # Deactivate all
    db.query(dbmodels.ModelVersion).update({dbmodels.ModelVersion.is_active: False})
    # Activate selected
    mv.is_active = True
    db.commit()
    return {"status": "ok", "activated_model_id": model_id}

@router.post("/drift_report")
async def drift_report(file: UploadFile = File(...)):
    content = await file.read()
    tmp_path = f"data/_candidate_{int(time.time())}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)
    ref_path = "data/latest_ingested.csv"
    if not os.path.exists(ref_path):
        raise HTTPException(status_code=400, detail="No reference dataset. Upload a dataset first.")
    report = simple_drift_report(candidate_csv=tmp_path, reference_csv=ref_path)
    return report

@router.get("/report/pdf/{building_id}")
def generate_pdf(building_id: int, db: Session = Depends(get_db)):
    pdf_path = create_inspection_report(building_id, db)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Report not generated")
    return FileResponse(pdf_path, media_type="application/pdf", filename=os.path.basename(pdf_path))
