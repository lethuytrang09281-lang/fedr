

 APIJSON (https://devtrends.ru/java/tencent-apijson) 
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text, MetaData
from sqlalchemy.orm import sessionmaker
from src.config import settings
from src.database.models import Auction, Lot, MessageHistory, Base


async def view_collected_data():
    """
    Просмотр собранных данных из SQLite базы
    """
    print("Просмотр собранных данных из fedresurs.db")

    # Создаем асинхронный движок с тем же URL, что и в приложении
    engine = create_async_engine(settings.database_url)

    try:
        # Создаем все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Проверим, какие таблицы существуют
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.fetchall()
            print(f"Найденные таблицы: {[table[0] for table in tables]}")

        # Создаем сессию
        SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            # Подсчитаем количество записей в каждой таблице
            for model, table_name in [(Auction, 'auctions'), (Lot, 'lots'), (MessageHistory, 'messages')]:
                try:
                    count = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count_result = count.fetchone()[0]
                    print(f"\n--- Таблица {table_name} ---")
                    print(f"Всего записей: {count_result}")

                    if count_result > 0:
                        # Получим несколько первых записей
                        result = await session.execute(text(f"SELECT * FROM {table_name} LIMIT 3;"))
                        rows = result.fetchall()
                        for i, row in enumerate(rows, 1):
                            print(f"  Запись {i}: {row}")

                except Exception as e:
                    print(f"Ошибка при чтении таблицы {table_name}: {e}")

    except Exception as e:
        print(f"Ошибка при подключении к базе данных: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(view_collected_data())