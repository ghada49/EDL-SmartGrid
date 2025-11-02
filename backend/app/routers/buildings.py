
from fastapi import APIRouter
from app.models.schemas import Building, BatchIn, ScoreOut
from utils.preprocess import to_dataframe_one, add_derived
from utils.scoring import score_row
import pandas as pd

router = APIRouter(prefix="/v1", tags=["buildings"])

@router.post("/score", response_model=ScoreOut)
def score_api(b: Building):
    row = to_dataframe_one(b.model_dump()).iloc[0]
    res = score_row(row)
    return {"building_code": b.building_code, **res}

@router.post("/batch/score")
def batch_score(payload: BatchIn):
    rows = [to_dataframe_one(b.model_dump()).iloc[0] for b in payload.items]
    df = pd.DataFrame(rows)
    d2 = add_derived(df)
    med = {
        "kwh_per_m2": float(d2["kwh_per_m2"].median()),
        "kwh_per_apartment": float(d2["kwh_per_apartment"].median())
    }
    mad = {
        "kwh_per_m2": float((d2["kwh_per_m2"] - med["kwh_per_m2"]).abs().median() + 1e-6),
        "kwh_per_apartment": float((d2["kwh_per_apartment"] - med["kwh_per_apartment"]).abs().median() + 1e-6)
    }
    out = []
    for _, r in df.iterrows():
        s = score_row(r, medians=med, mads=mad)
        out.append({"building_code": r.get("building_code"), **s})
    summary = {"count": len(out), "flagged": sum(1 for r in out if r["is_fraud"])}
    return {"results": out, "summary": summary, "medians": med, "mads": mad}
