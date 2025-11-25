#!/usr/bin/env bash
set -e

echo "[ENTRYPOINT] Seeding admin user..."
python -m backend.seed_admin || true

echo "[ENTRYPOINT] Starting uvicorn..."
exec python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
