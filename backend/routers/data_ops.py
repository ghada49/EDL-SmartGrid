from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import ops as dbmodels
from ..utils.validation import (
    validate_csv,
    df_to_buildings,
    EXPECTED_COLUMNS,
    calculate_missingness,
    compute_dq,
)
from ..utils.pdf import create_inspection_report
from ..utils.drift import simple_drift_report
import os, shutil, time
from ..models.dataset_version import DatasetVersion
from ..deps import require_roles
from typing import Optional, List
from ..ml.inference import score_new_dataset, NoActiveModelError
import re
import pandas as pd

router = APIRouter(prefix="/ops", tags=["Data & Reporting"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/upload_dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("Admin")),
):
    try:
        # Security: restrict extensions and size, sanitize name
        allowed_ext = {".csv", ".xlsx", ".xls"}
        orig_name = file.filename or "upload"
        ext = os.path.splitext(orig_name)[1].lower()
        if ext not in allowed_ext:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        content = await file.read()
        if len(content) > 20 * 1024 * 1024:  # 20MB
            raise HTTPException(status_code=400, detail="File too large (20MB limit)")

        os.makedirs("data", exist_ok=True)
        os.makedirs("data/uploads", exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_name)
        tmp_path = f"data/uploads/_upload_{int(time.time())}_{safe}"
        with open(tmp_path, "wb") as f:
            f.write(content)
        df = validate_csv(tmp_path)
        # Data quality basics
        dq = compute_dq(df)

        # Prepare drift report against previous latest, before updating it
        drift_columns = []
        ref_path = "data/latest_ingested.csv"
        if os.path.exists(ref_path):
            ext = os.path.splitext(tmp_path)[1].lower()
            if ext in {".xlsx", ".xls"}:
                candidate_csv = tmp_path + ".csv"
                df.to_csv(candidate_csv, index=False)
            else:
                candidate_csv = tmp_path
            drift_columns = simple_drift_report(candidate_csv=candidate_csv, reference_csv=ref_path)["columns"]

        # Persist buildings into DB
        n = df_to_buildings(df, db)

        # Versioning: mark previous as archived, new as active
        db.query(DatasetVersion).update({DatasetVersion.status: "archived"})
        os.makedirs("data/datasets", exist_ok=True)
        # Keep the original filename for the stored snapshot, overwrite if same name
        snapshot_path = os.path.join("data/datasets", safe)
        df.to_csv(snapshot_path, index=False)
        # Also maintain a latest reference for drift (update after computing drift)
        df.to_csv("data/latest_ingested.csv", index=False)
        dataset_record = DatasetVersion(
            filename=orig_name,
            row_count=n,
            status="active",
            uploaded_by=getattr(current_user, "email", None) or getattr(current_user, "id", None),
        )
        db.add(dataset_record)
        db.commit()
        return {
            "status": "ok",
            "rows_ingested": n,
            "saved_as": snapshot_path,
            "dq": dq,
            "columns": drift_columns,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)):
    total_buildings = db.query(dbmodels.Building).count()
    total_cases = db.query(dbmodels.Case).count()
    total_tickets = db.query(dbmodels.Ticket).count()
    anomalies = int(total_buildings * 0.1)
    return {
        "total_buildings": total_buildings,
        "total_cases": total_cases,
        "total_tickets": total_tickets,
        "flagged_anomalies_estimate": anomalies,
    }


@router.post("/models/upload")
async def upload_model(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin")),
):
    repo_dir = "models_repo"
    os.makedirs(repo_dir, exist_ok=True)
    artifact_path = os.path.join(repo_dir, file.filename)
    content = await file.read()
    with open(artifact_path, "wb") as f:
        f.write(content)
    mv = dbmodels.ModelVersion(filename=file.filename, is_active=False)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return {"status": "ok", "model_id": mv.id, "filename": file.filename}


@router.post("/model/activate")
def activate_model(
    model_id: int = Form(...),
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin")),
):
    mv = db.query(dbmodels.ModelVersion).filter_by(id=model_id).first()
    if not mv:
        raise HTTPException(status_code=404, detail="Model not found")
    db.query(dbmodels.ModelVersion).update({dbmodels.ModelVersion.is_active: False})
    mv.is_active = True
    db.commit()
    return {"status": "ok", "activated_model_id": model_id}


