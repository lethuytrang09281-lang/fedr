import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.client.api import EfrsbClient
from src.services.xml_parser import XMLParserService
from src.services.ingestor import IngestionService
from src.config import settings
from src.database.models import LotStatus
from src.schemas import AuctionDTO, LotDTO, MessageDTO


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Главный orchestrator для Fedresurs Radar.

    Отвечает за:
    1. Управление очередями задач
    2. Реализация "скользящего окна" для обхода лимита в 31 день
    3. Regex-фильтрация по ключевым словам (МКД, Земельные участки)
    4. Система логирования и обработка ошибок API (429, 502)
    5. Координация работы всех компонентов
    """

    def __init__(self):
        self.client = EfrsbClient()
        self.parser = XMLParserService()
        self.ingestor = IngestionService()
        self.engine = create_async_engine(settings.database_url)
        self.SessionLocal = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        # Regex-паттерны для фильтрации
        self.municipal_patterns = [
            re.compile(r'мкд', re.IGNORECASE),
            re.compile(r'многоквартирный дом', re.IGNORECASE),
            re.compile(r'жилой фонд', re.IGNORECASE),
            re.compile(r'жилое помещение', re.IGNORECASE),
            re.compile(r'дома на колесах', re.IGNORECASE),
        ]

        self.land_patterns = [
            re.compile(r'зем(ельный)?\s*участ(ок|ка)', re.IGNORECASE),
            re.compile(r'землепользование', re.IGNORECASE),
            re.compile(r'с/х угодья', re.IGNORECASE),
        ]

        # Очередь задач
        self.task_queue = asyncio.Queue()
        self.running = False

        # Executor для CPU-интенсивных задач (парсинг XML)
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def start(self):
        """Запуск orchestrator"""
        logger.info("Starting Fedresurs Radar Orchestrator...")
        self.running = True

        # Запуск обработчиков задач
        asyncio.create_task(self._process_tasks())

        # Запуск основного цикла
        await self._main_loop()

    async def stop(self):
        """Остановка orchestrator"""
        logger.info("Stopping Fedresurs Radar Orchestrator...")
        self.running = False
        await self.client.close()
        await self.engine.dispose()
        self.executor.shutdown(wait=True)

    async def _main_loop(self):
        """Основной цикл работы orchestrator"""
        while self.running:
            try:
                # Выполняем сканирование с "скользящим окном"
                await self._sliding_window_scan()

                # Ждем перед следующим циклом (например, 1 час)
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(60)  # Пауза перед повторной попыткой

    async def _sliding_window_scan(self):
        """
        Реализация "скользящего окна" для обхода лимита в 31 день.

        Вместо запроса за 31 день за раз, разбиваем на меньшие интервалы
        и выполняем последовательные запросы.
        """
        logger.info("Starting sliding window scan...")

        # Определяем диапазон для сканирования (например, последние 90 дней)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        # Шаг в 7 дней (меньше лимита в 31 день)
        step = timedelta(days=7)
        current_start = start_date

        while current_start < end_date and self.running:
            current_end = min(current_start + step, end_date)

            # Добавляем задачу в очередь
            task = {
                'type': 'scan_period',
                'start_date': current_start.strftime('%Y-%m-%d'),
                'end_date': current_end.strftime('%Y-%m-%d')
            }

            await self.task_queue.put(task)

            current_start = current_end

            # Небольшая задержка между задачами для соблюдения лимитов
            await asyncio.sleep(2)

    async def _process_tasks(self):
        """Обработка задач из очереди"""
        while self.running:
            try:
                task = await self.task_queue.get()

                if task['type'] == 'scan_period':
                    await self._process_scan_task(task)

                self.task_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing task {task}: {str(e)}")

    async def _process_scan_task(self, task: Dict[str, Any]):
        """Обработка задачи сканирования периода"""
        start_date = task['start_date']
        end_date = task['end_date']

        logger.info(f"Processing scan task for period {start_date} to {end_date}")

        try:
            # Получаем сообщения за период
            response = await self.client.search_messages(
                date_start=start_date,
                date_end=end_date,
                limit=500  # Максимальный лимит за один запрос
            )

            logger.info(f"Received {response.total} messages for period {start_date} to {end_date}")

            # Обрабатываем каждое сообщение
            for message in response.pageItems:
                await self._process_message(message)

        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(f"Rate limit exceeded for period {start_date} to {end_date}, retrying later")
                # Возвращаем задачу в очередь с задержкой
                await asyncio.sleep(60)
                await self.task_queue.put(task)
            elif "502" in str(e) or "bad gateway" in str(e).lower():
                logger.error(f"Bad Gateway error for period {start_date} to {end_date}, skipping")
            else:
                logger.error(f"Error processing scan task {start_date} to {end_date}: {str(e)}")

    async def _process_message(self, message):
        """Обработка отдельного сообщения"""
        try:
            # Проверяем, содержит ли сообщение ключевые слова
            if not self._matches_keywords(message.content):
                logger.debug(f"Message {message.guid} does not match keywords, skipping")
                return

            logger.info(f"Processing message {message.guid} with type {message.type}")

            # Парсим XML-контент
            lots_data = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.parser.parse_content,
                message.content,
                str(message.guid)
            )

            if not lots_data:
                logger.info(f"No lots found in message {message.guid}")
                return

            # Фильтруем лоты по ключевым словам
            filtered_lots = self._filter_lots_by_keywords(lots_data)

            if not filtered_lots:
                logger.info(f"No lots matched keywords in message {message.guid}")
                return

            # Подготовка DTO для сохранения
            auction_dto = {
                'guid': message.guid,
                'number': message.number or f"MSG_{message.guid}",
                'etp_id': getattr(message, 'etp_name', None),
                'organizer_inn': getattr(message, 'organizer_inn', None)
            }

            lots_dto = []
            for lot_data in filtered_lots:
                lot_dto = {
                    'lot_number': getattr(lot_data, 'lot_number', 1),
                    'description': lot_data.description,
                    'start_price': lot_data.start_price,
                    'category_code': lot_data.classifier_code,
                    'cadastral_numbers': lot_data.cadastral_numbers,
                    'status': LotStatus.ANNOUNCED.value,  # Используем .value для enum
                    'price_schedules': []  # Пока пустой, можно добавить из XML при необходимости
                }
                lots_dto.append(lot_dto)

            message_dto = {
                'guid': message.guid,
                'type': message.type,
                'date_publish': message.datePublish,
                'content_xml': message.content
            }

            # Сохраняем данные в БД
            async with self.SessionLocal() as session:
                await self.ingestor.save_parsed_data(
                    session=session,
                    auction_dto=auction_dto,
                    lots_dto=lots_dto,
                    message_dto=message_dto
                )

            logger.info(f"Successfully processed message {message.guid} with {len(filtered_lots)} lots")

        except Exception as e:
            logger.error(f"Error processing message {message.guid}: {str(e)}")

    def _matches_keywords(self, xml_content: str) -> bool:
        """
        Проверяет, содержит ли XML-контент ключевые слова (МКД, Земля и т.д.)
        """
        # Ищем в XML-контенте ключевые слова
        for pattern in self.municipal_patterns + self.land_patterns:
            if pattern.search(xml_content):
                return True
        return False

    def _filter_lots_by_keywords(self, lots_data) -> List[Any]:
        """
        Фильтрует лоты по ключевым словам
        """
        filtered_lots = []

        for lot_data in lots_data:
            # Проверяем описание лота на наличие ключевых слов
            description = lot_data.description.lower()

            # Проверяем на МКД
            for pattern in self.municipal_patterns:
                if pattern.search(description):
                    filtered_lots.append(lot_data)
                    break

            # Проверяем на землю
            for pattern in self.land_patterns:
                if pattern.search(description):
                    if lot_data not in filtered_lots:  # Избегаем дубликатов
                        filtered_lots.append(lot_data)
                    break

        return filtered_lots


# Глобальный экземпляр orchestrator для удобства
orchestrator = Orchestrator()