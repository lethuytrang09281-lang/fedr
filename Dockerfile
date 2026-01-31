FROM python:3.11-slim

# Установка системных зависимостей для lxml и netcat для проверки доступности БД
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    gcc \
    g++ \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Сделаем entrypoint исполняемым
RUN chmod +x entrypoint.sh

WORKDIR /app

ENTRYPOINT ["./entrypoint.sh"]
