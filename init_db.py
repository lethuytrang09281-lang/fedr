"""
Инициализация базы данных - создание всех таблиц
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.database.models import Base
from src.config import settings

async def init_database():
    """Создать все таблицы в базе данных"""
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.begin() as conn:
        # Создать все таблицы из моделей
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("✅ Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(init_database())