@router.post("/drift_report")
async def drift_report(file: UploadFile = File(...), _=Depends(require_roles("Admin"))):
    content = await file.read()
    os.makedirs("data", exist_ok=True)
    tmp_path = f"data/_candidate_{int(time.time())}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)
    ref_path = "data/latest_ingested.csv"
    if not os.path.exists(ref_path):
        raise HTTPException(status_code=400, detail="No reference dataset. Upload a dataset first.")
    # If uploaded file is Excel, convert to a temporary CSV before drift
    ext = os.path.splitext(tmp_path)[1].lower()
    candidate_csv = tmp_path
    if ext in {".xlsx", ".xls"}:
        import pandas as pd
        from ..utils.validation import EXPECTED_COLUMNS, ALIASES
        import re
        def _norm_name(s: str) -> str:
            s = str(s).strip().lower()
            s = s.replace("â€™", "'").replace("â€˜", "'").replace("â€œ", '"').replace("â€", '"')
            tokens = re.findall(r"[a-z0-9]+", s)
            tokens = [re.sub(r"s$", "", t) for t in tokens]
            return "".join(tokens)
        df = pd.read_excel(tmp_path)
        exp_map = { _norm_name(c): c for c in EXPECTED_COLUMNS }
        ren = {}
        for c in list(df.columns):
            k = _norm_name(c)
            if k in exp_map:
                ren[c] = exp_map[k]
            elif k in ALIASES:
                ren[c] = ALIASES[k]
        if ren:
            df = df.rename(columns=ren)
        candidate_csv = tmp_path + ".csv"
        df.to_csv(candidate_csv, index=False)
    report = simple_drift_report(candidate_csv=candidate_csv, reference_csv=ref_path)
    return report

@router.post("/analyze")
async def analyze_dataset(
    file: UploadFile = File(...),
    _=Depends(require_roles("Admin")),
):
    """
    Return data quality metrics and drift in one call without ingesting.
    - Computes full rule-aware DQ (row_count, duplicates, per-column stats)
    - Compares against latest ingested snapshot if available
    """
    content = await file.read()
    os.makedirs("data", exist_ok=True)
    tmp_path = f"data/_analyze_{int(time.time())}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(content)

    df = validate_csv(tmp_path)
    dq = compute_dq(df)

    # Drift vs latest ingested if present
    ref_path = "data/latest_ingested.csv"
    columns = []
    if os.path.exists(ref_path):
        ext = os.path.splitext(tmp_path)[1].lower()
        if ext in {".xlsx", ".xls"}:
            candidate_csv = tmp_path + ".csv"
            df.to_csv(candidate_csv, index=False)
        else:
            candidate_csv = tmp_path
        columns = simple_drift_report(candidate_csv=candidate_csv, reference_csv=ref_path)["columns"]

    return {"dq": dq, "columns": columns}

