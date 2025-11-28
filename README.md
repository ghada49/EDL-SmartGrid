
# ⚡EDL SmartGrid
## AI-Driven Electricity Anomaly Detection & Inspection Management Platform

EDL SmartGrid is an end-to-end AI platform for detecting unusual electricity consumption in buildings and managing the full inspection lifecycle.




## 📌 Overview
EDL SmartGrid is a complete AI platform that detects unusual electricity consumption in residential buildings and streamlines the workflow between citizens, inspectors, managers, and admin/data-ops teams.

It provides:
- A robust ML pipeline for anomaly detection
- A FastAPI backend for training, inference, model activation, drift reports
- A React frontend with role-based dashboards
- A Dockerized, reproducible deployment with backend + worker + Redis + frontend
- A full inspection workflow connecting anomalies → cases → visits → reports

### 🎯 Goal
To automatically flag abnormal consumption, reduce manual inspection workload, and support transparent, data-driven electricity management in Lebanon.



## 📂 Dataset Location
The dataset used for training and evaluation lives in:

``
/Dataset/data.xlsx
``

This is the file that the Admin/Data-Ops user uploads from the portal.
## 👨‍🏫 Acknowledgment
This project received excellent feedback from Dr. Riad Chedid, who described it as:
>"A very good and well-structured solution."


## 🚀 Features

### 🔍 Machine Learning
- Advanced preprocessing (schema fixing, imputation, Winsorization, skew correction)  
- Residual modeling (expected vs actual kWh)  
- Domain ratios: kWh/m², kWh/apartment, apartments/floor, residual intensity  
- PCA-based latent space  
- Ensemble anomaly critics:
**IF, LOF, OCSVM, AE, Copula, PPCA-MAH, HDBSCAN, GMM, VAE**
- Rank-fusion anomaly scoring  
- Full stability auditing (Spearman ρ, ARI, Jaccard@K)
- Baseline Model: One-Class SVM (OCSVM) implemented, tested, tunable, and available in the training pipeline. 

*(not connected to UI but present and used in full tuning pipeline)*
---

## 🛠 Backend (FastAPI)

### 🔐 Authentication
- `/auth/signup`  
- `/auth/login`  
- `/auth/signup/admin`  
- `/users/me`  
- `/users/{id}/role`  
- `/users/{id}/suspend`  

### 🗂 Cases
- Create, update, assign, confirm, reject  
- Attachments, comments, status tracking  

### 🕵️ Inspections
- Submit inspection reports  
- Review and classify outcomes 
- Geo-based routing with home-base location 

### 📊 Analytics & ML Ops
- `/ops/train` (full training pipeline)  
- `/ops/model/current`  
- `/ops/model/activate`  
- `/ops/drift_report`  
- `/ops/infer-and-create-cases`  

---

## 🌐 Frontend (React)
- **Citizen Portal:** submit/track tickets, awareness guidelines  
- **Inspector Console:** assigned visits, map-based navigation, PDF upload
- **Manager Dashboard:** anomalies, scheduling, KPIs, workload  
- **Admin interface:** dataset upload, drift score, model training, model registry, user roles management

---

## 🐳 Dockerized Architecture
The system runs using four containers:

| Container | Purpose |
|----------|----------|
| **backend** | FastAPI API (API, ML inference, model registry, training endpoints) |
| **worker** | Background ML training, tuning, drift checks |
| **redis** | Message broker + job queue |
| **frontend** | React user interface |

---
## 🔧 Running the Project (Docker)

## 1️⃣ Clone the Repository
```bash
git clone https://github.com/ghada49/EDL-SmartGrid.git
cd EDL-SmartGrid
```

## 2️⃣ Create Environment File
Copy example file:
```bash
cp backend.example.env backend.env

```
The backend will auto-create an admin:
```
ADMIN_EMAIL=admin@edl.gov.lb
ADMIN_PASSWORD=Admin123!
```
## 3️⃣ Start the System
```bash
docker compose up --build

```
## 4️⃣ Access the Interfaces
- Frontend: http://localhost:5173
- Backend Docs: http://localhost:8000/docs
## 🧭 How to Use the System

#### 1. Create a Citizen Account
Sign up normally (default role: citizen).

Citizen can:
- Submit tickets (complaints)
- Track ticket status
- Access awareness guidelines

#### 2. Log in as Admin
Use auto-created admin:
```
admin@edl.gov.lb
Admin123!
```
#### 3. Promote Users
Admin → User Management → You can change Role
Promote your citizen account to:
- Inspector
- Manager
#### 4. Train a Model
Admin → Data & Models

Upload:
```
/Dataset/data.xlsx
```
Then choose a training mode:
- Fast
- Moderate (ASHA)
- Slow
- Very Slow (Full Grid Search)

Click Start Training.

The backend:
- sends the job to Redis
- and the worker performs training asynchronously

You can see:
- training logs
- metrics
- stability audit
- fused scores
- saved model card

#### 5. Run Inference
Log in as Manager (or promote your account).

Manager → Inference

Steps:

- Upload a new dataset
- Select Top X% anomalies (based on number of inspectors available)
- Run the inference

The system:

- applies preprocessing exactly as training
- extracts features
- loads saved artifacts
- computes Mahalanobis + Copula
- produces fused anomaly ranking
- returns x% of buildings with highest scores

This automatically creates a case for each building flagged as anomalous one.

#### 6. Inspector Workflow
Log in as Inspector (a citizen account must be promoted from admin account)
Steps:
- Enter your Home Base (e.g., latitude 33.8, longitude 35.5)
- View assigned cases
- Accept or reject visits
- After inspection:
    - Upload PDF report
    - Add comments
    - Update case status

#### 7. Manager Review & Case Closure
- Manager views:
    - inspection results
    - uploaded PDFs
    - inspector notes
    - building details
    - anomaly score
- Manager labels each case as:
    - Fraud
    - Non-Fraud
    - Uncertain