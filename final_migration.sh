#!/bin/bash
set -e

echo "=== Final Migration Script for Fedresurs Radar ==="
echo

# Переходим в директорию проекта
cd /root/fedr

# 1. Проверка и запуск контейнеров
echo "1. Starting Docker containers..."
docker-compose down 2>/dev/null || true
docker-compose up -d

echo "Waiting for containers to start..."
sleep 5

# 2. Проверка статуса
echo -e "\n2. Container status:"
docker-compose ps

# 3. Проверка доступности PostgreSQL
echo -e "\n3. Testing PostgreSQL connection..."
if docker-compose exec -T db pg_isready -U postgres; then
    echo "PostgreSQL is ready"
else
    echo "Waiting for PostgreSQL..."
    sleep 10
    docker-compose exec -T db pg_isready -U postgres || echo "PostgreSQL may still be starting"
fi

# 4. Создание миграции
echo -e "\n4. Creating Alembic migration..."
docker-compose exec -T app alembic revision --autogenerate -m "Initial_migration_with_is_restricted" || {
    echo "Migration creation may have warnings, continuing..."
}

# 5. Применение миграции
echo -e "\n5. Applying Alembic migration..."
docker-compose exec -T app alembic upgrade head

# 6. Проверка таблиц
echo -e "\n6. Checking database tables..."
docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\dt'

# 7. Восстановление entrypoint.sh (включение автоматических миграций)
echo -e "\n7. Restoring automatic migrations in entrypoint.sh..."
sed -i 's/# alembic upgrade head/alembic upgrade head/' entrypoint.sh
echo "Entrypoint restored"

echo -e "\n=== Migration completed successfully ==="
echo "Containers are running with applied migrations"
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"