import psycopg2
from dotenv import load_dotenv
import os


def check_saved_data():
    """
    Проверяем, что данные сохраняются в PostgreSQL
    """
    # Load environment variables
    load_dotenv()
    
    # Get database settings from environment
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'quser')
    db_name = os.getenv('DB_NAME', 'fedresurs_db')
    
    print(f"Проверяем сохраненные данные в базе данных {db_name}...")
    
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
        
        # Check counts in each table
        tables = ['auctions', 'lots', 'messages', 'price_schedules', 'system_state']
        
        for table_name in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                print(f"Таблица {table_name}: {count} записей")
                
                # If there are records, show a few examples
                if count > 0:
                    cur.execute(f"SELECT * FROM {table_name} LIMIT 2;")
                    rows = cur.fetchall()
                    for i, row in enumerate(rows):
                        print(f"  Запись {i+1}: {row}")
                        
            except psycopg2.Error as e:
                print(f"Ошибка при чтении таблицы {table_name}: {e}")
        
        cur.close()
        conn.close()
        print("\nПроверка завершена!")
        
    except psycopg2.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")


if __name__ == "__main__":
    check_saved_data()