import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings
# Импортируем все модели для регистрации в метаданных
from src.database.models import Auction, Lot, MessageHistory, PriceSchedule, SystemState
from src.database.base import Base


async def init_db_async():
    # Используем асинхронный движок для инициализации
    # Но с URL, замененным на psycopg2 для создания таблиц
    sync_db_url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    
    # Если замена не сработала, используем оригинальный URL
    if sync_db_url == settings.database_url:
        # Создаем движок с оригинальным URL, но синхронно создаем таблицы
        engine = create_async_engine(settings.database_url)
    else:
        engine = create_async_engine(sync_db_url)
    
    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("База данных инициализирована успешно!")


if __name__ == "__main__":
    asyncio.run(init_db_async())