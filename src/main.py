import asyncio
import sys
import os
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.abspath('.'))

from src.orchestrator import orchestrator
from src.logic.price_calculator import PriceCalculator


async def main():
    """
    Главный цикл приложения Fedresurs Radar
    """
    try:
        print("Запуск Fedresurs Radar Orchestrator...")

        # Инициализация калькулятора цен
        price_calculator = PriceCalculator()

        # Запуск оркестратора
        await orchestrator.start()

    except KeyboardInterrupt:
        print("Остановка orchestrator по сигналу пользователя...")
    except Exception as e:
        logging.error(f"Ошибка в основном цикле: {str(e)}")
    finally:
        await orchestrator.stop()


def run_price_calculation_demo():
    """
    Демонстрация работы калькулятора цен
    """
    # Пример HTML-графика снижения цены
    sample_schedule_html = """
    <table class="schedule-table">
        <tr><th>Дата</th><th>Цена</th><th>Процент снижения</th></tr>
        <tr><td>01.02.2024</td><td>1000000.00</td><td>0%</td></tr>
        <tr><td>15.02.2024</td><td>950000.00</td><td>5%</td></tr>
        <tr><td>01.03.2024</td><td>900000.00</td><td>10%</td></tr>
    </table>
    """

    calculator = PriceCalculator()
    result = calculator.calculate_current_price(
        start_price=1000000.0,
        schedule_html=sample_schedule_html,
        start_date=datetime(2024, 1, 1)
    )

    print(f"Текущая цена: {result.current_price}")
    print(f"Статус графика: {result.schedule_status}")
    if result.next_reduction_date:
        print(f"Следующее снижение: {result.next_reduction_date}")


if __name__ == "__main__":
    # Запуск демонстрации (опционально)
    # run_price_calculation_demo()

    # Запуск основного цикла
    asyncio.run(main())