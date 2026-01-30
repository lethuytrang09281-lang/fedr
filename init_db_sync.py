from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings
# Импортируем все модели для регистрации в метаданных
from src.database.models import Auction, Lot, MessageHistory, PriceSchedule, SystemState
from src.database.base import Base


def init_db():
    # Используем синхронный движок для инициализации
    # Заменяем asyncpg на psycopg2 для синхронной работы
    sync_db_url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    engine = create_engine(sync_db_url)

    # Создаем все таблицы
    Base.metadata.create_all(engine)

    print("База данных инициализирована успешно!")


if __name__ == "__main__":
    init_db()