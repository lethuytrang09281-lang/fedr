# Deployment & Infrastructure

## VPS Details

**Host**: 157.22.231.149
**OS**: Ubuntu 24.04 LTS
**Access**: SSH key only (root@157.22.231.149)
**Location**: `/root/fedr/`

## Architecture

```
VPS (157.22.231.149)
│
├── Docker Containers
│   ├── fedr-app-1 (FastAPI + Orchestrator)
│   └── fedr-db-1 (PostgreSQL 16)
│
├── Nginx (Frontend proxy)
│   └── Serves Vue 3 from /root/fedr/frontend/dist
│
└── Xray VPN
    └── Split-routing via Germany
```

## Docker Setup

### docker-compose.yml

```yaml
version: "3.8"

services:
  app:
    build: .
    container_name: fedr-app-1
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres@db/fedresurs_db
      - PARSER_API_KEY=${PARSER_API_KEY}
      - CHECKO_API_KEY=${CHECKO_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    volumes:
      - ./data:/app/data
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:16
    container_name: fedr-db-1
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=fedresurs_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

volumes:
  postgres_data:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Environment Variables

### .env

```bash
# Database
DATABASE_URL=postgresql://postgres@fedr-db-1/fedresurs_db
POSTGRES_PASSWORD=<secure_password>

# APIs
PARSER_API_KEY=ede50185e3ccc8589a5c6c6efebc14cc
CHECKO_API_KEY=<checko_key>
MOSCOW_API_KEY=a32c7b59-183e-4643-ba40-6259eeb9c8b7

# Telegram
TELEGRAM_BOT_TOKEN=<bot_token>

# Orchestrator
SCAN_INTERVAL_MINUTES=360  # 6 hours

# Optional (not used)
EFRSB_LOGIN=
EFRSB_PASSWORD=
EFRSB_BASE_URL=
```

**Security**: .env is in .gitignore, never commit!

## Deployment Process

### Initial Setup

```bash
# 1. Clone repo (or rsync code)
cd /root
git clone <repo_url> fedr
cd fedr

# 2. Create .env
cp .env.example .env
nano .env  # Fill in secrets

# 3. Build and start
docker-compose build
docker-compose up -d

# 4. Apply migrations
docker exec fedr-app-1 alembic upgrade head

# 5. Load datasets
docker exec fedr-app-1 python /app/data/cadastral/loader.py
docker exec fedr-app-1 python /app/data/sberbank/loader.py

# 6. Check status
docker-compose ps
docker logs fedr-app-1
```

### Update Deployment

```bash
cd /root/fedr

# 1. Pull changes
git pull origin main

# 2. Rebuild
docker-compose build

# 3. Apply migrations
docker exec fedr-app-1 alembic upgrade head

# 4. Restart
docker-compose restart app

# 5. Verify
docker logs fedr-app-1 | tail -20
```

### Rollback

```bash
# 1. Git rollback
git log --oneline  # Find commit
git reset --hard <commit_hash>

