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

up: ## Запуск инфраструктуры (PostgreSQL + Redis)
	@echo "$(YELLOW)Starting infrastructure...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Infrastructure started$(NC)"
	@echo ""
	@echo "$(BLUE)Waiting for PostgreSQL to be ready...$(NC)"
	@sleep 3
	@docker-compose exec -T postgres pg_isready -U fedresurs_user && \
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
	docker-compose logs -f postgres

logs-app: ## Просмотр логов приложения
	tail -f logs/fedresurs_radar.log

health: ## Проверка здоровья системы
	@echo "$(YELLOW)Running health checks...$(NC)"
	@python health_check.py

test-api: ## Тест API клиента
	@echo "$(YELLOW)Testing API client...$(NC)"
	@python src/api_client.py

test-parser: ## Тест XML парсера
	@echo "$(YELLOW)Testing XML parser...$(NC)"
	@python src/xml_parser.py

psql: ## Подключиться к PostgreSQL (psql)
	docker-compose exec postgres psql -U fedresurs_user -d fedresurs_radar

redis-cli: ## Подключиться к Redis
	docker-compose exec redis redis-cli

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

stats: ## Показать статистику использования ресурсов
	@docker stats --no-stream fedresurs_postgres fedresurs_redis 2>/dev/null || \
		echo "$(YELLOW)⚠ Containers not running. Run 'make up' first$(NC)"

config: ## Показать текущую конфигурацию
	@echo "$(BLUE)Current Configuration:$(NC)"
	@python -c "from src.config import settings; \
		print(f'Environment: {settings.efrsb_env}'); \
		print(f'API URL: {settings.api_base_url}'); \
		print(f'Rate Limit: {settings.max_reqs_per_second} req/sec'); \
		print(f'Database: {settings.db_host}:{settings.db_port}/{settings.db_name}'); \
		print(f'Land Codes: {len(settings.land_codes)}'); \
		print(f'Include Keywords: {len(settings.include_keywords)}');"

backup-db: ## Создать бэкап базы данных
	@echo "$(YELLOW)Creating database backup...$(NC)"
	@mkdir -p backups
	@docker-compose exec -T postgres pg_dump -U fedresurs_user fedresurs_radar | gzip > backups/fedresurs_radar_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"

# Разработка
dev: ## Режим разработки (watch logs)
	@echo "$(BLUE)Development mode - press Ctrl+C to stop$(NC)"
	@make logs

format: ## Форматирование кода (black)
	@echo "$(YELLOW)Formatting code...$(NC)"
	@black src/ --line-length 100 || echo "$(YELLOW)Install black: pip install black$(NC)"

lint: ## Проверка кода (flake8)
	@echo "$(YELLOW)Linting code...$(NC)"
	@flake8 src/ --max-line-length=100 || echo "$(YELLOW)Install flake8: pip install flake8$(NC)"

# По умолчанию показываем help
.DEFAULT_GOAL := help
