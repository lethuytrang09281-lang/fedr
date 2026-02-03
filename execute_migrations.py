#!/usr/bin/env python3
import subprocess
import sys
import time
import os

def run_cmd(cmd, desc):
    print(f"\n▶ {desc}")
    print(f"  $ {cmd}")
    sys.stdout.flush()
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=30
        )
        
        print(f"  Статус: {result.returncode}")
        if result.stdout:
            print(f"  Вывод:\n{result.stdout[:1000]}")
        if result.stderr:
            print(f"  Ошибки:\n{result.stderr[:1000]}")
            
        return result
    except subprocess.TimeoutExpired:
        print("  ⚠ Таймаут (30 сек)")
        return None
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return None

def main():
    print("=" * 60)
    print("Настройка миграций Alembic для Fedresurs Radar")
    print("=" * 60)
    
    os.chdir("/root/fedr")
    
    # 1. Проверить контейнеры
    result = run_cmd("docker-compose ps", "Проверка контейнеров")
    if not result or result.returncode != 0:
        print("❌ Проблема с docker-compose")
        return 1
    
    # 2. Проверить доступность контейнера приложения
    result = run_cmd("docker-compose exec -T app whoami", "Проверка доступности контейнера app")
    if not result or result.returncode != 0:
        print("❌ Контейнер 'app' недоступен")
        return 1
    
    # 3. Создать миграцию
    print("\n" + "=" * 60)
    print("Создание миграции...")
    result = run_cmd(
        'docker-compose exec -T app alembic revision --autogenerate -m "Initial_migration_with_is_restricted"',
        "Создание миграции Alembic"
    )
    
    if result and result.returncode != 0:
        print("⚠ Не удалось создать миграцию, продолжаем...")
    
    # 4. Применить миграцию
    print("\n" + "=" * 60)
    print("Применение миграции...")
    result = run_cmd(
        "docker-compose exec -T app alembic upgrade head",
        "Применение миграций Alembic"
    )
    
    if result and result.returncode == 0:
        print("\n✅ Миграции успешно применены!")
        
        # 5. Проверить созданные файлы
        print("\n" + "=" * 60)
        print("Проверка созданных файлов миграций...")
        run_cmd("find alembic/versions -name '*.py' -type f | head -5", "Список файлов миграций")
        
        # 6. Проверить таблицы в БД
        print("\n" + "=" * 60)
        print("Проверка таблиц в базе данных...")
        run_cmd(
            "docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\\dt'",
            "Список таблиц в PostgreSQL"
        )
    else:
        print("\n❌ Не удалось применить миграции")
        return 1
    
    print("\n" + "=" * 60)
    print("Завершено!")
    return 0

if __name__ == "__main__":
    sys.exit(main())