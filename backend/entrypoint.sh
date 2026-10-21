#!/bin/sh
set -e
# Only the API process runs migrations (worker shares the same image).
case "$1" in
  uvicorn)
    echo "Running alembic upgrade head..."
    alembic upgrade head
    ;;
esac
exec "$@"
