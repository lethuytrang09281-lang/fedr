#!/bin/bash
set -e

echo "=== Debug Environment Variables ==="
echo

cd /root/fedr

# Останавливаем все контейнеры
docker-compose down 2>/dev/null || true

# Запускаем только БД
docker-compose up -d db
sleep 3

echo "1. Checking environment variables in app container..."
docker-compose run --rm --entrypoint /bin/bash app -c "
echo '=== Environment variables in container ==='
env | grep -E 'DB|POSTGRES|PASSWORD' | sort
echo
echo '=== Checking /app/.env ==='
ls -la /app/.env 2>/dev/null || echo 'No .env file in container'
echo
echo '=== Testing connection with different methods ==='
echo 'Method 1: Using psql command'
PGPASSWORD=\$DB_PASSWORD psql -h \$DB_HOST -U \$DB_USER -d \$DB_NAME -c 'SELECT 1 as test_psql;' 2>&1
echo 'Exit code: \$?'
echo
echo 'Method 2: Using asyncpg via Python'
python3 << 'PYEOF'
import asyncio
import asyncpg
import os

async def test():
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DB_HOST', 'db'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password'),
            database=os.getenv('DB_NAME', 'fedresurs_db')
        )
        print('AsyncPG connection successful')
        await conn.close()
        return True
    except Exception as e:
        print(f'AsyncPG error: {e}')
        return False

asyncio.run(test())
PYEOF
"

echo -e "\n2. Checking docker-compose environment setup..."
echo "Environment variables from docker-compose.yml:"
grep -A20 "environment:" docker-compose.yml | grep -E "^\s+-" | head -10

echo -e "\n3. Checking .env file on host:"
cat .env | grep -v "^#" | grep -E "DB|POSTGRES|PASSWORD"

echo -e "\n=== Debug complete ==="