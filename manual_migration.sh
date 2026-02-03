#!/bin/bash
set -e

echo "=== Manual Migration Script (bypassing async issues) ==="
echo

cd /root/fedr

# 1. Запускаем только базу данных
echo "1. Starting only database container..."
docker-compose up -d db

echo "Waiting for PostgreSQL..."
sleep 5

# 2. Проверяем подключение
echo -e "\n2. Testing database connection..."
docker-compose exec -T db psql -U postgres -d fedresurs_db -c "SELECT 1;" || {
    echo "Failed to connect to database"
    exit 1
}

# 3. Проверяем текущие таблицы
echo -e "\n3. Current tables in database:"
docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\dt'

# 4. Создаем таблицы напрямую через SQL
echo -e "\n4. Creating tables manually via SQL..."
echo "Applying SQL script..."
docker-compose exec -T db psql -U postgres -d fedresurs_db << 'EOF'
-- Создание таблицы system_state
CREATE TABLE IF NOT EXISTS system_state (
    id SERIAL PRIMARY KEY,
    current_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы auctions
CREATE TABLE IF NOT EXISTS auctions (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(255) NOT NULL UNIQUE,
    trade_number VARCHAR(255) NOT NULL,
    trade_date TIMESTAMP WITH TIME ZONE NOT NULL,
    trade_type VARCHAR(100) NOT NULL,
    trade_status VARCHAR(100) NOT NULL,
    trade_link TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы lots
CREATE TABLE IF NOT EXISTS lots (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
    lot_number VARCHAR(255) NOT NULL,
    description TEXT,
    start_price DECIMAL(15,2),
    current_price DECIMAL(15,2),
    currency VARCHAR(10),
    is_restricted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(100) NOT NULL,
    message_date TIMESTAMP WITH TIME ZONE NOT NULL,
    message_text TEXT,
    xml_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы price_schedules
CREATE TABLE IF NOT EXISTS price_schedules (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER REFERENCES lots(id) ON DELETE CASCADE,
    reduction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    new_price DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE INDEX IF NOT EXISTS idx_auctions_trade_id ON auctions(trade_id);
CREATE INDEX IF NOT EXISTS idx_auctions_trade_date ON auctions(trade_date);
CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id);
CREATE INDEX IF NOT EXISTS idx_lots_is_restricted ON lots(is_restricted);
CREATE INDEX IF NOT EXISTS idx_messages_trade_id ON messages(trade_id);
CREATE INDEX IF NOT EXISTS idx_price_schedules_lot_id ON price_schedules(lot_id);
EOF

# 5. Проверяем созданные таблицы
echo -e "\n5. Tables after manual creation:"
docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\dt'

# 6. Восстанавливаем entrypoint.sh
echo -e "\n6. Restoring entrypoint.sh to enable auto-migrations..."
sed -i 's/# alembic upgrade head/alembic upgrade head/' entrypoint.sh
echo "Entrypoint restored (will use auto-migrations on next start)"

# 7. Тестируем запуск приложения с исправленным entrypoint
echo -e "\n7. Testing application startup..."
docker-compose up -d app

sleep 3

echo -e "\n8. Checking container status:"
docker-compose ps

echo -e "\n9. Application logs (last 10 lines):"
docker-compose logs --tail=10 app

echo -e "\n=== Manual migration complete ==="
echo "Database tables created:"
docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\dt'