Backend (FastAPI) — Auth + RBAC

Run (dev)
- Create a virtualenv and install deps: `pip install -r backend/requirements.txt`
- Copy `backend/.env.example` to `backend/.env` and adjust values.
- Initialize DB tables automatically on first run.
- Start server: `uvicorn backend.app:app --reload`

Seed Admin
- `python -m backend.seed_admin`

Endpoints
- `POST /auth/signup` — Citizen signup (returns UserOut)
- `POST /auth/login` — returns Bearer token
- `POST /auth/signup/admin` — Admin-only create users (roles: Citizen/Inspector/Manager/Admin)
- `GET /users/me` — current user profile
- `GET /reports/kpi` — Manager/Admin only
- `POST /inspections/assign` — Inspector/Manager/Admin only

Notes
- `DB_URL` can be SQLite for local testing, e.g., `sqlite:///./app.db`.
- For Postgres, ensure `psycopg2-binary` is installed and DB is reachable.

