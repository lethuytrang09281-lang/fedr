import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.client.api import EfrsbClient
from src.client.exceptions import EfrsbError
from src.services.xml_parser import XMLParserService
from src.services.ingestor import IngestionService
from src.logic.price_calculator import PriceCalculator
from src.database.base import get_db_session
from src.database.models import SystemState
from src.config import Settings

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.settings = Settings()
        self.client = EfrsbClient()
        self.xml_parser = XMLParserService()
        self.ingestor = IngestionService()
        self.price_calculator = PriceCalculator()
        # Нарезаем запросы по 1 дню для надежности
        self.chunk_size_days = 1 

    async def get_last_processed_date(self, task_key: str, default_days_back: int = 30) -> datetime:
        """
        Возвращает дату последнего парсинга. Гарантированно возвращает aware-datetime (UTC).
        """
        default_date = datetime.now(timezone.utc) - timedelta(days=default_days_back)
        
        async for session in get_db_session():
            try:
                stmt = select(SystemState.last_processed_date).where(SystemState.task_key == task_key)
                result = await session.execute(stmt)
                db_date = result.scalar_one_or_none()

                if db_date:
                    # Если база вернула дату без зоны (naive), принудительно ставим UTC
                    if db_date.tzinfo is None:
                        db_date = db_date.replace(tzinfo=timezone.utc)
                    return db_date

                return default_date
            except Exception as e:
                logger.error(f"Failed to get state: {e}")
                return default_date
            finally:
                await session.close()
                break

    async def update_state(self, task_key: str, new_date: datetime):
        """Сохраняет прогресс в БД"""
        async for session in get_db_session():
            try:
                stmt = insert(SystemState).values(
                    task_key=task_key,
                    last_processed_date=new_date
                ).on_conflict_do_update(
                    index_elements=['task_key'],
                    set_={'last_processed_date': new_date}
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"State updated: {task_key} -> {new_date}")
            except Exception as e:
                logger.error(f"Failed to update state: {e}")
            finally:
                await session.close()
                break

    async def run_sync_period(self, start_date: datetime, end_date: datetime):
        """Проходит по периоду чанками"""
        current_start = start_date
        
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=self.chunk_size_days), end_date)
            logger.info(f"Processing chunk: {current_start} -> {current_end}")
            
            offset = 0
            limit = 50
            
            while True:
                try:
                    response = await self.client.get_trade_messages(
                        date_start=current_start.strftime('%Y-%m-%d'),
                        date_end=current_end.strftime('%Y-%m-%d'),
                        offset=offset,
                        limit=limit
                    )
                    
                    messages = response.pageItems
                    total = response.total
                    
                    if not messages:
                        break
                        
                    async for session in get_db_session():
                        try:
                            for msg in messages:
                                await self._process_single_message(session, msg)
                        finally:
                            await session.close()
                            break

                    offset += limit
                    if offset >= total:
                        break
                    
                    await asyncio.sleep(0.2)

                except EfrsbError as e:
                    if "429" in str(e):
                        logger.warning("Rate limit (429). Sleeping 60s...")
                        await asyncio.sleep(60)
                        continue 
                    else:
                        logger.error(f"API Error: {e}")
                        raise e 

            await self.update_state("trade_monitor", current_end)
            current_start = current_end

    async def _process_single_message(self, session, msg: dict):
        """Обработка одного сообщения"""
        if msg.get("isAnnulled"):
            return

        msg_guid = msg.get("guid")
        content_xml = msg.get("content")
        
        # Надежный парсинг даты с приведением к UTC
        try:
            date_str = msg.get("datePublish")
            if date_str:
                # API иногда шлет 'Z', иногда '+03:00'. Приводим к ISO.
                date_str = date_str.replace('Z', '+00:00')
                date_pub = datetime.fromisoformat(date_str)
            else:
                date_pub = datetime.now(timezone.utc)
        except ValueError:
            date_pub = datetime.now(timezone.utc)

        if not content_xml:
            return

        # 1. Парсинг
        # Используем новый парсер, который возвращает кортеж (лоты, графики цен)
        from src.services.xml_parser import XMLParserService
        parser = XMLParserService()
        lots_data, price_schedules_data = parser.parse_content(content_xml, msg_guid)

        lots_dicts = []

        # --- ФИЛЬТР КЛЮЧЕВЫХ СЛОВ (ОТКЛЮЧЕН для отладки) ---
        # Чтобы сохранялись ВСЕ сообщения, блок ниже закомментирован.
        # Если захочешь включить фильтр - раскомментируй строки.

        # keywords = ["земельн", "участок", "мкд", "жилая", "застройка"]
        # found_keywords = False
        # full_text = (content_xml + " ".join([l.description for l in lots_data])).lower()
        # for kw in keywords:
        #     if kw in full_text:
        #         found_keywords = True
        #         break

        # if not found_keywords:
        #     return  # Пропускаем, если нет слов
        # ---------------------------------------------------

        for lot_data in lots_data:
            is_public = "PublicOffer" in (msg.get("type") or "") or hasattr(lot_data, 'price_reduction_html') and lot_data.price_reduction_html

            if is_public:
                current_price, schedules = self.price_calculator.calculate_current_price(
                    lot_data.price_reduction_html if hasattr(lot_data, 'price_reduction_html') else "",
                    lot_data.start_price
                )
                lot_data.start_price = current_price
                lot_data.price_schedules = schedules

            # Создаем словарь лота
            lot_dict = {
                'lot_number': getattr(lot_data, 'lot_number', 1),
                'description': lot_data.description,
                'start_price': lot_data.start_price,
                'category_code': lot_data.classifier_code,
                'cadastral_numbers': lot_data.cadastral_numbers,
                'status': getattr(lot_data, 'status', 'Announced')
            }

            if "BiddingResult" in str(msg.get("type")):
                lot_dict["status"] = "Sold"
            elif "BiddingFail" in str(msg.get("type")):
                lot_dict["status"] = "Failed"

            lots_dicts.append(lot_dict)

        # Подготовка DTO для аукциона
        auction_info = msg.get("trade", {})
        auction_dto = {
            "guid": msg_guid,  # Используем guid сообщения как guid аукциона
            "number": msg.get("number") or f"MSG_{msg_guid}",
            "etp_id": msg.get("etpName"),  # Используем правильное поле
            "organizer_inn": msg.get("organizerInn")  # Используем правильное поле
        }

        # Убедимся, что дата публикации имеет временную зону
        if date_pub.tzinfo is None:
            date_pub = date_pub.replace(tzinfo=timezone.utc)

        message_dto = {
            "guid": msg_guid,
            "type": msg.get("type"),
            "date_publish": date_pub.replace(tzinfo=None) if date_pub.tzinfo else date_pub,
            "content_xml": content_xml
        }

        # Сохраняем данные
        await self.ingestor.save_parsed_data(session, auction_dto, lots_dicts, message_dto)

    async def start_monitoring(self):
        logger.info("Starting Fedresurs Monitoring Service 🦅")
        while True:
            try:
                # Начинаем поиск с 30 дней назад
                last_processed = await self.get_last_processed_date("trade_monitor", default_days_back=30)
                now = datetime.now(timezone.utc)

                if last_processed is None:
                    # Если дата не найдена в базе, используем дату 30 дней назад
                    last_processed = now - timedelta(days=30)

                if now - last_processed < timedelta(minutes=15):
                    logger.info("All caught up. Sleep for 15 minutes... 💤")
                    await asyncio.sleep(900)
                    continue

                logger.info(f"Resuming sync from {last_processed}")
                await self.run_sync_period(last_processed, now)
                
            except Exception as e:
                logger.error(f"Critical Orchestrator Error: {e}", exc_info=True)
                logger.info("Restarting in 60s...")
                await asyncio.sleep(60)