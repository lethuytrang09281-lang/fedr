#!/bin/bash
set -e

echo "=== Запуск миграций Alembic для Fedresurs Radar ==="
echo

# 1. Проверка контейнеров
echo "1. Проверка статуса контейнеров..."
docker-compose ps

echo
echo "2. Создание миграции..."
docker-compose exec -T app alembic revision --autogenerate -m "Initial_migration_with_is_restricted"

echo
echo "3. Применение миграции..."
docker-compose exec -T app alembic upgrade head

echo
echo "4. Проверка созданных миграций..."
find alembic/versions -name "*.py" -type f | head -5

echo
echo "=== Миграции выполнены ==="