@router.post("/infer-and-create-cases")
async def infer_and_create_cases(
    file: UploadFile = File(...),
    top_percent: float = Form(5.0),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("Manager", "Admin")),
):
    """
    1) Take a CSV/Excel file with *the same schema as the ingested dataset*.
    2) Run the exact same preprocessing pipeline as training.
    3) Load the active fused model's scaler/PCA; compute anomaly scores.
    4) Pick the top X% anomalies.
    5) For each anomaly row:
         - Try to map its FID to an existing Building.
         - Create a new Case with status 'New' (unassigned).
         - Log a CaseActivity 'CREATE'.
    6) Return a compact list of anomalies + created case IDs.
    """
    # Basic sanity check for the manager input
    if top_percent <= 0 or top_percent > 50:
        raise HTTPException(
            status_code=400,
            detail="top_percent must be in (0, 50]. Example: 5 for top 5%.",
        )

    # Save uploaded file temporarily
    os.makedirs("data/tmp", exist_ok=True)
    safe_name = file.filename or "inference_upload"
    tmp_path = f"data/tmp/_infer_{int(time.time())}_{safe_name}"

    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    # Validate / normalize the CSV (same as upload_dataset)
    try:
        df = validate_csv(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}")

    # Run scoring with the active model
    try:
        df_scored, df_top = score_new_dataset(df, top_percent=top_percent)
    except NoActiveModelError as e:
        # No trained/active model in the registry
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Bubble up preprocessing / scaler shape errors etc.
        raise HTTPException(status_code=400, detail=f"Inference failed: {e}")

    anomalies: List[dict] = []

    creator = getattr(current_user, "email", None) or getattr(current_user, "id", None)

    # Helper: resolve building by FID if possible
    def _find_building_id(row) -> Optional[int]:
        fid_val = None
        if "FID" in row and not pd.isna(row["FID"]):
            fid_val = int(row["FID"])
        elif "fid" in row and not pd.isna(row["fid"]):
            fid_val = int(row["fid"])

        if fid_val is None:
            return None

        # Check if a Building with this id exists
        b = db.query(dbmodels.Building).filter(dbmodels.Building.id == fid_val).first()
        return b.id if b else None

    # Create Cases for each anomaly row
    for _, r in df_top.iterrows():
        building_id = _find_building_id(r)

        # extract coords if present
        lat_val = None
        lng_val = None
        if "lat" in r and not pd.isna(r["lat"]):
            try:
                lat_val = float(r["lat"])
            except Exception:
                lat_val = None
        if "long" in r and not pd.isna(r["long"]):
            try:
                lng_val = float(r["long"])
            except Exception:
                lng_val = None

        # If no building found but coordinates exist, create a placeholder building so maps work
        if building_id is None and lat_val is not None and lng_val is not None:
            b = dbmodels.Building(
                building_name=f"Anomaly #{int(r.get('rank', 0))}" if "rank" in r else "Anomaly",
                latitude=lat_val,
                longitude=lng_val,
            )
            db.add(b)
            db.flush()
            building_id = b.id
        elif building_id is not None:
            # backfill coords on existing building if missing
            b = db.query(dbmodels.Building).get(building_id)
            if b and (b.latitude is None or b.longitude is None) and lat_val is not None and lng_val is not None:
                b.latitude = lat_val
                b.longitude = lng_val
                db.add(b)

        case = dbmodels.Case(
            building_id=building_id,
            anomaly_id=None,  # optional - depends on your schema
            notes="Case created from anomaly scoring",
            created_by=creator,
            status="New",  # unassigned, will appear in Case Management
        )
        db.add(case)
        db.flush()  # get case.id without committing yet

        activity = dbmodels.CaseActivity(
            case_id=case.id,
            actor=creator or "system",
            action="CREATE",
            note=f"Case created from anomaly scoring (fused_score={float(r['fused_score']):.3f})",
        )
        db.add(activity)

        anomalies.append(
            {
                "rank": int(r.get("rank", 0)),
                "FID": r.get("FID") if "FID" in r else r.get("fid"),
                "building_id": building_id,
                "lat": lat_val,
                "long": lng_val,
                "fused_score": float(r["fused_score"]),
                "case_id": case.id,
            }
        )

    db.commit()

    return {
        "status": "ok",
        "top_percent": top_percent,
        "n_total_rows": int(len(df_scored)),
        "n_anomalies": len(anomalies),
        "anomalies": anomalies,
    }


@router.get("/report/pdf/{building_id}")
def generate_pdf(building_id: int, db: Session = Depends(get_db)):
    os.makedirs("data", exist_ok=True)
    pdf_path = create_inspection_report(building_id, db)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Report not generated")
    return FileResponse(pdf_path, media_type="application/pdf", filename=os.path.basename(pdf_path))

@router.get("/datasets/history")
def list_dataset_versions(db: Session = Depends(get_db), _=Depends(require_roles("Admin", "Manager"))):
    from ..models.dataset_version import DatasetVersion
    records = db.query(DatasetVersion).order_by(DatasetVersion.upload_time.desc()).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "rows": r.row_count,
            "uploaded_at": r.upload_time,
            "status": r.status,
        }
        for r in records
    ]




