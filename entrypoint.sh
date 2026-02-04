#!/bin/bash
set -e

echo "DEBUG: Checking environment variables"
echo "DB_HOST=$DB_HOST"
echo "DB_PORT=$DB_PORT"
echo "DB_USER=$DB_USER"
echo "DB_PASSWORD=$DB_PASSWORD"
echo "DB_NAME=$DB_NAME"
echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"
echo "TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID"
echo "Waiting for PostgreSQL to be ready..."

# Ждем пока PostgreSQL станет доступен
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "PostgreSQL is ready!"

# Временное отключение миграций для отладки
echo "Skipping migrations for now..."
# alembic upgrade head

echo "Starting application..."
exec python -m src.main
