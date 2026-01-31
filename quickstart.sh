#!/bin/bash
# FEDRESURS RADAR - Quick Start Script
# Автоматическая настройка и запуск системы

set -e  # Exit on error

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   FEDRESURS RADAR                          ║"
echo "║              Quick Start Installation                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверка Python версии
echo -e "${YELLOW}[1/6] Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.11"

if awk -v ver="$PYTHON_VERSION" -v req="$REQUIRED_VERSION" 'BEGIN{exit(!(ver>=req))}'; then
    echo -e "${GREEN}✓ Python $PYTHON_VERSION installed${NC}"
else
    echo -e "${RED}✗ Python 3.11+ required (found: $PYTHON_VERSION)${NC}"
    echo "  Install: sudo apt install python3.11"
    exit 1
fi

# Проверка Docker
echo -e "${YELLOW}[2/6] Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker installed${NC}"
else
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Install: https://docs.docker.com/get-docker/"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose installed${NC}"
else
    echo -e "${RED}✗ Docker Compose not found${NC}"
    echo "  Install: sudo apt install docker-compose"
    exit 1
fi

# Создание виртуального окружения
echo -e "${YELLOW}[3/6] Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${BLUE}→ Virtual environment already exists${NC}"
fi

# Активация venv
source venv/bin/activate

# Установка зависимостей
echo -e "${YELLOW}[4/6] Installing Python dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt --break-system-packages
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Создание .env
echo -e "${YELLOW}[5/6] Creating configuration...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from template${NC}"
else
    echo -e "${BLUE}→ .env already exists${NC}"
fi

# Создание директории для логов
mkdir -p logs
echo -e "${GREEN}✓ Created logs directory${NC}"

# Запуск инфраструктуры
echo -e "${YELLOW}[6/6] Starting infrastructure...${NC}"
docker-compose up -d

# Ожидание готовности PostgreSQL
echo -e "${BLUE}→ Waiting for PostgreSQL...${NC}"
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U fedresurs_user &>/dev/null; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL timeout${NC}"
        exit 1
    fi
    sleep 1
done

# Финальная проверка
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Installation complete!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Запуск health check
echo -e "${YELLOW}Running health checks...${NC}"
python health_check.py

# Итоги
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Review configuration: ${YELLOW}cat .env${NC}"
echo "  2. Check logs:           ${YELLOW}make logs${NC}"
echo "  3. View database:        ${YELLOW}make psql${NC}"
echo "  4. Test API:             ${YELLOW}make test-api${NC}"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  ${YELLOW}make help${NC}     - Show all available commands"
echo "  ${YELLOW}make health${NC}   - Run health checks"
echo "  ${YELLOW}make down${NC}     - Stop infrastructure"
echo "  ${YELLOW}make logs${NC}     - View Docker logs"
echo ""
echo -e "${GREEN}FEDRESURS RADAR is ready to deploy! 🚀${NC}"
echo ""
