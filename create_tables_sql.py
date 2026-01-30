import psycopg2
from dotenv import load_dotenv
import os


def create_tables_sql():
    """
    Создаем таблицы напрямую через SQL запросы
    """
    # Load environment variables
    load_dotenv()
    
    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'quser')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')
    
    print(f"Создаем таблицы в базе данных {db_name}...")
    
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        )
        
        cur = conn.cursor()
        
        # Create enums first
        try:
            cur.execute("""
                CREATE TYPE lot_status AS ENUM (
                    'Announced', 'Active', 'Failed', 'Sold', 'Cancelled'
                );
            """)
        except psycopg2.Error:
            # Enum может уже существовать
            conn.rollback()
            print("Тип enum уже существует")
        
        # Create tables
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS system_state (
                task_key VARCHAR(50) PRIMARY KEY,
                last_processed_date TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS auctions (
                guid UUID PRIMARY KEY,
                number VARCHAR(100),
                etp_id VARCHAR(255),
                organizer_inn VARCHAR(20),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                guid UUID PRIMARY KEY,
                auction_id UUID REFERENCES auctions(guid),
                type VARCHAR(100) NOT NULL,
                date_publish TIMESTAMP NOT NULL,
                content_xml TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS lots (
                id SERIAL PRIMARY KEY,
                guid UUID,
                auction_id UUID NOT NULL REFERENCES auctions(guid) ON DELETE CASCADE,
                lot_number INTEGER DEFAULT 1,
                description TEXT NOT NULL,
                start_price NUMERIC(20, 2),
                category_code VARCHAR(20),
                cadastral_numbers TEXT[] DEFAULT '{}',
                status lot_status DEFAULT 'Announced'::lot_status
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS price_schedules (
                id SERIAL PRIMARY KEY,
                lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
                date_start TIMESTAMP NOT NULL,
                date_end TIMESTAMP NOT NULL,
                price NUMERIC(20, 2) NOT NULL
            );
            """
        ]

        for sql in tables_sql:
            try:
                cur.execute(sql)
            except psycopg2.Error as e:
                print(f"Ошибка при создании таблицы: {e}")
                conn.rollback()

        # Create indexes
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_auctions_number ON auctions(number);",
            "CREATE INDEX IF NOT EXISTS idx_auctions_organizer_inn ON auctions(organizer_inn);",
            "CREATE INDEX IF NOT EXISTS idx_messages_date_publish ON messages(date_publish);",
            "CREATE INDEX IF NOT EXISTS idx_lots_guid ON lots(guid);",
            "CREATE INDEX IF NOT EXISTS idx_lots_category_code ON lots(category_code);",
            "CREATE INDEX IF NOT EXISTS idx_lots_cadastral_gin ON lots USING GIN (cadastral_numbers);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_lots_auction_lot_num ON lots (auction_id, lot_number);"
        ]
        
        for sql in indexes_sql:
            try:
                cur.execute(sql)
            except psycopg2.Error as e:
                print(f"Ошибка при создании индекса: {e}")
                conn.rollback()
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("Все таблицы успешно созданы!")
        
    except psycopg2.Error as e:
        print(f"Ошибка при подключении или создании таблиц: {e}")


if __name__ == "__main__":
    create_tables_sql()