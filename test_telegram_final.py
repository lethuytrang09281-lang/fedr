import asyncio
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.abspath('.'))

from src.bot.notifier import TelegramNotifier

async def test():
    print("Запуск теста Telegram...")
    try:
        notifier = TelegramNotifier()
        await notifier.send_lot_alert({
            'guid': 'test-guid-sprint2',
            'description': '🚀 Спринт 2: Система уведомлений активирована! Тестовый лот в центре Москвы.',
            'start_price': 75000000,
            'location_zone': 'GARDEN_RING',
            'cadastral_numbers': ['77:01:0001001:123'],
            'semantic_tags': ['мкд', 'инвестиции'],
            'red_flags': [],
            'rosreestr_area': 2100,
        })
        print("✅ Уведомление успешно отправлено!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await notifier.close()

if __name__ == "__main__":
    asyncio.run(test())
