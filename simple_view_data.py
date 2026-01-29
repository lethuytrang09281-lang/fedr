import asyncio
import aiosqlite
import sqlite3
from src.config import settings
import os


def view_collected_data():
    """
    Просмотр собранных данных из SQLite базы
    """
    print("Просмотр собранных данных из fedresurs.db")
    
    # Проверим, существует ли файл базы данных
    if not os.path.exists('fedresurs.db'):
        print("Файл базы данных не найден")
        return
    
    # Подключаемся к базе данных
    try:
        conn = sqlite3.connect('fedresurs.db')
        cursor = conn.cursor()
        
        # Проверим, какие таблицы существуют
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Найденные таблицы: {[table[0] for table in tables]}")
        
        # Проверим содержимое таблиц
        for table_name in ['auctions', 'lots', 'messages']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"\n--- Таблица {table_name} ---")
                print(f"Всего записей: {count}")
                
                if count > 0:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [column[1] for column in cursor.fetchall()]
                    print(f"Колонки: {columns}")
                    
                    # Выведем первые несколько записей
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                    rows = cursor.fetchall()
                    for i, row in enumerate(rows, 1):
                        print(f"  Запись {i}: {row}")
            except sqlite3.OperationalError as e:
                print(f"Таблица {table_name} не существует: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"Ошибка при чтении базы данных: {e}")


if __name__ == "__main__":
    view_collected_data()