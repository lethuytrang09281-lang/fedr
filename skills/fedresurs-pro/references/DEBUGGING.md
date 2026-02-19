# Debugging Guide

## Quick Diagnostics

### System Health Check
```bash
# All containers running?
docker ps

# Orchestrator logs (last 50 lines)
docker logs fedr-app-1 2>&1 | tail -50

# Database accessible?
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "SELECT 1;"

# API limits
curl -s "https://parser-api.com/stat/?key=ede50185e3ccc8589a5c6c6efebc14cc"
```

---

## Common Issues

### 1. Orchestrator Not Finding Lots

**Symptoms:**
- Logs show "Найдено лотов: 0"
- `lots` table empty after search

**Diagnosis:**
```bash
# Check if search ran
docker logs fedr-app-1 | grep "Запуск поиска лотов"

# Check for errors
docker logs fedr-app-1 | grep ERROR

# Check filter settings
docker exec fedr-app-1 cat /app/src/services/fedresurs_search.py | grep -A 10 "BUILDING_KEYWORDS"
```

**Possible Causes:**

#### A) API Limit Exhausted
```bash
curl -s "https://parser-api.com/stat/?key=..." | grep fedresurs
# If day_request_count == day_limit → wait until midnight
```

**Fix**: Wait until 00:00 UTC (03:00 MSK)

#### B) No Matching Organizations
```bash
# Check if orgs found
docker logs fedr-app-1 | grep "ШАГ 1: Поиск организаций"
docker logs fedr-app-1 | grep "Найдено организаций"
```

**Fix**: API may be down or returning no results. Try manual query:
```bash
curl "https://parser-api.com/api/fedresurs/search_ur?key=...&orgRegionID=77&page=1"
```

#### C) Filter Too Strict
```bash
# Check filter logs
docker logs fedr-app-1 | grep "фильтр"
```

**Fix**: Temporarily disable filter to see if lots exist:
```python
# In fedresurs_search.py, comment out filter
# if self._matches_filter(lot):
#     filtered_lots.append(lot)
filtered_lots.append(lot)  # Add all lots
```

**Rebuild and test**:
```bash
docker-compose build app && docker-compose up -d app
```

#### D) Parsing Error
```bash
# Check for KeyError, AttributeError
docker logs fedr-app-1 | grep -i "error\|exception"
```

**Fix**: API response format may have changed. Check `_extract_lots_from_message()` logic.

---

### 2. Infinite Loop (Orchestrator Runs Every 10 Seconds)

**Symptoms:**
- Logs show "Первый запуск" repeatedly
- `system_state` updates every 10 seconds

**Diagnosis:**
```bash
# Check state updates
docker logs fedr-app-1 | grep "State updated"

# Check state in DB
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT * FROM system_state WHERE task_key='trade_monitor';"
```

**Possible Causes:**

#### A) `get_last_processed_date()` Returns None
```bash
# Add debug logging
docker exec fedr-app-1 python -c "
import asyncio
from src.orchestrator import Orchestrator
async def test():
    orch = Orchestrator()
    date = await orch.get_last_processed_date()
    print(f'Type: {type(date)}, Value: {date}')
asyncio.run(test())
"
```

**Fix**: Ensure function always returns `datetime`, not `None`. See `ORCHESTRATOR.md` for correct implementation.

#### B) `update_state()` Not Called
```bash
# Check if state is updating
docker logs fedr-app-1 | grep "State updated"
```

**Fix**: Ensure `update_state()` is in `finally` block:
```python
try:
    lots = await self.search()
except Exception as e:
    logger.error(f"Error: {e}")
finally:
    await self.update_state('trade_monitor', datetime.now())
```

---

### 3. API Limit Burned in Minutes

**Symptoms:**
- `curl .../stat/` shows 240+/250 used
- Orchestrator ran once, burned all requests

**Diagnosis:**
```bash
# Check limit protection threshold
docker logs fedr-app-1 | grep "Лимит почти исчерпан"
```

**Cause**: Threshold too high (e.g., 240 instead of 50)

**Fix**:
```python
# In orchestrator.py
if day_left < 50:  # Not 240!
    await asyncio.sleep(self._seconds_until_midnight())
```

**Immediate action**:
```bash
# Stop orchestrator
docker-compose down

# Wait for limit reset (00:00 UTC = 03:00 MSK)
```

---

### 4. Database Connection Errors

**Symptoms:**
- "Cannot connect to database"
- "FATAL: password authentication failed"

**Diagnosis:**
```bash
# Check DB container
docker ps | grep fedr-db-1

# Check DB logs
docker logs fedr-db-1

# Test connection
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "SELECT 1;"
```

**Possible Causes:**

#### A) Container Not Running
```bash
docker ps -a | grep fedr-db-1
# If STATUS is "Exited" → restart
docker-compose up -d db
```

