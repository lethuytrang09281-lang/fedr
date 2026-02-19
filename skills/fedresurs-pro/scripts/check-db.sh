#!/bin/bash
# Quick database health check

echo "📊 Database Status"
echo "===================="
echo ""

echo "Tables:"
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT 
  tablename,
  n_live_tup AS rows,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
"

echo ""
echo "Orchestrator State:"
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT task_key, last_processed_date 
FROM system_state 
WHERE task_key='trade_monitor';
"

echo ""
echo "Database Size:"
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT pg_size_pretty(pg_database_size('fedresurs_db')) AS db_size;
"
