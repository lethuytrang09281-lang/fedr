import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.database.base import Base
from src.config import settings
# Импортируем все модели для регистрации в метаданных
from src.database.models import Auction, Lot, MessageHistory, PriceSchedule


async def init_db():
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)

    print("База данных инициализирована успешно!")


if __name__ == "__main__":
    asyncio.run(init_db())