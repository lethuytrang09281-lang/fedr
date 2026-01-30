import psycopg2
from dotenv import load_dotenv
import os


def check_tables():
    """
    Проверяем, какие таблицы существуют в базе данных
    """
    # Load environment variables
    load_dotenv()
    
    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'quser')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')
    
    print(f"Проверяем таблицы в базе данных {db_name}...")
    
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
        
        # Query to get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        
        print(f"Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Also check for records in each table
        for table in tables:
            table_name = table[0]
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                print(f"    ({table_name}): {count} записей")
            except Exception as e:
                print(f"    (ошибка при подсчете записей в {table_name}: {e}")
        
        cur.close()
        conn.close()
        print("Проверка завершена!")
        
    except psycopg2.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")


if __name__ == "__main__":
    check_tables()