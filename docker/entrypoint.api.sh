#!/bin/sh
set -eu

echo "Applying database migrations..."
alembic upgrade head

if [ "${PRISM_SEED_DEMO:-false}" = "true" ]; then
  echo "Seeding the explicitly requested synthetic demonstration world..."
  python -c "from app.seed.seed_service import seed_demo_database; seed_demo_database()"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
