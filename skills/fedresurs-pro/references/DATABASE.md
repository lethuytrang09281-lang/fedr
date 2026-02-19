# Database Schema & Datasets

## Connection

```bash
Host: fedr-db-1 (Docker container)
Database: fedresurs_db
User: postgres
Port: 5432 (internal Docker network)
```

```python
# .env
DATABASE_URL=postgresql://postgres@fedr-db-1/fedresurs_db
```

## Tables

### lots
Bankruptcy auction lots (commercial real estate).

```sql
CREATE TABLE lots (
    id SERIAL PRIMARY KEY,
    lot_number VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    start_price DECIMAL(15, 2),
    debtor_inn VARCHAR(12),
    message_id VARCHAR(255),
    auction_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Current state**: 0 records (waiting for orchestrator search)

### auctions
Auction metadata.

```sql
CREATE TABLE auctions (
    id SERIAL PRIMARY KEY,
    auction_id VARCHAR(255) UNIQUE NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Current state**: 0 records

### cadastral_index
Moscow cadastral records (584,354 properties).

```sql
CREATE TABLE cadastral_index (
    id SERIAL PRIMARY KEY,
    cadastral_number VARCHAR(50) UNIQUE NOT NULL,
    address TEXT,
    area DECIMAL(10, 2),           -- м²
    cadastral_value DECIMAL(15, 2), -- ₽
    permitted_use TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    district VARCHAR(100)
);
```

**Source**: HuggingFace dataset `danilsergeev/moscow_parcel_geo_meta`
**Loaded**: 2026-02-18 via `/app/data/cadastral/loader.py`
**Size**: 584,354 records

**Sample query:**
```sql
SELECT * FROM cadastral_index 
WHERE district = 'Таганский' 
  AND area > 100 
LIMIT 10;
```

### market_benchmarks
District-level real estate price benchmarks (60 districts).

```sql
CREATE TABLE market_benchmarks (
    id SERIAL PRIMARY KEY,
    district VARCHAR(100) NOT NULL,
    avg_price_sqm DECIMAL(10, 2),  -- ₽/м²
    median_price_sqm DECIMAL(10, 2),
    property_type VARCHAR(50),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Source**: Sberbank real estate data (processed)
**Loaded**: 2026-02-18 via `/app/data/sberbank/loader.py`
**Size**: 60 records

**Sample query:**
```sql
SELECT district, avg_price_sqm, median_price_sqm
FROM market_benchmarks
WHERE property_type = 'commercial'
ORDER BY avg_price_sqm DESC
LIMIT 10;
```

### system_state
Orchestrator state tracking.

```sql
CREATE TABLE system_state (
    id SERIAL PRIMARY KEY,
    task_key VARCHAR(50) UNIQUE NOT NULL,
    last_processed_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Current state**:
```
task_key: trade_monitor
last_processed_date: 2026-02-18 08:12:00+00
```

## Datasets on VPS

### Location
```
/root/fedr/data/
├── cadastral/
│   ├── moscow_parcel_geo_meta.parquet  (113 MB)
│   └── loader.py
└── sberbank/
    ├── train.csv
    ├── market_benchmarks.csv
    └── loader.py
```

### Cadastral Data

**Format**: Parquet (columnar, compressed)
**Fields**:
- `cadastral_number`: Кадастровый номер (77:01:0001001:123)
- `address`: Полный адрес
- `area`: Площадь участка/здания (м²)
- `cadastral_value`: Кадастровая стоимость (₽)
- `permitted_use`: Разрешенное использование
- `latitude`, `longitude`: Координаты
- `district`: Район Москвы

**Load script**:
```python
# /app/data/cadastral/loader.py
import pandas as pd
from sqlalchemy import create_engine

df = pd.read_parquet('/app/data/cadastral/moscow_parcel_geo_meta.parquet')
engine = create_engine('postgresql://postgres@fedr-db-1/fedresurs_db')
df.to_sql('cadastral_index', engine, if_exists='replace', index=False)
```

### Market Benchmarks

**Format**: CSV
**Fields**:
- `district`: Район
- `avg_price_sqm`: Средняя цена за м² (₽)
- `median_price_sqm`: Медианная цена за м²
- `property_type`: Тип (commercial/residential)

**Load script**:
```python
# /app/data/sberbank/loader.py
import pandas as pd
from sqlalchemy import create_engine

df = pd.read_csv('/app/data/sberbank/market_benchmarks.csv')
engine = create_engine('postgresql://postgres@fedr-db-1/fedresurs_db')
df.to_sql('market_benchmarks', engine, if_exists='replace', index=False)
```

## Common Queries

### Check lot count
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT COUNT(*) FROM lots;"
```

### View latest lots
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT id, lot_number, description, start_price FROM lots ORDER BY created_at DESC LIMIT 5;"
```

### Check orchestrator state
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT * FROM system_state WHERE task_key='trade_monitor';"
```

### Find cadastral by address
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT * FROM cadastral_index WHERE address ILIKE '%Таганская%' LIMIT 5;"
```

### District price benchmarks
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT * FROM market_benchmarks ORDER BY avg_price_sqm DESC LIMIT 10;"
```

### Check table sizes
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  n_live_tup AS rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Migrations

**Tool**: Alembic
**Location**: `/root/fedr/alembic/`
**Current version**: `a881e873d6f2`

### Check migration status
```bash
docker exec fedr-app-1 alembic current
```

### Apply migrations
```bash
docker exec fedr-app-1 alembic upgrade head
```

### Create new migration
```bash
docker exec fedr-app-1 alembic revision -m "description"
```

## Backup & Restore

### Backup
```bash
docker exec fedr-db-1 pg_dump -U postgres fedresurs_db > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
cat backup_20260218.sql | docker exec -i fedr-db-1 psql -U postgres -d fedresurs_db
```

### Backup only schema
```bash
docker exec fedr-db-1 pg_dump -U postgres -s fedresurs_db > schema.sql
```

## Data Volume

```yaml
# docker-compose.yml
volumes:
  - postgres_data:/var/lib/postgresql/data
  - ./data:/app/data  # For dataset loading
```

**Location on host**: `/root/fedr/data/`
**Location in container**: `/app/data/`

## Troubleshooting

### Cannot connect to database
```bash
# Check container is running
docker ps | grep fedr-db-1

# Check logs
docker logs fedr-db-1

# Restart
docker-compose restart db
```

### Table does not exist
```bash
# Check migrations
docker exec fedr-app-1 alembic current

# Apply migrations
docker exec fedr-app-1 alembic upgrade head
```

### Dataset not loaded
```bash
# Check data directory exists
ls /root/fedr/data/cadastral/
ls /root/fedr/data/sberbank/

# Re-run loaders
docker exec fedr-app-1 python /app/data/cadastral/loader.py
docker exec fedr-app-1 python /app/data/sberbank/loader.py
```

### Slow queries
```sql
-- Enable query logging
ALTER DATABASE fedresurs_db SET log_min_duration_statement = 1000; -- Log queries > 1s

-- Check slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```
