#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_WORKERS:-4}" \
    --no-access-log
