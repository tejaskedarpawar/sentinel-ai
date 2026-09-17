#!/usr/bin/env bash
# Sentinel AI — backend setup + run.
# Assumes Postgres + Redis are running (see setup_env.sh).
set -e
cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

echo "Installing dependencies (first run only — torch is a large download)..."
pip install -q -r requirements.txt

echo ""
echo "Seeding the database with the simulated 20-employee / 30-day dataset"
echo "and running the full detection pipeline (Isolation Forest + Autoencoder"
echo "+ LSTM + XGBoost -> risk scoring -> AI investigation agent)..."
python -m app.pipeline

echo ""
echo "Starting the API at http://localhost:8000  (docs at /docs)"
echo "(Ctrl+C to stop)"
uvicorn app.main:app --host 0.0.0.0 --port 8000
