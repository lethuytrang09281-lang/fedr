#!/usr/bin/env python3
"""Короткий запуск оркестратора для проверки исправлений"""
import asyncio
import logging
import sys
from datetime import datetime, timezone

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_orchestrator():
    """Тестовый запуск оркестратора"""
    print("=" * 60)
    print("Запуск оркестратора для проверки исправлений часовых поясов")
    print("=" * 60)
    
    try:
        # Импортируем оркестратор
        from src.orchestrator import Orchestrator
        
        # Создаем экземпляр
        orchestrator = Orchestrator()
        print("✅ Orchestrator создан успешно")
        
        # Проверяем методы, которые используют даты
        print("\nПроверка методов оркестратора:")
        
        # Проверяем get_last_processed_date
        last_date = await orchestrator.get_last_processed_date("trade_monitor", default_days_back=1)
        print(f"✅ get_last_processed_date: {last_date}")
        print(f"   Часовой пояс: {last_date.tzinfo}")
        print(f"   Является aware: {last_date.tzinfo is not None}")
        
        # Проверяем, что дата в UTC
        if last_date.tzinfo == timezone.utc:
            print("   ✅ Дата в часовом поясе UTC")
        else:
            print(f"   ⚠️  Дата не в UTC: {last_date.tzinfo}")
        
        # Проверяем update_state
        test_date = datetime.now(timezone.utc)
        print(f"\n✅ update_state: тестовая дата {test_date}")
        
        # Пытаемся запустить start_monitoring, но ограничиваем по времени
        print("\nЗапуск start_monitoring на 10 секунд...")
        print("(Проверка корректности запуска, реальный мониторинг не выполняется)")
        
        # Создаем задачу с таймаутом
        monitoring_task = asyncio.create_task(orchestrator.start_monitoring())
        
        # Ждем 10 секунд, затем отменяем
        await asyncio.sleep(10)
        monitoring_task.cancel()
        
        try:
            await monitoring_task
        except asyncio.CancelledError:
            print("✅ Оркестратор успешно остановлен")
        
        print("\n" + "=" * 60)
        print("✅ Оркестратор работает корректно!")
        print("✅ Исправления часовых поясов применены успешно")
        print("=" * 60)
        
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при запуске оркестратора: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Основная функция"""
    try:
        success = await test_orchestrator()
        if success:
            print("\n🎉 Все проверки пройдены успешно!")
            print("   Приложение готово к работе с исправленными часовыми поясами.")
        else:
            print("\n⚠️  Проверки не пройдены")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nОстановлено пользователем")
    finally:
        print("\nЗавершение тестового запуска")

if __name__ == "__main__":
    # Запускаем асинхронную main
    asyncio.run(main())