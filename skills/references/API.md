# External APIs

## Parser API (parser-api.com)

**Purpose**: Access to Russian legal registries (ЕФРСБ, arbitration courts, pledge registry, court records)

**Base URL**: `https://parser-api.com/`
**API Key**: `ede50185e3ccc8589a5c6c6efebc14cc`
**Documentation**: https://parser-api.com/docs/

### Rate Limits

```
fedresurs:  250/day,  7,500/month  (expires 2026-03-15)
arbitr:     200/month              (expires 2026-03-04)
reestr:     200/month              (expires 2026-03-04)
mosgorsud:  200/month              (expires 2026-03-04)
```

**Reset time**: 00:00 UTC daily (03:00 MSK)

### Check Limits

```bash
curl -s "https://parser-api.com/stat/?key=ede50185e3ccc8589a5c6c6efebc14cc"
```

**Response**:
```json
[
  {
    "service": "fedresurs",
    "day_request_count": 10,
    "day_limit": 250,
    "month_request_count": 250,
    "month_limit": 7500
  },
  {
    "service": "arbitr",
    "day_request_count": 0,
    "day_limit": 200,
    "month_request_count": 0,
    "month_limit": 200
  }
]
```

### Fedresurs Endpoints

#### 1. Search Organizations
```bash
GET https://parser-api.com/api/fedresurs/search_ur?key={KEY}&orgRegionID=77&page=1
```

**Parameters**:
- `orgRegionID=77`: Moscow region code
- `page`: Pagination (1-indexed)

**Response**:
```json
{
  "items": [
    {
      "id": "org-12345",
      "name": "ООО КОМПАНИЯ",
      "inn": "7701234567",
      "status": "bankrupt"
    }
  ],
  "total": 1234
}
```

#### 2. Get Organization Messages
```bash
GET https://parser-api.com/api/fedresurs/get_org_messages?key={KEY}&id={org_id}&page=1
```

**Filters**: Only messages with type "торги" (auctions)

**Response**:
```json
{
  "messages": [
    {
      "id": "msg-67890",
      "type": "торги",
      "datePublished": "2026-02-15T10:00:00Z",
      "lots": [...]
    }
  ]
}
```

#### 3. Get Message Details
```bash
GET https://parser-api.com/api/fedresurs/get_message?key={KEY}&id={message_id}
```

**Response**:
```json
{
  "id": "msg-67890",
  "lots": [
    {
      "lotNumber": "LOT-00001",
      "description": "Офисное здание площадью 500 м²...",
      "startPrice": 50000000,
      "type": "здание"
    }
  ],
  "debtor": {
    "inn": "7701234567",
    "name": "ООО КОМПАНИЯ"
  }
}
```

### Arbitr Endpoints (200/month)

**Use sparingly** — only for high-score lots (≥70).

#### Case Search
```bash
GET https://parser-api.com/api/arbitr/search?key={KEY}&inn={INN}
```

**Response**: Court cases involving the company.

### Reestr Endpoints (200/month)

**Use sparingly** — only for high-score lots (≥70).

#### Pledge Registry
```bash
GET https://parser-api.com/api/reestr/search?key={KEY}&cadastral_number={CADASTRAL}
```

**Response**: Pledges/liens on the property.

---

## Checko API

**Purpose**: Company verification, antifaud checks, director info, financial analysis

**Base URL**: `https://api.checko.ru/v2/`
**API Key**: (stored in `.env` as `CHECKO_API_KEY`)
**Documentation**: https://checko.ru/api
**Rate Limit**: Unlimited (paid plan)

### Endpoints

#### 1. Company Info
```bash
GET https://api.checko.ru/v2/company?key={KEY}&inn={INN}
```

**Response**:
```json
{
  "inn": "7701234567",
  "name": "ООО КОМПАНИЯ",
  "status": "active",
  "director": {
    "name": "Иванов Иван Иванович",
    "inn": "770123456789"
  },
  "authorizedCapital": 10000,
  "registrationDate": "2015-03-20"
}
```

#### 2. Antifaud Check
```bash
GET https://api.checko.ru/v2/antifaud?key={KEY}&inn={INN}
```

**Response**:
```json
{
  "fraud_score": 45,
  "risks": [
    {
      "type": "mass_address",
      "severity": "medium",
      "description": "Массовый адрес регистрации"
    },
    {
      "type": "disqualified_director",
      "severity": "high",
      "description": "Директор дисквалифицирован"
    }
  ]
}
```

**fraud_score**: 0-100 (higher = more risky)

#### 3. Financial Analysis
```bash
GET https://api.checko.ru/v2/finance?key={KEY}&inn={INN}
```

**Response**:
```json
{
  "revenue": 5000000,
  "profit": 500000,
  "assets": 10000000,
  "liabilities": 8000000,
  "year": 2025
}
```

