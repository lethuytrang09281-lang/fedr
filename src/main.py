import asyncio
import sys
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.abspath('.'))

from src.orchestrator import orchestrator


async def main():
    try:
        print("Запуск Fedresurs Radar Orchestrator...")
        await orchestrator.start()
    except KeyboardInterrupt:
        print("Остановка orchestrator по сигналу пользователя...")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())