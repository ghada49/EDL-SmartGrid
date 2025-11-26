# ⚡ Electricity Anomaly Detection & Field Inspection Platform for EDL
 (EECE 490/690 – Fall 2025-2026)

## 📌 Overview
This project is an end-to-end AI platform that detects **unusual electricity consumption** in residential buildings and streamlines the **inspection workflow** between managers, inspectors, and citizens.

We combine:
- **Machine Learning models** (...)
- **FastAPI backend** with model inference, dataset uploads, PDF reporting
- **React frontend** for Manager, Inspector, and Citizen portals
- **Dockerized deployment** for reproducibility

The goal is to automatically flag anomalies, reduce inspection workload, and support data-driven decision-making.

Acknowledgment 👨‍🏫✨

This project received positive feedback from Dr. Riad Chedid, who described it as “a very good and well-structured solution” during the evaluation phase.

---

## 🚀 Features

### 🔍 Machine Learning
...

### 🛠 Backend (FastAPI)
🔐 Auth & Users
/auth/signup, /auth/login, /auth/signup/admin
/users/me, /users/, /users/{id}/role, /users/{id}/suspend

🗂 Cases
/cases/ (create, list)
/cases/{id} (details, status, assign, comments, attachments)
/cases/{id}/confirm, /cases/{id}/reject

🕵️ Inspections
/inspections/{case_id}/report
/inspections/{case_id}/review

📊 Reports & Analytics
/reports/kpi
/reports/analytics
/reports/export

🧠 ML & Training

/ops/train
/ops/train/model/current
/ops/models/upload
/ops/model/activate
/ops/drift_report
/ops/infer-and-create-cases

📅 Manager Scheduling
Inspectors list, workload, appointments, auto-assign

🎫 Tickets (Citizen)
/tickets/ (submit)
/tickets/mine
/tickets/{id} + follow-up

### 🌐 Frontend (React)
- **Manager dashboard**: overview, case management, ticket management, scheduling
- **Inspector console**: assigned cases, map  
- **Citizen portal**: ticket submission + tracking, awarness guidelines  


### 🐳 Docker
- `docker-compose.yml` for backend + frontend  
- Reproducible environment with pinned dependencies  
- `.env` templates for configuration


## 🧠 Machine Learning Models

We use a combination of baseline and improved models:

| Task | Baseline | Improved |
|------|----------|----------|
| Expected kWh | Huber Regressor | Random Forest |
| Anomalies | Isolation Forest | Autoencoder |
| Clustering | KMeans | HDBSCAN |

Artifacts include:  
- `feature_list.json`  
- `scaler.joblib`  
- `kwh_regressor.joblib`  
- `if_model.joblib`  
- `ae_model.h5`  
- `thresholds.json`  
- `model_card.json`

---

## 🏗 Running the Project (Docker)

### 1. Clone the repo
```bash
git clone <repo-url>
cd project
````

### 2. Create environment files

```
cp backend.env.example backend.env
```

### 3. Start containers

```bash
docker-compose up --build
```

### 4. Access the system

* Backend Docs → [http://localhost:8000/docs](http://localhost:8000/docs)
* Frontend → [http://localhost:5173](http://localhost:5173)

---

## 👥 User Roles

### 👤 Citizen

* Submit a ticket
* Track ticket
* Energy awarness

### 🕵️ Inspector

* Assigned cases dashboard
* Accept/reject visits
* Generate PDF report

### 👨‍💼 Manager

* View all anomalies
* Assign cases
* Review inspection results
* Label outcomes (Fraud / Non-Fraud / Uncertain)
* View analytics & KPIs

### 🔧 Admin

* Upload datasets
* Upload/activate ML models
* View drift reports
* Manage user roles

---

## 📊 Why Machine Learning?

Electricity consumption is multi-dimensional and depends on structure, location, and behavior.
Simple averages cannot capture these relationships.

ML learns:

* what is normal for each building
* which patterns are suspicious
* how consumption compares to similar buildings

This allows anomaly detection at **scale, accuracy, and objectivity**.

---


 
