import asyncio
import logging
from datetime import datetime, timedelta, timezone
from src.orchestrator import FedresursOrchestrator


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    try:
        print("Запуск оркестратора на короткое время для проверки сохранения данных...")

        # Создаем экземпляр оркестратора
        orchestrator = FedresursOrchestrator()

        # Запускаем оркестратор
        await orchestrator.start_monitoring()

        # Работаем 30 секунд, затем останавливаем
        await asyncio.sleep(30)

        print("Время истекло, останавливаем оркестратор...")

    except KeyboardInterrupt:
        print("Оркестратор остановлен по сигналу пользователя...")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())