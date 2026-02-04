import os
import sys

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.core.config import settings
    print("Config loaded successfully")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"APP_ENV: {settings.APP_ENV}")
    
    # Проверяем, что DATABASE_URL не пустой
    if not settings.DATABASE_URL:
        print("ERROR: DATABASE_URL is empty!")
    else:
        print("DATABASE_URL looks OK")
        
except Exception as e:
    print(f"Error loading config: {e}")
    import traceback
    traceback.print_exc()