#### 4. Director Info
```bash
GET https://api.checko.ru/v2/person?key={KEY}&inn={PERSON_INN}
```

**Response**:
```json
{
  "name": "Иванов Иван Иванович",
  "inn": "770123456789",
  "companies": [
    {"inn": "7701234567", "role": "director"},
    {"inn": "7709876543", "role": "founder"}
  ],
  "disqualified": false
}
```

#### 5. Related Companies
```bash
GET https://api.checko.ru/v2/related?key={KEY}&inn={INN}
```

**Response**: Companies with same directors/founders.

### All 13 Endpoints

1. `/company` — Basic company info
2. `/antifaud` — Fraud risk score
3. `/finance` — Financial statements
4. `/person` — Individual info
5. `/related` — Related companies
6. `/history` — Company history
7. `/licenses` — Licenses and permits
8. `/contracts` — Government contracts
9. `/court` — Court cases
10. `/bankruptcy` — Bankruptcy status
11. `/tax` — Tax debts
12. `/pledge` — Pledged assets
13. `/founders` — Ownership structure

---

## Rosreestr PKK (Public Cadastral Map)

**Purpose**: Cadastral data for real estate (area, coordinates, permitted use)

**Base URL**: `https://pkk.rosreestr.ru/api/`
**Authentication**: None (public API)
**Rate Limit**: ~10-20 requests/minute (not enforced strictly, but be respectful)

### Endpoint

```bash
GET https://pkk.rosreestr.ru/api/features/1/{cadastral_number}
```

**Example**:
```bash
curl "https://pkk.rosreestr.ru/api/features/1/77:01:0001001:123"
```

**Response**:
```json
{
  "feature": {
    "attrs": {
      "cn": "77:01:0001001:123",
      "address": "г Москва, ул Таганская, д 1",
      "area_value": 500.5,
      "cad_cost": 50000000,
      "util_by_doc": "Для размещения офисов",
      "category_type": "Земли населенных пунктов"
    },
    "center": {
      "x": 37.6173,
      "y": 55.7558
    }
  }
}
```

### Fields

- `cn`: Cadastral number
- `address`: Full address
- `area_value`: Area (м²)
- `cad_cost`: Cadastral value (₽)
- `util_by_doc`: Permitted use
- `category_type`: Land category
- `center.x`: Longitude
- `center.y`: Latitude

### Error Handling

**404**: Cadastral number not found (property may not be registered)
**429**: Rate limit exceeded (wait 1 minute, retry)

---

## Moscow Open Data (data.mos.ru)

**Purpose**: City data (zones, restrictions, master plans)

**Base URL**: `https://apidata.mos.ru/v1/`
**API Key**: `a32c7b59-183e-4643-ba40-6259eeb9c8b7`
**Documentation**: https://data.mos.ru/opendata

### Example: Zone Restrictions

```bash
GET https://apidata.mos.ru/v1/datasets/2539/rows?api_key={KEY}&$filter=contains(Address,'Таганская')
```

**Response**: JSON with zone restrictions (ПЗЗ), protected zones, etc.

### Rate Limit
Unknown, but appears generous (~100/min).

---

## Integration Flow

```
1. FedresursSearch finds lot
   ↓
2. Extract cadastral_number from description
   ↓
3. Rosreestr PKK → get area, coordinates, permitted use
   ↓
4. Checko API → verify debtor (fraud_score, director, finances)
   ↓
5. Moscow Open Data → check zone restrictions
   ↓
6. Calculate scores:
   - investment_score (location, price, area)
   - fraud_score (Checko antifaud)
   - deal_score = investment - fraud × 0.6
   ↓
7. If deal_score ≥ 80 → Telegram alert
```

---

## API Usage Guidelines

### Conservative Use (Limited APIs)

**Parser API fedresurs** (250/day):
- Use for broad search (all orgs, all messages)
- Primary data source

**Parser API arbitr/reestr** (200/month):
- ONLY use for lots with score ≥ 70
- Save requests for high-value targets

### Unlimited APIs

**Checko** (unlimited):
- Use freely for all lots
- Antifaud check is critical

**Rosreestr PKK** (rate-limited but not quota):
- Use for all lots with cadastral numbers
- Respect rate limit (~10-20/min)

**Moscow Open Data** (unknown limit):
- Use sparingly, cache results
- Most properties won't need this data

---

## Error Codes

### Parser API

- `40304`: Daily limit exhausted → sleep until midnight
- `40305`: Monthly limit exhausted → wait for next month
- `40001`: Invalid API key → check `.env`
- `40400`: Not found → entity doesn't exist

### Checko

- `401`: Invalid API key
- `404`: Company not found (INN invalid)
- `429`: Rate limit (shouldn't happen on paid plan)

### Rosreestr

- `404`: Cadastral number not found
- `429`: Rate limit → wait 1 minute

### Moscow Open Data

- `401`: Invalid API key
- `404`: Dataset not found
