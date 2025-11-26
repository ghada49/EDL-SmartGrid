# ⚡ Backend – EDL Anomaly Detection & Inspection Platform

## 🔧 Setup

### 1. Create & activate a virtual environment

**Windows (PowerShell):**

```ps1
py -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Create environment file `backend/.env`

Example:

```
DB_URL=sqlite:///./app.db
JWT_SECRET=change_me
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 4. Run the API

From the repo root:

```bash
python -m uvicorn backend.app:app --reload
```

### 5. Test the server

* Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* Docs:   [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 6. Seed an Admin (optional)

```bash
python -m backend.seed_admin
```

Optional env for seeding: ADMIN_EMAIL, ADMIN_PASSWORD


---

## 🧾 Key Endpoints (Summary)

### 🔐 Auth

* `POST /auth/signup` — citizen signup
* `POST /auth/login` — returns JWT
* `POST /auth/signup/admin` — admin-only create admin/manager accounts

### 👥 Users

* `GET /users/me` — current user info
* `GET /users/` — list all users (Admin/Manager)
* `PATCH /users/{id}/role` — update role
* `PATCH /users/{id}/suspend` — suspend/reactivate account

### 🗂 Cases & Inspections

* `POST /cases/` — create case
* `GET /cases/` — list all cases
* `PATCH /cases/{id}/status` — update status
* `POST /inspections/{case_id}/report` — inspector submits report
* `POST /inspections/{case_id}/review` — manager reviews report

### 📊 Reports

* `GET /reports/kpi` — KPIs summary
* `GET /reports/analytics` — analytics for manager
* `GET /reports/export` — export reports

### 🤖 ML Scoring

* `POST /ml/v1/score` — score one building
* `POST /ml/v1/batch/score` — score multiple buildings

### 🧠 Training & Model Ops

* `POST /ops/train` — start training
* `GET /ops/train/model/current` — view active model
* `POST /ops/models/upload` — upload model artifact
* `POST /ops/model/activate` — activate model version

### 📡 Data Ops

* `POST /ops/upload_dataset` — upload CSV
* `POST /ops/drift_report` — detect dataset drift
* `GET  /ops/public/stats` — public statistics
* `POST /ops/infer-and-create-cases` — run ML + auto-generate cases
* `GET  /ops/report/pdf/{building_id}` — generate PDF report

### 🎫 Tickets (Citizen)

* `POST /tickets/` — submit ticket
* `GET /tickets/mine` — my tickets
* `POST /tickets/{ticket_id}/followup` — add follow-up

### 📅 Scheduling (Manager)

* list inspectors, workload, appointments
* reschedule / reassign visits
* auto-assign scheduling

---

## 🔄 Notes

* CORS allows `http://localhost:5173` for the local frontend.
* SQLite is used by default for development.
* For PostgreSQL:
  set `DB_URL=postgresql+psycopg2://user:pass@host/dbname`

---
