import asyncio
from src.core.logger import logger
from src.database.session import init_db

async def main():
    logger.info("Starting Fedresurs Pro...")
    await init_db()
    # Здесь будет запуск Ingestor Loop
    logger.info("System initialized.")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())