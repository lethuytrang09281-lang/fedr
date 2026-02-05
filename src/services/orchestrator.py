"""
Orchestrator для парсинга банкротных торгов Fedresurs.
Боевая версия с интеграцией реальных компонентов.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.core.logger import logger
from src.core.config import settings
from src.database.base import AsyncSessionLocal
from src.database.models import SystemState, Auction, Lot, LotStatus, MessageHistory
from src.api.client import FedresursClient
from src.services.xml_parser import XMLParserService
from src.services.ingestor import IngestionService
from src.services.zone_service import MoscowZoneService
from src.services.classifier import SemanticClassifier


class Orchestrator:
    """
    Главный координатор системы парсинга банкротных торгов.
    Интегрирует: FedresursClient, XMLParserService, IngestionService.
    """

    def __init__(self):
        self.is_running = False
        self.client = FedresursClient()
        self.xml_parser = XMLParserService()
        self.ingestor = IngestionService()
        self.chunk_size_days = 1  # Окно поиска (дней)
        logger.info("🔧 Orchestrator initialized with real components")

    async def get_last_processed_date(self, task_key: str, default_days_back: int = 1) -> datetime:
        """Получить последнюю обработанную дату из системного состояния."""
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

    async def update_state(self, task_key: str, new_date: datetime):
        """Обновить последнюю обработанную дату в системном состоянии."""
        async with AsyncSessionLocal() as session:
            stmt = insert(SystemState).values(
                task_key=task_key,
                last_processed_date=new_date
            ).on_conflict_do_update(
                index_elements=['task_key'],
                set_={'last_processed_date': new_date}
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"💾 Updated state for '{task_key}': {new_date}")

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
        Боевой цикл парсинга с интеграцией реальных компонентов.
        Использует FedresursClient для получения сообщений о торгах из API ЕФРСБ.
        """
        logger.info("🚀 Orchestrator: Starting REAL parsing cycle...")

        try:
            # 1. Определяем диапазон дат
            last_date = await self.get_last_processed_date("trade_monitor", default_days_back=1)
            now = datetime.now(timezone.utc)

            # Если отставание небольшое, просто ждем
            if now - last_date < timedelta(minutes=5):
                logger.info("💤 No new data expected yet. Sleeping...")
                return

            # Ограничиваем конец периода (макс. 31 день согласно API)
            end_date = min(last_date + timedelta(days=self.chunk_size_days), now)

            logger.info(f"📡 Fetching Fedresurs data: {last_date} -> {end_date}")

            # 2. Запрашиваем данные из API ЕФРСБ
            date_start = last_date.strftime('%Y-%m-%dT%H:%M:%S')
            date_end = end_date.strftime('%Y-%m-%dT%H:%M:%S')

            # Пагинация: обрабатываем по 50 записей за раз
            offset = 0
            limit = 50
            total_processed = 0

            async with AsyncSessionLocal() as session:
                while True:
                    # Получаем порцию сообщений
                    response = await self.client.get_trade_messages(
                        date_start=date_start,
                        date_end=date_end,
                        include_content=True,
                        limit=limit,
                        offset=offset
                    )

                    messages = response.get("pageData", [])
                    total = response.get("total", 0)

                    if not messages:
                        logger.info(f"✅ No more messages. Processed {total_processed} total.")
                        break

                    logger.info(f"📦 Processing batch: offset={offset}, count={len(messages)}, total={total}")

                    # Обрабатываем каждое сообщение
                    for msg in messages:
                        try:
                            await self._process_single_message(session, msg)
                            total_processed += 1
                        except Exception as e:
                            logger.error(f"❌ Error processing message {msg.get('guid')}: {e}")
                            continue

                    # Переходим к следующей странице
                    offset += limit

                    # Если обработали все - выходим
                    if offset >= total:
                        break

            # 3. Обновляем курсор
            await self.update_state("trade_monitor", end_date)
            logger.success(f"✅ Cycle complete! Processed {total_processed} messages. Cursor: {end_date}")

        except Exception as e:
            logger.error(f"❌ Orchestrator Critical Error: {e}", exc_info=True)
            await asyncio.sleep(10)  # Error backoff

    async def _process_single_message(self, session: AsyncSession, msg: dict):
        """
        Обработка конкретного сообщения о торге.
        Интегрирует XMLParserService и IngestionService.

        Структура входящего сообщения (из API):
        {
            "guid": "...",
            "number": "...",
            "type": "BiddingInvitation" | "Auction2" | "PublicOffer",
            "datePublish": "2025-02-20T12:30:01.767",
            "content": "<?xml version='1.0'?>...",
            "tradePlaceGuid": "...",
            "trade": {"number": "...", "guid": "..."}
        }
        """
        try:
            msg_guid = msg.get("guid")
            content_xml = msg.get("content")

            if not content_xml:
                logger.debug(f"⏭️  Message {msg_guid} has no XML content, skipping")
                return

            # Парсинг XML
            logger.debug(f"🔍 Parsing XML for message {msg_guid} (type: {msg.get('type')})")
            lots_data, price_schedules = self.xml_parser.parse_content(content_xml, msg_guid)

            if not lots_data:
                logger.debug(f"⏭️  No lots found in message {msg_guid}")
                return

            logger.info(f"📦 Found {len(lots_data)} lots in message {msg_guid}")

            # Извлекаем данные о торге
            trade_info = msg.get("trade", {})
            trade_number = trade_info.get("number") if trade_info else msg.get("number", "N/A")
            trade_guid = trade_info.get("guid") if trade_info else msg_guid

            # Подготовка DTO для Ingestor
            auction_dto = {
                "guid": trade_guid,
                "number": trade_number,
                "etp_id": msg.get("tradePlaceGuid", "N/A"),
                "organizer_inn": msg.get("organizerInn", "N/A")  # Может отсутствовать в ответе
            }

            # Парсим дату публикации
            date_publish = msg.get("datePublish")
            if date_publish:
                try:
                    # Убираем миллисекунды если есть: "2025-02-20T12:30:01.767"
                    date_publish = datetime.fromisoformat(date_publish.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    date_publish = datetime.now(timezone.utc)
            else:
                date_publish = datetime.now(timezone.utc)

            message_dto = {
                "guid": msg_guid,
                "type": msg.get("type", "TradeMessage"),
                "date_publish": date_publish,
                "content_xml": content_xml
            }

            # Преобразуем распарсенные лоты в формат для Ingestor + классификация
            lots_dicts = []
            for lot_data in lots_data:
                # 1. Определяем гео-зону по кадастровым номерам
                cadastral_numbers = lot_data.cadastral_numbers or []
                location_zone = MoscowZoneService.determine_zone(cadastral_numbers)

                # 2. Семантическая классификация (целевые теги, мусор, красные флаги)
                classification = SemanticClassifier.classify(
                    description=lot_data.description,
                    category_code=lot_data.classifier_code
                )

                lots_dicts.append({
                    "lot_number": getattr(lot_data, "lot_number", 1),
                    "description": lot_data.description,
                    "start_price": lot_data.start_price,
                    "category_code": lot_data.classifier_code,
                    "cadastral_numbers": cadastral_numbers,
                    "status": "Active",
                    # Новые поля классификации (Sprint 1)
                    "location_zone": location_zone,
                    "is_relevant": classification.is_relevant,
                    "semantic_tags": classification.semantic_tags,
                    "red_flags": classification.red_flags,
                    "needs_enrichment": len(cadastral_numbers) > 0,  # Если есть кадастры - можно обогатить
                })

            # Сохранение в БД через Ingestor
            await self.ingestor.save_parsed_data(session, auction_dto, lots_dicts, message_dto)
            logger.success(f"✅ Successfully processed message {msg_guid} with {len(lots_dicts)} lots")

        except Exception as e:
            logger.error(f"❌ Message processing error {msg.get('guid')}: {e}", exc_info=True)

    async def start_monitoring(self):
        """
        Основной цикл мониторинга торгов.
        Запускает периодический парсинг каждые 60 секунд.
        """
        self.is_running = True
        logger.info("🚀 Orchestrator monitoring started")

        # Проверяем конфигурацию
        if not settings.EFRSB_BASE_URL:
            logger.warning("⚠️  EFRSB_BASE_URL not configured")
        else:
            logger.info(f"📡 Using EFRSB API: {settings.EFRSB_BASE_URL}")

        try:
            iteration = 0
            while self.is_running:
                iteration += 1
                logger.info(f"🔄 Parsing cycle #{iteration} started...")

                try:
                    await self.run_parsing_cycle()
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


# Singleton instance
orchestrator = Orchestrator()

# Алиас класса для разных вариантов импорта
FedresursOrchestrator = Orchestrator
