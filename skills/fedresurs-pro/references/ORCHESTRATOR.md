# Orchestrator — Search Cycle & Limit Protection

## Overview

The orchestrator (`src/orchestrator.py`) runs a continuous 6-hour search cycle, fetching bankruptcy lots from fedresurs API while respecting daily rate limits (250 requests/day).

## Main Loop

```python
async def run(self):
    while True:
        # 1. Check API limits
        stats = await self._check_api_limits()
        fedresurs = stats.get('fedresurs', {})
        day_left = fedresurs.get('day_limit', 250) - fedresurs.get('day_request_count', 0)
        
        # 2. Sleep if limit low
        if day_left < 10:
            wait = self._seconds_until_midnight()
            logger.warning(f"⚠️ Лимит почти исчерпан ({day_left} запросов). Пауза {wait//3600}ч.")
            await asyncio.sleep(wait)
            continue
        
        # 3. Check if search needed
        last_processed = await self.get_last_processed_date()
        now = datetime.now(timezone.utc)
        
        if last_processed and (now - last_processed).total_seconds() < self.scan_interval:
            sleep_seconds = self.scan_interval - (now - last_processed).total_seconds()
            logger.info(f"💤 Следующий поиск через {sleep_seconds//60} минут...")
            await asyncio.sleep(sleep_seconds)
            continue
        
        # 4. Run search
        try:
            lots = await self.fedresurs_search.search_lots()
            if lots:
                for lot_data in lots:
                    await self._save_lot_to_db(lot_data)
        except Exception as e:
            logger.error(f"Search failed: {e}")
        finally:
            # ALWAYS update state (even on error)
            await self.update_state('trade_monitor', now)
```

## API Limit Protection

### Check Limits (`_check_api_limits`)

Queries parser-api.com/stat/ endpoint:

```python
async def _check_api_limits(self) -> dict:
    url = f"https://parser-api.com/stat/?key={self.settings.PARSER_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            # API returns array: [{"service":"fedresurs", "day_request_count":240, ...}]
            return {item['service']: item for item in data}
```

**Response format:**
```json
[
  {
    "service": "fedresurs",
    "day_request_count": 240,
    "day_limit": 250,
    "month_request_count": 240,
    "month_limit": 7500
  }
]
```

### Sleep Until Midnight (`_seconds_until_midnight`)

Calculates seconds until 00:00 UTC (when limits reset):

```python
def _seconds_until_midnight(self) -> int:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return int((tomorrow - now).total_seconds())
```

**Critical**: Uses UTC, not local time. Fedresurs limits reset at 00:00 UTC = 03:00 MSK.

## State Management

### Get Last Processed Date

```python
async def get_last_processed_date(self, task_key: str = "trade_monitor") -> datetime:
    result_date = None
    default_date = datetime.now(timezone.utc) - timedelta(hours=6)
    
    try:
        async for session in get_db_session():
            try:
                result = await session.execute(
                    select(SystemState).where(SystemState.task_key == task_key)
                )
                state = result.scalar_one_or_none()
                if state and state.last_processed_date:
                    result_date = state.last_processed_date
            finally:
                await session.close()
                break
    except Exception as e:
        logger.error(f"Failed to get state: {e}")
    
    # Return result AFTER finally block (avoid Python quirk with return/finally/break)
    return result_date if result_date is not None else default_date
```

**Critical bug fixed (2026-02-18):**
- OLD: `return` inside `try`, `break` in `finally` → `break` overwrote `return`
- NEW: Save to variable, return AFTER `finally` block

### Update State

```python
async def update_state(self, task_key: str, processed_date: datetime):
    try:
        async for session in get_db_session():
            try:
                result = await session.execute(
                    select(SystemState).where(SystemState.task_key == task_key)
                )
                state = result.scalar_one_or_none()
                
                if state:
                    state.last_processed_date = processed_date
                else:
                    state = SystemState(task_key=task_key, last_processed_date=processed_date)
                    session.add(state)
                
                await session.commit()
                logger.info(f"State updated: {task_key} -> {processed_date}")
            finally:
                await session.close()
                break
    except Exception as e:
        logger.error(f"Failed to update state: {e}")
```

**MUST be called in `finally` block** to prevent infinite loops on errors.

## FedresursSearch Integration

```python
from src.services.fedresurs_search import FedresursSearch

self.fedresurs_search = FedresursSearch(api_key=settings.PARSER_API_KEY)
lots = await self.fedresurs_search.search_lots()
```

Returns list of dicts:
```python
[
    {
        "lot_number": "LOT-00001",
        "description": "Офисное здание...",
        "start_price": 50000000,
        "debtor_inn": "7701234567",
        "message_id": "msg-123",
        "auction_id": "auction-456"
    }
]
```

## Configuration

```python
# .env
SCAN_INTERVAL_MINUTES=360  # 6 hours
PARSER_API_KEY=ede50185e3ccc8589a5c6c6efebc14cc
DATABASE_URL=postgresql://postgres@fedr-db-1/fedresurs_db
```

## Common Issues

### Issue: Infinite loop ("Первый запуск" every 10 seconds)

**Cause**: `get_last_processed_date()` returned `None`

**Fix**: Ensure function returns `datetime`, not `None`. Check:
1. `get_db_session()` yields session
2. No `return` inside `try/finally` with `break`
3. Always return `default_date` as fallback

### Issue: State not updating after errors

**Cause**: `update_state()` only called on success, not in `finally` block

**Fix**: 
```python
try:
    lots = await self.fedresurs_search.search_lots()
except Exception as e:
    logger.error(f"Error: {e}")
finally:
    await self.update_state('trade_monitor', now)  # ALWAYS update
```

### Issue: Orchestrator burns all 250 requests in minutes

**Cause**: 
1. No limit check before search
2. Threshold too high (240/250 leaves only 10 for debugging)

**Fix**:
```python
# Check BEFORE search
if day_left < 10:  # Not 240!
    await asyncio.sleep(self._seconds_until_midnight())
```

**Recommended threshold**: 50 requests (leaves 200 for real search, 50 for debugging)

## Monitoring Commands

```bash
# Check orchestrator logs
docker logs fedr-app-1 2>&1 | grep -E "лимит|Найдено|Сохранено|ERROR"

# Check when next search
docker logs fedr-app-1 2>&1 | grep "Следующий поиск через"

# Check state in DB
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT * FROM system_state WHERE task_key='trade_monitor';"

# Check API limits
curl -s "https://parser-api.com/stat/?key=ede50185e3ccc8589a5c6c6efebc14cc"
```

## Manual Control

```bash
# Stop orchestrator
docker-compose down

# Start orchestrator
docker-compose up -d

# Restart orchestrator
docker-compose restart app

# Reset state (force immediate search)
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "UPDATE system_state SET last_processed_date = NOW() - INTERVAL '7 hours' WHERE task_key='trade_monitor';"
```
