#!/usr/bin/env bash
set -e

echo "[ENTRYPOINT] Creating required data directories..."
# Create all required data directories if they don't exist
mkdir -p /app/data/plots
mkdir -p /app/data/uploads
mkdir -p /app/data/datasets
mkdir -p /app/data/tmp
mkdir -p /app/data/case_attachments
mkdir -p /app/data/model_registry
mkdir -p /app/data/processed
mkdir -p /app/data/raw

echo "[ENTRYPOINT] Seeding admin user..."
python -m backend.seed_admin || true

echo "[ENTRYPOINT] Starting uvicorn..."
exec python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
