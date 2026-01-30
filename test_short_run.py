import asyncio
import logging
from src.orchestrator import orchestrator


# Настройка логирования для вывода в консоль
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_short_run():
    """
    Тестовый запуск оркестратора на короткое время для проверки сохранения данных
    """
    print("Запуск оркестратора на короткое время для проверки...")
    
    try:
        # Запуск оркестратора
        # Используем метод start_monitoring, который реализует основной цикл
        task = asyncio.create_task(orchestrator.start_monitoring())

        # Работаем 30 секунд, затем останавливаем
        print("Ожидание получения и сохранения данных...")
        await asyncio.sleep(30)

        print("Время истекло, останавливаем оркестратор...")
        task.cancel()

    except Exception as e:
        print(f"Ошибка в процессе работы: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.client.close()


if __name__ == "__main__":
    asyncio.run(test_short_run())