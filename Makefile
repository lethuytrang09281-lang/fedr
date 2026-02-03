# FEDRESURS RADAR - Makefile
# Удобные команды для управления проектом

.PHONY: help setup up down logs health test clean

# Цвета для вывода
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Показать эту справку
	@echo "$(BLUE)FEDRESURS RADAR - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

setup: ## Первоначальная настройка проекта
	@echo "$(YELLOW)Setting up FEDRESURS RADAR...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from template$(NC)"; \
	else \
		echo "$(YELLOW)⚠ .env already exists, skipping$(NC)"; \
	fi
	@mkdir -p logs
	@echo "$(GREEN)✓ Created logs directory$(NC)"
	@echo ""
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "  1. Review and edit .env file"
	@echo "  2. Run: make up"
	@echo "  3. Run: make health"

install: ## Установка Python-зависимостей
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	pip install -r requirements.txt --break-system-packages
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

up: ## Запуск инфраструктуры (PostgreSQL + App)
	@echo "$(YELLOW)Starting infrastructure...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Infrastructure started$(NC)"
	@echo ""
	@echo "$(BLUE)Waiting for PostgreSQL to be ready...$(NC)"
	@sleep 3
	@docker-compose exec -T db pg_isready -U postgres && \
		echo "$(GREEN)✓ PostgreSQL is ready$(NC)" || \
		echo "$(YELLOW)⚠ PostgreSQL not ready yet, wait a moment$(NC)"

down: ## Остановка инфраструктуры
	@echo "$(YELLOW)Stopping infrastructure...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Infrastructure stopped$(NC)"

restart: down up ## Перезапуск инфраструктуры

logs: ## Просмотр логов Docker
	docker-compose logs -f

logs-db: ## Просмотр логов PostgreSQL
	docker-compose logs -f db

logs-app: ## Просмотр логов приложения
	docker-compose logs -f app

health: ## Проверка здоровья системы
	@echo "$(YELLOW)Running health checks...$(NC)"
	@python health_check.py

test-api: ## Тест API клиента
	@echo "$(YELLOW)Testing API client...$(NC)"
	@python -c "import asyncio; from src.client.api import EfrsbClient; \
		async def test(): \
			client = EfrsbClient(); \
			await client.login(); \
			print('Auth OK'); \
			await client.close(); \
		asyncio.run(test())"

test-parser: ## Тест XML парсера
	@echo "$(YELLOW)Testing XML parser...$(NC)"
	@python src/services/xml_parser.py

psql: ## Подключиться к PostgreSQL (psql)
	docker-compose exec db psql -U postgres -d fedresurs_db

clean: ## Очистка временных файлов
	@echo "$(YELLOW)Cleaning temporary files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean down ## Полная очистка (включая Docker volumes)
	@echo "$(YELLOW)Removing Docker volumes...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

status: ## Показать статус контейнеров
	@docker-compose ps

config: ## Показать текущую конфигурацию
	@echo "$(BLUE)Current Configuration:$(NC)"
	@python -c "from src.config import settings; \
		print(f'Environment: {getattr(settings, \"EFRSB_ENV\", \"NOT SET\")}'); \
		print(f'API URL: {getattr(settings, \"base_url\", \"NOT SET\")}'); \
		print(f'Rate Limit: {getattr(settings, \"MAX_REQS_PER_SECOND\", \"NOT SET\")} req/sec'); \
		print(f'Database: {getattr(settings, \"DB_HOST\", \"localhost\")}:{getattr(settings, \"DB_PORT\", 5432)}/{getattr(settings, \"DB_NAME\", \"fedresurs_db\")}');"

backup-db: ## Создать бэкап базы данных
	@echo "$(YELLOW)Creating database backup...$(NC)"
	@mkdir -p backups
	@docker-compose exec -T db pg_dump -U postgres fedresurs_db | gzip > backups/fedresurs_radar_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"

# Разработка
dev: ## Режим разработки (watch logs)
	@echo "$(BLUE)Development mode - press Ctrl+C to stop$(NC)"
	@make logs

# По умолчанию показываем help
.DEFAULT_GOAL := help