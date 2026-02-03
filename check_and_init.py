#!/usr/bin/env python3
"""Скрипт для проверки статуса и инициализации БД"""
import subprocess
import sys
import time

def run_command(cmd, description):
    print(f"▶ {description}...")
    print(f"  Команда: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(f"  Вывод:\n{result.stdout}")
    if result.stderr:
        print(f"  Ошибки:\n{result.stderr}")
    print(f"  Код возврата: {result.returncode}")
    return result

def main():
    print("=" * 60)
    print("Проверка статуса проекта Fedresurs Radar")
    print("=" * 60)
    
    # 1. Проверка Docker контейнеров
    result = run_command("docker ps -a --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", 
                        "Проверка Docker контейнеров")
    
    # 2. Проверка конкретно контейнеров fedresurs
    result = run_command("docker-compose ps", "Проверка контейнеров docker-compose")
    
    # 3. Проверка логов базы данных
    result = run_command("docker-compose logs --tail=10 db", "Логи базы данных")
    
    # 4. Проверка логов приложения
    result = run_command("docker-compose logs --tail=10 app", "Логи приложения")
    
    # 5. Попытка инициализации БД через скрипт
    print("\n" + "=" * 60)
    print("Попытка инициализации базы данных...")
    
    # Проверяем, какие файлы инициализации доступны
    print("\nДоступные скрипты инициализации:")
    import os
    init_scripts = ["init_db.py", "init_db_sync.py", "init_db_async_fixed.py", "init_db_new.py"]
    for script in init_scripts:
        if os.path.exists(script):
            print(f"  ✅ {script}")
        else:
            print(f"  ❌ {script} (не найден)")
    
    # Если контейнеры работают, пытаемся выполнить инициализацию
    print("\nПопытка запуска инициализации через контейнер...")
    result = run_command("docker-compose exec -T app python init_db_sync.py", 
                        "Инициализация БД (init_db_sync.py)")
    
    if result.returncode != 0:
        print("\nПопытка через другую команду...")
        result = run_command("docker-compose run --rm app python init_db_sync.py",
                           "Инициализация БД (run --rm)")
    
    # 6. Проверка таблиц
    print("\n" + "=" * 60)
    print("Проверка существующих таблиц...")
    result = run_command("docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\\dt'",
                        "Список таблиц в БД")
    
    print("\n" + "=" * 60)
    print("Проверка завершена!")
    
    if result.returncode == 0:
        print("✅ База данных доступна и содержит таблицы")
    else:
        print("❌ Проблемы с подключением к базе данных")

if __name__ == "__main__":
    main()