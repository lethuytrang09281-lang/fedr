import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from src.config import settings
from src.database.models import Auction, Lot, MessageHistory


async def check_collected_data():
    """
    Проверяем собранные данные в PostgreSQL
    """
    print("Проверяем собранные данные в PostgreSQL...")
    
    # Создаем асинхронный движок
    engine = create_async_engine(settings.database_url)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with SessionLocal() as session:
            # Подсчитаем количество записей в каждой таблице
            for model, table_name in [(Auction, 'auctions'), (Lot, 'lots'), (MessageHistory, 'messages')]:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count_result = result.fetchone()[0]
                    print(f"Таблица {table_name}: {count_result} записей")
                    
                    if count_result > 0:
                        # Получим несколько первых записей
                        result = await session.execute(text(f"SELECT * FROM {table_name} LIMIT 2;"))
                        rows = result.fetchall()
                        for i, row in enumerate(rows, 1):
                            print(f"  Запись {i}: ID={row[0] if len(row) > 0 else 'N/A'}")
                            
                except Exception as e:
                    print(f"Ошибка при чтении таблицы {table_name}: {e}")
    
    except Exception as e:
        print(f"Ошибка при подключении к базе данных: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_collected_data())