#### B) Wrong DATABASE_URL
```bash
# Check .env
cat /root/fedr/.env | grep DATABASE_URL
# Should be: postgresql://postgres@fedr-db-1/fedresurs_db
```

#### C) Network Issue
```bash
# Check Docker network
docker network ls
docker network inspect fedr_default
```

**Fix**: Recreate network:
```bash
docker-compose down
docker network prune
docker-compose up -d
```

---

### 5. Frontend Shows Old Version

**Symptoms:**
- Updated Vue app, but browser shows old version
- Ctrl+F5 doesn't help

**Diagnosis:**
```bash
# Check nginx cache headers
curl -I http://157.22.231.149 | grep -i cache
```

**Fix**: Clear nginx cache:
```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/fedresurs-pro

# Add to location / block:
add_header Cache-Control "no-cache, no-store, must-revalidate";
add_header Pragma "no-cache";
add_header Expires "0";

# Reload nginx
sudo nginx -t && sudo nginx -s reload

# Rebuild frontend
cd /root/fedr/frontend
npm run build
```

---

### 6. FedresursSearch Returns Error 40304

**Symptoms:**
- Logs show "❌ Дневной лимит исчерпан! 240/250"
- Search doesn't run

**Cause**: API limit exhausted (expected behavior)

**Fix**: Wait until 00:00 UTC (03:00 MSK) when limits reset.

**Check reset time**:
```bash
date -u  # Current UTC time
# Limits reset at 00:00 UTC
```

---

## Manual Testing

### Test Search Without Burning Limits

**Method 1**: Mock API responses
```python
# In fedresurs_search.py, temporarily replace API calls with mock data
async def _fetch_organizations(self):
    return [{"id": "test-org", "inn": "7701234567"}]
```

**Method 2**: Use saved responses
```bash
# Save API response
curl "https://parser-api.com/api/fedresurs/search_ur?..." > /tmp/orgs.json

# Load from file in code
with open('/tmp/orgs.json') as f:
    return json.load(f)
```

### Test Database Queries

```bash
# Connect to DB
docker exec -it fedr-db-1 psql -U postgres -d fedresurs_db

# Test queries
fedresurs_db=# SELECT COUNT(*) FROM lots;
fedresurs_db=# SELECT * FROM system_state;
fedresurs_db=# \dt  -- List tables
fedresurs_db=# \d lots  -- Describe table
```

### Test Orchestrator Manually

```bash
# Stop scheduled orchestrator
docker-compose down

# Run once manually
docker-compose run --rm app python -c "
import asyncio
from src.orchestrator import Orchestrator

async def main():
    orch = Orchestrator()
    await orch.run_once()  # Run single cycle

asyncio.run(main())
"
```

---

## Recovery Procedures

### Reset Orchestrator State

**Force immediate search** (ignores 6-hour wait):
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "UPDATE system_state 
      SET last_processed_date = NOW() - INTERVAL '7 hours' 
      WHERE task_key='trade_monitor';"
```

### Clear All Lots

**WARNING**: Deletes all data!
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "TRUNCATE lots, auctions RESTART IDENTITY CASCADE;"
```

### Restore from Backup

```bash
# List backups
ls /root/fedr/backups/

# Restore
cat /root/fedr/backups/backup_20260218.sql | \
  docker exec -i fedr-db-1 psql -U postgres -d fedresurs_db
```

### Full System Reset

**Nuclear option** (stops all containers, clears data):
```bash
cd /root/fedr
docker-compose down -v  # -v removes volumes
docker system prune -a  # Clean Docker cache
docker-compose up -d
```

---

## Monitoring Commands

```bash
# Live logs
docker logs -f fedr-app-1

# Search-related logs
docker logs fedr-app-1 | grep -E "Запуск поиска|Найдено|Сохранено"

# Error logs
docker logs fedr-app-1 | grep -i error

# Resource usage
docker stats fedr-app-1 fedr-db-1

# API limits (live)
watch -n 60 'curl -s "https://parser-api.com/stat/?key=..." | jq'
```

---

## Performance Troubleshooting

### Slow Database Queries

```sql
-- Enable query logging
ALTER DATABASE fedresurs_db SET log_min_duration_statement = 1000;

-- Find slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

### High Memory Usage

```bash
# Check container stats
docker stats

# If memory > 80%, restart
docker-compose restart app
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Clean Docker
docker system prune -a --volumes

# Clean logs
docker logs fedr-app-1 > /dev/null
```

---

## Emergency Contacts

**VPS Access**: root@157.22.231.149 (SSH key only)
**Database**: fedr-db-1 container, port 5432
**Frontend**: http://157.22.231.149
**API**: http://157.22.231.149:8000
