import asyncio
import signal
import sys
from src.orchestrator import orchestrator


async def main():
    """
    Краткосрочный запуск оркестратора для получения данных
    """
    try:
        print("Запуск Fedresurs Radar Orchestrator на короткое время...")
        
        # Запуск оркестратора
        await orchestrator.start()
        
        # Работаем 30 секунд, затем останавливаем
        await asyncio.sleep(30)
        
        print("Время истекло, останавливаем оркестратор...")
        
    except KeyboardInterrupt:
        print("Остановка orchestrator по сигналу пользователя...")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())