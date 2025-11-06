Backend (FastAPI) — Auth/RBAC + ML/Ops

Quick Start (dev)
- Create and activate a venv
  - Windows (PowerShell)
    - `py -m venv .venv`
    - `.venv\Scripts\Activate.ps1`
  - macOS/Linux
    - `python3 -m venv .venv`
    - `source .venv/bin/activate`
- Install deps: `pip install -r backend/requirements.txt`
- Create env file `backend/.env` (example):
  - `DB_URL=sqlite:///./app.db`
  - `JWT_SECRET=change_me`
  - `JWT_ALG=HS256`
  - `ACCESS_TOKEN_EXPIRE_MINUTES=60`
- Run API (from repo root):
  - `python -m uvicorn backend.app:app --reload`
- Check:
  - Health: http://127.0.0.1:8000/health
  - Docs:   http://127.0.0.1:8000/docs

Seed Admin (optional)
- `python -m backend.seed_admin`
- Optional env: `ADMIN_EMAIL`, `ADMIN_PASSWORD`

Endpoints (selected)
- Auth
  - `POST /auth/signup` — Citizen signup
  - `POST /auth/login` — returns Bearer token
  - `POST /auth/signup/admin` — Admin-only create users
- Users
  - `GET /users/me` — current user
  - `GET /users` — list users (Admin/Manager)
  - `PATCH /users/{id}/role` — change role (Admin/Manager policy)
  - `PATCH /users/{id}/suspend` — suspend/reactivate (Admin)
- Reports/Inspections
  - `GET /reports/kpi` — basic KPIs (Manager/Admin)
  - `POST /inspections/assign` — assign inspection (Inspector/Manager/Admin)
- ML Scoring
  - `POST /ml/v1/score` — score single building
  - `POST /ml/v1/batch/score` — batch scoring
- Data & Ops
  - `GET /ops/health`
  - `POST /ops/upload_dataset` — CSV ingest to DB
  - `GET /ops/public/stats` — simple aggregates
  - `POST /ops/models/upload` — upload model artifact
  - `POST /ops/model/activate` — set active model
  - `GET /ops/report/pdf/{building_id}` — generate PDF report

Notes
- CORS allows `http://localhost:5173` for local frontend.
- SQLite default is fine for dev. For Postgres, set `DB_URL` accordingly and ensure connectivity (`psycopg2-binary` is included).

