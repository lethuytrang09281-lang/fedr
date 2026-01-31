# Инструкции по запуску проекта Fedresurs Radar

## Предварительные требования
- Docker и Docker Compose установлены
- Файл `.env` настроен с вашими учетными данными ЕФРСБ

## 1. Запуск инфраструктуры

### Установите Docker Compose (если не установлен)
```bash
sudo apt update
sudo apt install docker-compose
```

### Запустите базу данных PostgreSQL
```bash
docker-compose up -d db
```

Проверьте, что база данных запущена:
```bash
docker-compose ps
```

Вы должны увидеть сообщение: `Database system is ready to accept connections` в логах.

## 2. Создание первой миграции

### Вариант A: Локально (если установлен Alembic)
```bash
# Установите зависимости в виртуальном окружении
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создайте миграцию на основе моделей
alembic revision --autogenerate -m "Initial migration with UUID and ARRAY types"
```

### Вариант B: Внутри контейнера
```bash
# Соберите и запустите контейнер приложения
docker-compose build app
docker-compose run --rm app alembic revision --autogenerate -m "Initial migration"
```

## 3. Применение миграций

### Автоматически при запуске (рекомендуется)
Контейнер приложения автоматически применяет миграции через `entrypoint.sh`.

### Вручную:
```bash
docker-compose run --rm app alembic upgrade head
```

## 4. Запуск всего приложения

```bash
docker-compose up
```

## 5. Проверка работоспособности

### Проверьте логи базы данных:
```bash
docker-compose logs db | grep "ready to accept connections"
```

### Проверьте таблицы в базе данных:
```bash
docker-compose exec db psql -U postgres -d fedresurs_db -c "\dt"
```

### Проверьте GIN индекс для cadastral_numbers:
```bash
docker-compose exec db psql -U postgres -d fedresurs_db -c "\di idx_lots_cadastral_gin"
```

## 6. Команды для разработки

### Остановка всех контейнеров:
```bash
docker-compose down
```

### Остановка с удалением томов:
```bash
docker-compose down -v
```

### Пересборка и запуск:
```bash
docker-compose up --build
```

### Просмотр логов:
```bash
docker-compose logs -f app
```

## Проверка моделей

Модели уже содержат:
1. `UUID` для первичных ключей (диалект PostgreSQL)
2. `ARRAY(String)` для поля `cadastral_numbers`
3. GIN-индекс `idx_lots_cadastral_gin` для быстрого поиска по кадастровым номерам
4. Асинхронные подключения через asyncpg

## Устранение неполадок

### Ошибка с libxml2:
Контейнер уже включает установку `libxml2-dev` и `libxslt-dev`.

### Ошибка подключения к базе данных:
Убедитесь, что в `.env` установлены правильные значения:
- `DB_HOST=db` (для Docker)
- `DB_HOST=localhost` (для локальной разработки)

### Проблемы с миграциями:
Удалите папку `alembic/versions` и создайте миграцию заново:
```bash
rm -rf alembic/versions
alembic revision --autogenerate -m "Initial migration"