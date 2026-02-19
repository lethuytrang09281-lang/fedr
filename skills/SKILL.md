---
name: fedresurs-pro
description: Real estate bankruptcy auction analysis platform for Moscow. Orchestrator collects commercial property lots from Russian bankruptcy registry (fedresurs), enriches with cadastral/company data, scores investment potential. Use when debugging orchestrator, checking database state, analyzing API limits, troubleshooting search pipeline, or working with Russian legal/cadastral APIs.
license: Proprietary
compatibility: Requires Docker, PostgreSQL, access to parser-api.com and Russian government APIs
metadata:
  author: ui
  version: "1.0"
  environment: VPS 157.22.231.149
  stack: FastAPI, PostgreSQL, Docker, Vue 3
---

# Fedresurs Pro — Bankruptcy Real Estate Hunter

## Overview

Fedresurs Pro identifies undervalued commercial real estate in Moscow bankruptcy auctions through automated analysis. The system:

1. **Searches** Russian bankruptcy registry (ЕФРСБ) via parser-api.com
2. **Filters** for commercial buildings in Moscow (price 1M-300M ₽)
3. **Enriches** with cadastral data, company verification, antifaud checks
4. **Scores** investment potential (deal_score = investment - fraud × 0.6)
5. **Alerts** via Telegram for hot deals (score ≥ 80)

## Architecture

```
Orchestrator (6-hour cycle)
    ↓
FedresursSearch (parser-api.com fedresurs API, 250 req/day)
    ↓
PostgreSQL (lots, auctions, cadastral_index, market_benchmarks)
    ↓
Enrichment Pipeline (Checko, Rosreestr, Moscow Open Data)
    ↓
Scoring Engine (investment_score - fraud_score × 0.6)
    ↓
Telegram Notifications (@dev2dev1_bot)
```

## Key Components

### 1. Orchestrator (`src/orchestrator.py`)
- **Schedule**: Every 6 hours (configurable via `SCAN_INTERVAL_MINUTES`)
- **API Limit Protection**: Checks parser-api.com/stat/, sleeps until midnight if < 10 requests left
- **State Management**: Tracks `last_processed_date` in `system_state` table

### 2. FedresursSearch (`src/services/fedresurs_search.py`)
- **Step 1**: Search bankrupt organizations in Moscow (`search_ur?orgRegionID=77`)
- **Step 2**: Get trade messages for each org (`get_org_messages`)
- **Step 3**: Extract lots with filters (keywords + price range)
- **Filters**: "здание", "нежилое здание", etc. + 1M-300M ₽

### 3. Database (`fedresurs_db`)
- **lots**: Bankruptcy auction lots
- **cadastral_index**: 584,354 Moscow cadastral records
- **market_benchmarks**: 60 district price benchmarks
- **system_state**: Orchestrator state tracking

### 4. API Integrations
- **Parser API**: fedresurs (250/day), arbitr (200/month), reestr (200/month)
- **Checko API**: Company verification, antifaud (unlimited)
- **Rosreestr PKK**: Cadastral data (free, rate-limited)
- **Moscow Open Data**: Zone restrictions, ПЗЗ (free)

## Common Tasks

### Check Orchestrator Status
```bash
docker logs fedr-app-1 2>&1 | grep -E "лимит|Найдено|ERROR" | tail -20
```

### Check API Limits
```bash
curl -s "https://parser-api.com/stat/?key=ede50185e3ccc8589a5c6c6efebc14cc"
```

### Check Database
```bash
docker exec fedr-db-1 psql -U postgres -d fedresurs_db \
  -c "SELECT COUNT(*) FROM lots;"
```

### Manual Search Test
```bash
docker exec -it fedr-app-1 python /app/scripts/test_search.py
```

## Reference Documents

For detailed information, see:
- **[ORCHESTRATOR.md](references/ORCHESTRATOR.md)**: Search cycle, limit protection, state management
- **[DATABASE.md](references/DATABASE.md)**: Schema, tables, datasets, queries
- **[API.md](references/API.md)**: Parser API, Checko, Rosreestr endpoints
- **[DEBUGGING.md](references/DEBUGGING.md)**: Common issues, checklists, recovery procedures
- **[DEPLOYMENT.md](references/DEPLOYMENT.md)**: Docker setup, nginx, environment variables

## Quick Troubleshooting

**Orchestrator not finding lots:**
1. Check API limit: `curl -s "https://parser-api.com/stat/..."`
2. Check logs: `docker logs fedr-app-1 | grep ERROR`
3. Run manual test: `docker exec -it fedr-app-1 python /app/scripts/test_search.py`

**Infinite loop:**
1. Check `system_state`: `SELECT * FROM system_state WHERE task_key='trade_monitor';`
2. Verify `get_last_processed_date()` returns datetime, not None
3. Check `update_state()` is called in `finally` block

**API limit exhausted:**
1. Stop orchestrator: `docker-compose down`
2. Wait until 00:00 UTC (03:00 MSK)
3. Restart: `docker-compose up -d`

## File Locations

**VPS**: root@157.22.231.149:/root/fedr
**Database**: fedr-db-1 container, `fedresurs_db` database
**Logs**: `docker logs fedr-app-1`
**Frontend**: Nginx serves Vue 3 app from `/root/fedr/frontend/dist`

## Current Status (2026-02-18)

- **Orchestrator**: Working, next search at 14:12 MSK
- **API Limits**: 10/250 fedresurs remaining (resets 03:00 MSK 2026-02-19)
- **Database**: 584,354 cadastral records, 60 benchmarks, 0 lots (waiting for search)
- **Known Issues**: Filter may be too strict, enrichment pipeline not yet enabled
