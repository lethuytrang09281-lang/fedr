"""
Orchestrator для парсинга банкротных торгов Fedresurs.
Координирует работу API клиента, парсера XML и сохранение в БД.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.core.config import settings
from src.database.session import AsyncSessionLocal
from src.database.models import SystemState, Auction, Lot, LotStatus
from src.api.client import FedresursClient


class Orchestrator:
    """
    Главный координатор системы парсинга.
    Безопасный режим: не крашит приложение при отсутствии API ключей.
    """

    def __init__(self):
        self.is_running = False
        self.client: Optional[FedresursClient] = None
        logger.info("🔧 Orchestrator initialized")

    async def get_last_processed_date(self, task_key: str, default_days_back: int = 7) -> datetime:
        """
        Получить последнюю обработанную дату из системного состояния.
        Если записи нет, вернуть дату N дней назад.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(SystemState).where(SystemState.task_key == task_key)
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()

            if state:
                logger.info(f"📅 Last processed date for '{task_key}': {state.last_processed_date}")
                return state.last_processed_date
            else:
                default_date = datetime.now(timezone.utc) - timedelta(days=default_days_back)
                logger.info(f"📅 No state found for '{task_key}', using default: {default_date}")
                return default_date

    async def save_last_processed_date(self, task_key: str, date: datetime):
        """Сохранить последнюю обработанную дату."""
        async with AsyncSessionLocal() as session:
            # Upsert логика
            stmt = select(SystemState).where(SystemState.task_key == task_key)
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()

            if state:
                state.last_processed_date = date
            else:
                state = SystemState(task_key=task_key, last_processed_date=date)
                session.add(state)

            await session.commit()
            logger.debug(f"💾 Saved state for '{task_key}': {date}")

    async def create_dummy_lot(self):
        """
        Создать тестовый лот для проверки работоспособности.
        Вызывается в режиме симуляции.
        """
        async with AsyncSessionLocal() as session:
            try:
                # Создаём тестовый аукцион
                auction_guid = uuid4()
                auction = Auction(
                    guid=auction_guid,
                    number=f"TEST-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
                    etp_id="Simulation",
                    organizer_inn="0000000000"
                )
                session.add(auction)
                await session.flush()

                # Создаём тестовый лот
                lot = Lot(
                    guid=uuid4(),
                    auction_id=auction_guid,
                    lot_number=1,
                    description="🧪 Тестовый лот для проверки работы системы (создан оркестратором)",
                    start_price=1000000.00,
                    category_code="0101014",
                    status=LotStatus.ANNOUNCED.value,
                    cadastral_numbers=["77:01:0001001:1234"],
                    is_restricted=False
                )
                session.add(lot)
                await session.commit()

                logger.info(f"✅ Created dummy lot: {lot.id} (Auction: {auction.number})")
                return lot.id
            except Exception as e:
                logger.error(f"❌ Error creating dummy lot: {e}")
                await session.rollback()
                return None

    async def run_parsing_cycle(self):
        """
        Одиночный цикл парсинга (для совместимости со старым кодом).
        """
        logger.info("🔄 Orchestrator: Starting single parsing cycle...")

        try:
            # В режиме симуляции создаём тестовый лот
            await self.create_dummy_lot()
            logger.info("✅ Parsing cycle completed (simulation)")
        except Exception as e:
            logger.error(f"❌ Error in parsing cycle: {e}", exc_info=True)

    async def start_monitoring(self):
        """
        Основной цикл мониторинга торгов.
        В безопасном режиме просто логирует и создаёт тестовые данные.
        """
        self.is_running = True
        logger.info("🚀 Orchestrator monitoring started (SIMULATION MODE)")

        # Проверяем наличие API ключей
        if not settings.CHECKO_API_KEY:
            logger.warning("⚠️  CHECKO_API_KEY not configured - running in SIMULATION MODE")

        try:
            self.client = FedresursClient()

            # Получаем последнюю обработанную дату
            last_date = await self.get_last_processed_date("trade_monitor", default_days_back=30)
            logger.info(f"📍 Starting from date: {last_date}")

            iteration = 0
            while self.is_running:
                iteration += 1
                logger.info(f"🔄 Parsing cycle #{iteration} started...")

                try:
                    # В режиме симуляции создаём тестовый лот раз в 5 минут
                    if iteration % 5 == 1:  # На первой итерации и каждые 5 циклов
                        await self.create_dummy_lot()

                    # Обновляем состояние системы
                    current_time = datetime.now(timezone.utc)
                    await self.save_last_processed_date("trade_monitor", current_time)

                    logger.info("✅ Parsing cycle completed (simulation)")

                except Exception as e:
                    logger.error(f"❌ Error in parsing cycle: {e}", exc_info=True)

                # Ждём 60 секунд до следующей итерации
                logger.debug("💤 Waiting 60 seconds before next cycle...")
                await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"❌ Critical error in orchestrator: {e}", exc_info=True)
        finally:
            await self.stop()

    async def start(self):
        """Алиас для start_monitoring для обратной совместимости."""
        await self.start_monitoring()

    async def stop(self):
        """Остановить мониторинг и закрыть соединения."""
        logger.info("🛑 Stopping orchestrator...")
        self.is_running = False

        if self.client:
            try:
                await self.client.close()
                logger.info("✅ Client connection closed")
            except Exception as e:
                logger.error(f"Error closing client: {e}")


# Singleton instance для обратной совместимости со старым кодом
orchestrator = Orchestrator()

# Алиас класса для разных вариантов импорта
FedresursOrchestrator = Orchestrator
