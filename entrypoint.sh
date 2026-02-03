#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."

# Ждем пока PostgreSQL станет доступен
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "PostgreSQL is ready!"

# Временное отключение миграций (применяются вручную)
echo "Skipping automatic migrations (applying manually)..."
alembic upgrade head

echo "Starting application..."
exec python -m src.main