# 2. Rebuild
docker-compose down
docker-compose build
docker-compose up -d
```

## Nginx Configuration

### /etc/nginx/sites-available/fedresurs-pro

```nginx
server {
    listen 80;
    server_name 157.22.231.149;

    # Frontend (Vue 3)
    location / {
        root /root/fedr/frontend/dist;
        try_files $uri $uri/ /index.html;
        
        # Disable cache during development
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # API (FastAPI)
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Static files (js/css)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        root /root/fedr/frontend/dist;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
```

### Enable Site

```bash
# Link config
sudo ln -s /etc/nginx/sites-available/fedresurs-pro /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload
sudo nginx -s reload
```

### SSL (Optional)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

## Frontend Build

### Build Process

```bash
cd /root/fedr/frontend

# Install dependencies
npm install

# Build for production
npm run build

# Output: /root/fedr/frontend/dist/
```

### Development Mode

```bash
# Run dev server (local machine)
npm run dev
# Access at http://localhost:5173

# API proxy in vite.config.js:
export default {
  server: {
    proxy: {
      '/api': 'http://157.22.231.149:8000'
    }
  }
}
```

## Monitoring

### Container Health

```bash
# Status
docker-compose ps

# Logs (live)
docker logs -f fedr-app-1

# Resource usage
docker stats

# Restart unhealthy container
docker-compose restart app
```

### Application Logs

```bash
# Orchestrator logs
docker logs fedr-app-1 | grep orchestrator

# API request logs
docker logs fedr-app-1 | grep -E "GET|POST"

# Errors
docker logs fedr-app-1 | grep -i error
```

### Database Health

```bash
# Connection test
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "SELECT 1;"

# Table sizes
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_stat_user_tables;
"

# Active connections
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
"
```

## Backup & Disaster Recovery

### Automated Backup (Cron)

```bash
# Create backup script
cat > /root/fedr/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/root/fedr/backups
DATE=$(date +%Y%m%d_%H%M%S)
docker exec fedr-db-1 pg_dump -U postgres fedresurs_db > $BACKUP_DIR/backup_$DATE.sql
# Keep only last 7 days
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
EOF

chmod +x /root/fedr/backup.sh

# Add to cron (daily at 3 AM)
crontab -e
# Add line:
0 3 * * * /root/fedr/backup.sh
```

### Manual Backup

```bash
# Full backup
docker exec fedr-db-1 pg_dump -U postgres fedresurs_db > backup_$(date +%Y%m%d).sql

# Schema only
docker exec fedr-db-1 pg_dump -U postgres -s fedresurs_db > schema.sql

# Data only
docker exec fedr-db-1 pg_dump -U postgres -a fedresurs_db > data.sql
```

### Restore

```bash
# From backup file
cat backup_20260218.sql | docker exec -i fedr-db-1 psql -U postgres -d fedresurs_db

# Or if DB needs to be recreated
docker exec fedr-db-1 psql -U postgres -c "DROP DATABASE IF EXISTS fedresurs_db;"
docker exec fedr-db-1 psql -U postgres -c "CREATE DATABASE fedresurs_db;"
cat backup.sql | docker exec -i fedr-db-1 psql -U postgres -d fedresurs_db
```

## Security

### SSH Access

```bash
# Only key-based auth (password disabled)
# Key location: ~/.ssh/authorized_keys

# Add new key
echo "ssh-rsa AAAA..." >> ~/.ssh/authorized_keys
```

### Firewall (UFW)

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow 22

# Allow HTTP
sudo ufw allow 80

# Allow HTTPS
sudo ufw allow 443

# Check status
sudo ufw status
```

### Docker Security

```bash
# Don't expose DB port publicly (only to Docker network)
# In docker-compose.yml:
ports:
  - "127.0.0.1:5432:5432"  # Bind to localhost only
```

### Environment Variables

```bash
# Never commit .env
echo ".env" >> .gitignore

# Restrict permissions
chmod 600 /root/fedr/.env
```

## Network

### Xray VPN

**Purpose**: Split-routing for Russian government APIs

```bash
# Check VPN status
sudo systemctl status xray

# Restart VPN
sudo systemctl restart xray

# Test routing
curl --interface tun0 ifconfig.me
```

**Routes**: Only Russian IPs (Rosreestr, mos.ru) go through VPN, rest direct.

### Docker Network

```bash
# Inspect network
docker network inspect fedr_default

# DNS resolution
docker exec fedr-app-1 ping fedr-db-1
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs fedr-app-1

# Common issues:
# - Port 8000 already in use
# - Missing .env variables
# - Database not ready

# Fix: Restart in order
docker-compose down
docker-compose up -d db
sleep 5
docker-compose up -d app
```

### Database Connection Refused

```bash
# Check DB container
docker ps | grep fedr-db-1

# Check network
docker network ls
docker network inspect fedr_default

# Restart
docker-compose restart db
```

### Nginx 502 Bad Gateway

```bash
# Check app container
docker ps | grep fedr-app-1

# Check logs
docker logs fedr-app-1

# Test API directly
curl http://localhost:8000/api/health
```

### Out of Disk Space

```bash
# Check usage
df -h

# Clean Docker
docker system prune -a --volumes

# Clean logs
truncate -s 0 /var/log/nginx/access.log
truncate -s 0 /var/log/nginx/error.log
```

## Maintenance

### Regular Tasks

```bash
# Weekly: Update system
sudo apt update && sudo apt upgrade -y

# Weekly: Clean Docker
docker system prune -f

# Daily: Check logs for errors
docker logs fedr-app-1 | grep -i error

# Daily: Check API limits
curl -s "https://parser-api.com/stat/?key=..."
```

### Performance Tuning

```bash
# PostgreSQL config
docker exec fedr-db-1 psql -U postgres -d fedresurs_db -c "
ALTER DATABASE fedresurs_db SET shared_buffers = '256MB';
ALTER DATABASE fedresurs_db SET effective_cache_size = '1GB';
"

# Restart DB
docker-compose restart db
```
