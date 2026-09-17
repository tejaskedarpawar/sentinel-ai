#!/usr/bin/env bash
# Sentinel AI — one-time local environment setup.
# Installs & starts Postgres + Redis, creates the sentinel DB/user.
# Run once (or whenever Postgres/Redis aren't already running).
set -e

if ! command -v psql >/dev/null; then
  echo "Installing PostgreSQL and Redis..."
  sudo apt-get update -qq
  sudo apt-get install -y postgresql redis-server
fi

echo "Starting PostgreSQL..."
sudo service postgresql start

echo "Starting Redis..."
redis-server --daemonize yes

sleep 2

echo "Creating sentinel database/user (safe to re-run)..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='sentinel'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER sentinel WITH PASSWORD 'sentinel_dev_password';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='sentinel'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE sentinel OWNER sentinel;"

echo "Done. Postgres + Redis are running and the sentinel DB is ready."
echo "Next: ./run_backend.sh   (in one terminal)"
echo "      ./run_frontend.sh  (in another terminal)"
