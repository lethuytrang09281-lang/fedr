import psycopg2
from dotenv import load_dotenv
import os


def check_tables_direct():
    """
    Проверяем таблицы напрямую через psycopg2
    """
    # Load environment variables
    load_dotenv()
    
    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'quser')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')
    
    print(f"Проверяем таблицы в базе данных {db_name} через psycopg2...")
    
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
        
        # Query to get all tables in public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        
        print(f"Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check specific tables that should exist
        expected_tables = ['auctions', 'lots', 'messages', 'price_schedules', 'system_state']
        print("\nПроверка ожидаемых таблиц:")
        for table_name in expected_tables:
            cur.execute("""
                SELECT EXISTS (
                   SELECT FROM information_schema.tables 
                   WHERE table_schema = 'public' 
                   AND table_name = %s
                );
            """, (table_name,))
            exists = cur.fetchone()[0]
            status = "✓ Существует" if exists else "✗ Отсутствует"
            print(f"  {table_name}: {status}")
        
        cur.close()
        conn.close()
        print("\nПроверка завершена!")
        
    except psycopg2.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")


if __name__ == "__main__":
    check_tables_direct()