#!/bin/sh
set -e

cd /app/frontend || exit 1

echo "[FRONTEND] Installing dependencies..."
unset NODE_ENV
npm install --include=dev

echo "[FRONTEND] Verifying vite installation..."
# Check if vite package exists
if [ ! -d "node_modules/vite" ]; then
    echo "[FRONTEND] ERROR: Vite package not found. Reinstalling..."
    rm -rf node_modules package-lock.json
    npm install --include=dev
fi

# Check if vite binary exists
if [ ! -f "node_modules/vite/bin/vite.js" ]; then
    echo "[FRONTEND] ERROR: Vite binary not found!"
    exit 1
fi

echo "[FRONTEND] Starting Vite dev server..."
# Use node to run vite directly, bypassing npm's PATH resolution
exec node node_modules/vite/bin/vite.js --host 0.0.0.0 --port 5173