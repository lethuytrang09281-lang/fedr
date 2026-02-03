#!/usr/bin/env python3
import subprocess
import sys
import os
import time

# Открываем файл для записи вывода
output_file = "/root/fedr/direct_output.txt"

def run_and_save(cmd, desc):
    with open(output_file, "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Command: {cmd}\n")
        f.write(f"Description: {desc}\n")
        f.write(f"{'='*60}\n")
    
    print(f"Executing: {cmd}")
    
    # Выполняем команду и перенаправляем вывод в файл
    with open(output_file, "a") as f:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        returncode = process.returncode
        
        f.write(f"Return code: {returncode}\n")
        
        if stdout:
            f.write("STDOUT:\n")
            f.write(stdout)
            f.write("\n")
        
        if stderr:
            f.write("STDERR:\n")
            f.write(stderr)
            f.write("\n")
        
        return returncode, stdout, stderr

def main():
    # Очищаем файл вывода
    with open(output_file, "w") as f:
        f.write("Fedresurs Radar Migration Execution\n")
        f.write(f"Time: {time.ctime()}\n")
        f.write("="*60 + "\n")
    
    os.chdir("/root/fedr")
    
    print("Starting migration execution...")
    
    # 1. Проверка Docker
    run_and_save("docker --version", "Docker version check")
    
    # 2. Проверка docker-compose
    run_and_save("docker-compose --version", "Docker Compose version check")
    
    # 3. Проверка контейнеров
    run_and_save("docker ps -a", "List all Docker containers")
    
    # 4. Проверка контейнеров проекта
    run_and_save("docker-compose ps", "List project containers")
    
    # 5. Попробуем запустить контейнеры, если они не запущены
    print("Starting containers if not running...")
    run_and_save("docker-compose up -d", "Start containers")
    
    time.sleep(5)
    
    # 6. Проверка после запуска
    run_and_save("docker-compose ps", "Check containers after start")
    
    # 7. Проверка доступности контейнера app
    run_and_save("docker-compose exec -T app whoami", "Check app container accessibility")
    
    # 8. Выполнение миграций
    print("Executing Alembic migrations...")
    
    # 8.1 Создание миграции
    run_and_save(
        'docker-compose exec -T app alembic revision --autogenerate -m "Initial_migration_with_is_restricted"',
        "Create Alembic migration"
    )
    
    # 8.2 Применение миграции
    run_and_save(
        "docker-compose exec -T app alembic upgrade head",
        "Apply Alembic migrations"
    )
    
    # 9. Проверка таблиц в БД
    run_and_save(
        "docker-compose exec -T db psql -U postgres -d fedresurs_db -c '\\dt'",
        "Check database tables"
    )
    
    print(f"\nExecution complete. Check output in: {output_file}")
    print("\nLast 50 lines of output:")
    
    # Показываем последние строки вывода
    try:
        with open(output_file, "r") as f:
            lines = f.readlines()
            for line in lines[-50:]:
                print(line, end="")
    except Exception as e:
        print(f"Error reading output file: {e}")

if __name__ == "__main__":
    main()