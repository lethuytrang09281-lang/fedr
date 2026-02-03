FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для lxml (парсинг XML) и psycopg2 (база данных)
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Флаг --no-cache-dir уменьшает размер образа
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Указываем Python путь, чтобы модули виделись корректно
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
