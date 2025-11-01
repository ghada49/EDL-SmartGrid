# EECE490 Week 1 — Student 3 (Platform & Ops)

This is a minimal, working scaffold to complete **Week 1** tasks for Student 3:
- Dataset upload + validation
- SQLite schema (users, buildings, cases, tickets, model_versions)
- Stats endpoint `/public/stats`
- PDF reporting utility (inspection sheet)
- Model upload + activate endpoints
- Simple dataset drift report

## How to run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Visit interactive docs at: `http://127.0.0.1:8000/docs`

## Endpoints
- `POST /upload_dataset` — upload CSV; validates and stores rows into `buildings` table.
- `GET /public/stats` — returns mock/aggregated stats.
- `POST /models/upload` — upload a model artifact file; stores metadata in DB and file to `models_repo/`.
- `POST /model/activate` — activate a model by id.
- `POST /drift_report` — compare uploaded CSV to the last ingested dataset and return simple drift flags.
- `GET /health` — health check.