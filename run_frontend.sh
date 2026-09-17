#!/usr/bin/env bash
# Sentinel AI — SOC dashboard (Vite + React) setup + run.
set -e
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies (first run only)..."
  npm install
fi

echo "Starting the dashboard at http://localhost:5173"
echo "(Ctrl+C to stop — make sure run_backend.sh is running in another terminal)"
npm run dev
