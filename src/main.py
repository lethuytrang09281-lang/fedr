import asyncio
import sys
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.abspath('.'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.orchestrator import Orchestrator
from src.logic.price_calculator import PriceCalculator

# Импорт API routes (согласно INSTALLATION_GUIDE и QUICK_START)
from src.api import hunter_routes


# Глобальная переменная для оркестратора
orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan контекст для управления жизненным циклом приложения"""
    global orchestrator

    # Startup
    logging.info("🚀 Запуск Fedresurs Radar...")

    # 🎯 Запуск оркестратора с Resource Monitor
    orchestrator = Orchestrator()
    asyncio.create_task(run_orchestrator())
    logging.info("✅ Оркестратор запущен в фоновом режиме с Resource Monitor")

    yield

    # Shutdown
    logging.info("🛑 Остановка Fedresurs Radar...")
    # Orchestrator останавливается автоматически при завершении задачи


async def run_orchestrator():
    """Фоновая задача для оркестратора"""
    try:
        await orchestrator.start_monitoring()
    except Exception as e:
        logging.error(f"Ошибка в оркестраторе: {str(e)}")


# Создание FastAPI приложения
app = FastAPI(
    title="Fedresurs Radar API",
    description="API для Hunter Engine и анализа торгов",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров (согласно INSTALLATION_GUIDE)
app.include_router(hunter_routes.router)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "name": "Fedresurs Radar",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья приложения"""
    return {
        "status": "healthy",
        "orchestrator_running": orchestrator is not None
    }


# ВРЕМЕННО ОТКЛЮЧЕНО (пока нет Parser API ключа)
# async def main():
#     """
#     Главный цикл приложения Fedresurs Radar (режим CLI)
#     """
#     try:
#         print("Запуск Fedresurs Radar Orchestrator...")

#         # Создаем новый оркестратор
#         local_orchestrator = Orchestrator()

#         # Инициализация калькулятора цен
#         price_calculator = PriceCalculator()

#         # Запуск мониторинга
#         await local_orchestrator.start_monitoring()

#     except KeyboardInterrupt:
#         print("Остановка orchestrator по сигналу пользователя...")
#     except Exception as e:
#         logging.error(f"Ошибка в основном цикле: {str(e)}")


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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
