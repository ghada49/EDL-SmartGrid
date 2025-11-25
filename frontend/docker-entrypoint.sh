#!/bin/sh
set -e

# Ensure we're in the frontend directory
cd /app/frontend || exit 1

echo "[FRONTEND] Installing dependencies (including dev dependencies)..."
# Ensure NODE_ENV is not production so devDependencies are installed
# npm install will update/install packages as needed (can't remove node_modules as it's a volume mount)
NODE_ENV=development npm install

echo "[FRONTEND] Verifying vite installation..."
if [ ! -f "node_modules/.bin/vite" ]; then
    echo "[FRONTEND] WARNING: vite binary not found, attempting to reinstall vite..."
    NODE_ENV=development npm install vite@^5.4.21 --save-dev
    if [ ! -f "node_modules/.bin/vite" ]; then
        echo "[FRONTEND] ERROR: vite binary still not found after reinstall"
        echo "[FRONTEND] Listing node_modules/.bin contents:"
        ls -la node_modules/.bin/ 2>&1 | head -20 || echo "node_modules/.bin does not exist"
        echo "[FRONTEND] Checking if vite package is installed:"
        ls -la node_modules/vite/ 2>&1 | head -10 || echo "vite package not found"
        echo "[FRONTEND] Try removing the volume manually: docker volume rm eece-490-project-3_frontend_node_modules"
        exit 1
    fi
fi

echo "[FRONTEND] Starting Vite dev server..."
# Use the direct path to vite binary to avoid PATH issues
exec ./node_modules/.bin/vite --host 0.0.0.0 --port 5173

