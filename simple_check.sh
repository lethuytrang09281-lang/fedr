#!/bin/bash
set -e

echo "=== Simple Docker Check ==="
echo "Current directory: $(pwd)"
echo

echo "1. Docker version:"
docker --version
echo

echo "2. docker-compose version:"
docker-compose --version
echo

echo "3. All containers:"
docker ps -a
echo

echo "4. Fedr containers:"
cd /root/fedr && docker-compose ps
echo

echo "5. Try to run a test command in app container:"
cd /root/fedr && docker-compose exec -T app echo "Test from app" || echo "Failed to run command in app"
echo

echo "6. Check if entrypoint.sh was modified:"
cd /root/fedr && grep -n "alembic\|Skipping" entrypoint.sh
echo

echo "=== Check Complete ==="