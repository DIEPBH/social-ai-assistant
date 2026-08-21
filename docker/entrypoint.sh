#!/bin/sh
set -e

echo "=================================================="
echo " Starting Social AI Assistant Container Entrypoint"
echo "=================================================="

# Wait for PostgreSQL
echo "==> Waiting for PostgreSQL (${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432})..."
while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  sleep 1
done
echo "==> PostgreSQL database is ready!"

# Run migrations
echo "==> Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting service process: $@"
exec "$@"
