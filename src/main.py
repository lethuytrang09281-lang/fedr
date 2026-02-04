import asyncio
import logging
from src.core.logger import logger
from src.database.session import init_db
# Импорт сервиса парсинга (если есть)
# from src.services.parser import ParserService

async def main_loop():
    logger.info("🚀 Starting Fedresurs Pro Main Loop...")
    
    # --- 1. ЗАПУСК ПАРСИНГА СРАЗУ ПРИ СТАРТЕ ---
    logger.info("⚡ Immediate check started...")
    try:
        # Здесь вызов главной функции парсинга
        # Если у тебя класс Manager, то вызови его метод
        # await parser_service.run_once()
        # Пока временно отключено для отладки админ-панели
        logger.debug("Парсер временно отключен для отладки админ-панели")
        pass 
    except Exception as e:
        logger.error(f"Immediate check failed: {e}")
    # -------------------------------------------

    logger.info("⏳ Entering scheduler loop (Checking every N minutes)...")
    
    while True:
        try:
            # Здесь должна быть логика расписания
            # await parser_service.run_if_scheduled()
            
            # Лог пульса раз в минуту, чтобы видеть, что бот жив
            logger.debug("💓 System is alive. Waiting for next schedule...")
            pass
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")
        
        await asyncio.sleep(60) # Проверка раз в минуту

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("System stopped manually")

if __name__ == "__main__":
    main()
