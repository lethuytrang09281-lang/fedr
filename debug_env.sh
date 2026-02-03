#!/bin/bash
set -e

echo "=== Debug Environment Script ==="
echo

cd /root/fedr

# Создаем файл для проверки переменных окружения в контейнере
cat > /tmp/debug_env.py << 'EOF'
import os
import sys

print("Environment variables in container:")
print("=" * 60)
for key in sorted(os.environ.keys()):
    if 'DB' in key or 'POSTGRES' in key or 'PASSWORD' in key:
        value = os.environ[key]
        masked = value[:3] + '***' if value and len(value) > 3 else '***'
        print(f"{key}={masked}")
print("=" * 60)

# Проверяем настройки из config.py
try:
    sys.path.append('/app')
    from src.config import settings
    print(f"\nSettings from config.py:")
    print(f"DB_HOST: {settings.DB_HOST}")
    print(f"DB_USER: {settings.DB_USER}")
    print(f"DB_PASSWORD: {settings.DB_PASSWORD[:3] if settings.DB_PASSWORD else 'None'}***")
    print(f"database_url: {settings.database_url}")
except Exception as e:
    print(f"Error loading settings: {e}")
EOF

echo "1. Running debug script in app container..."
docker-compose run --rm app python /tmp/debug_env.py

echo -e "\n2. Testing direct connection from app container..."
docker-compose run --rm app /bin/bash -c "
echo 'Testing connection with PGPASSWORD...'
export PGPASSWORD=password
psql -h db -U postgres -d fedresurs_db -c 'SELECT 1 as test;'
echo 'Exit code: $?'
"

echo -e "\n3. Checking docker-compose environment variables..."
grep -A5 -B5 "environment:" docker-compose.yml

echo -e "\n4. Checking .env file..."
cat .env | grep -v "^#" | grep -E "DB|POSTGRES|PASSWORD"

echo -e "\n=== Debug complete ==="