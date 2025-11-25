#!/usr/bin/env bash
set -e

echo "[WORKER] Waiting for Redis..."

until python - << 'EOF'
import sys, os, traceback
import redis

# Hard-code the docker-compose redis service address
url = "redis://redis:6379/0"
print("[WORKER] Trying Redis URL:", url, flush=True)

try:
    r = redis.from_url(url)
    r.ping()
    print("[WORKER] Redis ping OK", flush=True)
    sys.exit(0)
except Exception as e:
    print("[WORKER] Redis ping FAILED:", repr(e), flush=True)
    traceback.print_exc()
    sys.exit(1)
EOF
do
  echo "[WORKER] Redis not ready yet, retrying..."
  sleep 2
done

echo "[WORKER] Starting RQ worker..."
exec python -m backend.workers.train_worker
