import asyncio
import aiohttp
import logging
import json
import os
import glob
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.services.xml_parser import XMLParserService
from src.services.ingestor import IngestionService
from src.services.enricher import RosreestrEnricher
from src.services.external_api import ParserAPIClient
from src.services.fedresurs_search import FedresursSearch
from src.services.checko_client import CheckoAPIClient
from src.bot.notifier import TelegramNotifier
from src.logic.price_calculator import PriceCalculator
from src.logic.scorer import DealScorer
from src.database.base import get_db_session
from src.database.models import SystemState, Lot, Auction, Lead
from src.config import Settings
from src.utils.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.settings = Settings()
        # 🔄 Используем Parser API вместо прямого клиента Fedresurs
        self.parser_api = ParserAPIClient()
        self.xml_parser = XMLParserService()
        self.ingestor = IngestionService()
        self.price_calculator = PriceCalculator()
        self.enricher = RosreestrEnricher()
        self.notifier = TelegramNotifier()
        # Нарезаем запросы по 1 дню для надежности
        self.chunk_size_days = 1

        self.checko = CheckoAPIClient()
        self.scorer = DealScorer()

        # 🔍 Resource Monitor
        self.resource_monitor = ResourceMonitor(
            cpu_threshold=80.0,      # Throttle при CPU > 80%
            cpu_critical=150.0,      # Critical при CPU > 150%
            ram_threshold=85.0,      # Throttle при RAM > 85%
            ram_critical=95.0,       # Critical при RAM > 95%
            check_interval=5         # Проверка каждые 5 секунд
        ) 

    async def get_last_processed_date(self, task_key: str, default_days_back: int = 30) -> datetime:
        """
        Возвращает дату последнего парсинга. Гарантированно возвращает aware-datetime (UTC).
        """
        default_date = datetime.now(timezone.utc) - timedelta(days=default_days_back)

        try:
            session_count = 0
            result_date = None  # Сохраняем результат чтобы вернуть его ПОСЛЕ finally

            async for session in get_db_session():
                session_count += 1
                try:
                    stmt = select(SystemState.last_processed_date).where(SystemState.task_key == task_key)
                    result = await session.execute(stmt)
                    db_date = result.scalar_one_or_none()

                    if db_date:
                        # Если база вернула дату без зоны (naive), принудительно ставим UTC
                        if db_date.tzinfo is None:
                            db_date = db_date.replace(tzinfo=timezone.utc)
                        result_date = db_date
                    else:
                        result_date = default_date

                except Exception as e:
                    logger.error(f"Failed to get state: {e}", exc_info=True)
                    result_date = default_date
                finally:
                    await session.close()
                    break

            # Если получили результат из БД, возвращаем его
            if result_date is not None:
                return result_date

            if session_count == 0:
                logger.error(f"❌ get_db_session() yielded {session_count} sessions (expected 1+)")

        except Exception as e:
            logger.error(f"Failed to get DB session: {e}", exc_info=True)
            return default_date

        # Если цикл не выполнился (не должно происходить), возвращаем default
        logger.warning(f"⚠️ get_db_session() did not yield! Returning default_date={default_date}")
        return default_date

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

    async def _check_api_limits(self) -> dict:
        """Проверяет остаток лимитов parser-api.com"""
        url = f"https://parser-api.com/stat/?key={self.settings.PARSER_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                # API возвращает список, преобразуем в словарь {service: {...}}
                if isinstance(data, list):
                    return {item['service']: item for item in data}
                return data

    def _seconds_until_midnight(self) -> int:
        """Секунд до полуночи UTC"""
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight += timedelta(days=1)
        return int((midnight - now).total_seconds())

    RAW_LOTS_DIR = "/app/data/raw_lots"

    def _save_lots_to_disk(self, lots: list) -> str:
        """Сохраняет сырые лоты на диск до записи в БД. Возвращает путь к файлу."""
        os.makedirs(self.RAW_LOTS_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.RAW_LOTS_DIR, f"{ts}_lots.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "source": "fedresurs",
                "lots": lots
            }, f, ensure_ascii=False, default=str)
        logger.info(f"💾 Лоты сохранены на диск: {path} ({len(lots)} шт.)")
        return path

    async def _process_pending_lots_from_disk(self):
        """При старте подхватывает необработанные файлы (без .done маркера)."""
        if not os.path.isdir(self.RAW_LOTS_DIR):
            return
        pending = sorted([
            f for f in glob.glob(os.path.join(self.RAW_LOTS_DIR, "*_lots.json"))
            if not os.path.exists(f + ".done")
        ])
        if not pending:
            return
        logger.info(f"🔄 Найдено {len(pending)} необработанных файлов лотов, восстанавливаю...")
        for json_path in pending:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lots = data.get("lots", [])
                logger.info(f"  → {os.path.basename(json_path)}: {len(lots)} лотов")
                async for session in get_db_session():
                    try:
                        saved = 0
                        for lot in lots:
                            if await self._save_lot_to_db(session, lot):
                                saved += 1
                        logger.info(f"  ✅ Восстановлено {saved}/{len(lots)} лотов из {os.path.basename(json_path)}")
                        open(json_path + ".done", "w").close()  # маркер
                    except Exception as e:
                        logger.error(f"  ❌ Ошибка восстановления {json_path}: {e}", exc_info=True)
                    finally:
                        await session.close()
                        break
            except Exception as e:
                logger.error(f"  ❌ Не удалось прочитать {json_path}: {e}", exc_info=True)

    async def run_search(self):
        """Запуск поиска лотов через FedresursSearch"""
        # 🔍 Проверка ресурсов перед поиском
        await self.resource_monitor.wait_if_needed()

        # 🛡️ Проверка лимита API
        try:
            stats = await self._check_api_limits()
            fedresurs = stats.get('fedresurs', {})
            day_limit = fedresurs.get('day_limit', 250)
            day_used = fedresurs.get('day_request_count', 0)
            day_left = day_limit - day_used

            logger.info(f"📊 Fedresurs лимит: {day_used}/{day_limit} использовано, осталось {day_left}")

            if day_left <= 10:
                wait = self._seconds_until_midnight()
                logger.warning(f"⚠️ Лимит почти исчерпан ({day_left} запросов). Пауза {wait//3600}ч {(wait%3600)//60}м до обновления.")
                await asyncio.sleep(wait)
                return
        except Exception as e:
            logger.error(f"❌ Не удалось проверить лимиты: {e}", exc_info=True)
            # Продолжаем — лучше работать чем стоять из-за ошибки stat

        logger.info("🔍 Запуск поиска лотов через FedresursSearch...")

        # 🔄 Используем FedresursSearch для поиска лотов
        try:
            # Окно поиска: 6 месяцев назад (фиксированное, не зависит от last_processed)
            # last_processed используется только для обновления state в БД
            await self.get_last_processed_date("trade_monitor", default_days_back=180)
            published_after = datetime.now(timezone.utc) - timedelta(days=180)

            search = FedresursSearch(
                api_key=self.settings.PARSER_API_KEY,
                resource_monitor=self.resource_monitor
            )
            result = await search.search_lots(published_after=published_after)
            await search.close()

            lots = result.get("lots", []) if isinstance(result, dict) else result
            leads = result.get("leads", []) if isinstance(result, dict) else []

            if lots:
                logger.info(f"✅ Найдено {len(lots)} лотов, сохраняю на диск и в БД...")

                # 1. Сохраняем на диск ДО записи в БД
                disk_path = self._save_lots_to_disk(lots)

                # 2. Записываем в БД
                saved_pairs = []  # [(lot_dict, lot_id), ...]
                async for session in get_db_session():
                    try:
                        for lot in lots:
                            lot_id = await self._save_lot_to_db(session, lot)
                            if lot_id is not None:
                                saved_pairs.append((lot, lot_id))

                        logger.info(f"✅ Сохранено {len(saved_pairs)}/{len(lots)} лотов в БД")

                        # 3. Ставим .done только если есть успешные записи
                        if saved_pairs:
                            open(disk_path + ".done", "w").close()
                    finally:
                        await session.close()
                        break

                # 4. Скоринг и Telegram уведомления
                for lot, lot_id in saved_pairs:
                    await self._score_and_notify_lot(lot, lot_id)
            else:
                logger.info("ℹ️ Лоты не найдены")

            # 5. Сохраняем лиды (ранний захват)
            if leads:
                logger.info(f"🌱 Найдено {len(leads)} лидов, сохраняю...")
                saved_leads = 0
                async for session in get_db_session():
                    try:
                        for lead in leads:
                            if await self._save_lead_to_db(session, lead):
                                saved_leads += 1
                        logger.info(f"✅ Сохранено {saved_leads}/{len(leads)} лидов в БД")
                    finally:
                        await session.close()
                        break
            else:
                logger.info("ℹ️ Лиды не найдены")

        except Exception as e:
            # Обработка ошибок FedresursSearch - оркестратор продолжает работу, не падает
            logger.error(f"❌ FedresursSearch Error: {e}", exc_info=True)
            logger.info("⚠️ Оркестратор продолжает работу несмотря на ошибку")

        finally:
            # ⚠️ ВАЖНО: Обновляем состояние ВСЕГДА (даже при ошибке), чтобы не было бесконечной петли
            await self.update_state("trade_monitor", datetime.now(timezone.utc))

    def _classify_lot(self, description: str, cadastral_numbers: list) -> dict:
        """
        Классификация лота: релевантность и зона
        """
        description_lower = description.lower()

        # Релевантность (Target vs Trash)
        target_keywords = ["мкд", "ж-зона", "гпзу", "многоквартирн", "жилая застройка"]
        trash_keywords = ["снт", "лпх", "дача", "огород", "садовый"]

        is_relevant = any(kw in description_lower for kw in target_keywords)
        if any(kw in description_lower for kw in trash_keywords):
            is_relevant = False

        # Определение зоны (Упрощенно)
        # В реальности здесь должен быть ГИС-поиск или база кадастров
        location_zone = "OUTSIDE"
        if cadastral_numbers:
            # Например, 77:01 - это ЦАО (примерно Садовое Кольцо)
            # 77:02, 03... - ТТК и прочее
            cn = cadastral_numbers[0]
            if cn.startswith("77:01:"):
                location_zone = "GARDEN_RING"
            elif cn.startswith("77:"):
                location_zone = "TTK"

        # Семантические теги
        semantic_tags = []
        if "мкд" in description_lower or "многоквартирн" in description_lower:
            semantic_tags.append("мкд")
        if "участок" in description_lower:
            semantic_tags.append("земельный участок")

        return {
            "is_relevant": is_relevant,
            "location_zone": location_zone,
            "semantic_tags": semantic_tags,
            "red_flags": [] # Можно добавить логику поиска рисков
        }

    async def _get_or_create_auction(self, session, lot: dict) -> UUID:
        """Создает или получает auction по message_id"""
        message_id = lot.get('message_id', '')

        # Генерируем UUID из message_id (детерминированно)
        # Используем namespace UUID для fedresurs
        namespace = UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # стандартный namespace
        auction_guid = uuid4()  # или можно использовать uuid5(namespace, message_id)

        # Проверяем, существует ли auction с таким number
        stmt = select(Auction).where(Auction.number == lot.get('message_num'))
        result = await session.execute(stmt)
        existing_auction = result.scalar_one_or_none()

        if existing_auction:
            return existing_auction.guid

        # Создаем новый auction
        auction = Auction(
            guid=auction_guid,
            number=lot.get('message_num'),
            etp_id=message_id,
            organizer_inn=lot.get('debtor_inn'),
            last_updated=datetime.now(timezone.utc)
        )

        session.add(auction)
        await session.flush()  # Чтобы получить guid

        logger.debug(f"Создан auction {auction_guid} для message {message_id}")
        return auction_guid

    async def _save_lot_to_db(self, session, lot: dict) -> int | None:
        """
        Сохраняет лот в таблицу lots.
        Возвращает id лота при успехе, None при ошибке или дубле.
        """
        try:
            # Получаем или создаем auction
            auction_id = await self._get_or_create_auction(session, lot)

            lot_num = int(lot.get('lot_num', 1))

            # INSERT ON CONFLICT DO NOTHING — атомарно, без гонок и ошибок на дублях
            stmt = insert(Lot).values(
                guid=uuid4(),
                auction_id=auction_id,
                lot_number=lot_num,
                description=lot.get('description', ''),
                start_price=lot.get('start_price', 0),
                category_code=lot.get('lot_type', ''),
                cadastral_numbers=[],
                status='Announced',
                is_relevant=True,
                location_zone=None,
                semantic_tags=[],
                red_flags=[],
                is_restricted=False,
                needs_enrichment=True,
                # Данные должника
                debtor_name=lot.get('debtor_name'),
                debtor_inn=lot.get('debtor_inn'),
                debtor_ogrn=lot.get('debtor_ogrn'),
                debtor_address=lot.get('debtor_address'),
                # Дело и управляющий
                case_num=lot.get('case_num'),
                manager_name=lot.get('manager_name'),
                # Параметры торгов
                trade_type=lot.get('trade_type'),
                trade_app_start=lot.get('trade_app_start'),
                trade_app_end=lot.get('trade_app_end'),
                trade_place=lot.get('trade_place'),
                step=lot.get('step'),
                deposit=lot.get('deposit'),
                # Ссылка на сообщение
                message_id=lot.get('message_id'),
                message_num=lot.get('message_num'),
            ).on_conflict_do_nothing(
                index_elements=['auction_id', 'lot_number']
            ).returning(Lot.id)

            result = await session.execute(stmt)
            await session.commit()

            lot_id = result.scalar_one_or_none()
            if lot_id is None:
                logger.debug(f"⏭️ Лот #{lot_num} уже в БД, пропускаем")
                return None

            logger.info(
                f"💾 Сохранен лот #{lot_num} | "
                f"{lot.get('debtor_name', '')[:40]} | "
                f"{lot.get('start_price', 0):,.0f} ₽"
            )
            return lot_id

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лота в БД: {e}", exc_info=True)
            await session.rollback()
            return None

    async def _save_lead_to_db(self, session, lead: dict) -> bool:
        """
        Сохраняет лид в таблицу leads.
        Возвращает True при успехе, False при дубле или ошибке.
        """
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(Lead).values(
                debtor_guid=lead.get("debtor_guid"),
                debtor_name=lead.get("debtor_name"),
                debtor_inn=lead.get("debtor_inn"),
                message_type=lead.get("message_type"),
                description=lead.get("description"),
                address=lead.get("address"),
                estimated_value=lead.get("estimated_value"),
                source_message_id=lead.get("source_message_id"),
                published_at=lead.get("published_at"),
                status="new",
            ).on_conflict_do_nothing(index_elements=["source_message_id"])

            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount == 0:
                logger.debug(f"⏭️ Лид {lead.get('source_message_id')} уже в БД")
                return False

            logger.info(
                f"🌱 Сохранён лид | {lead.get('debtor_name', '')[:40]} | "
                f"type={lead.get('message_type')} | {lead.get('description', '')[:50]}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лида: {e}", exc_info=True)
            await session.rollback()
            return False

    async def _score_and_notify_lot(self, lot: dict, lot_id: int):
        """
        Считает deal_score, сохраняет в БД и отправляет Telegram при score >= 80.
        """
        try:
            # Получаем антифрод-флаги из Checko (если есть ИНН)
            antifraud_flags = []
            debtor_inn = lot.get('debtor_inn')
            if debtor_inn:
                flags = await self.checko.get_antifraud_flags(debtor_inn)
                if flags:
                    antifraud_flags = flags

            # Считаем скоринг
            result = self.scorer.calculate(lot, antifraud_flags)
            deal_score = result['deal_score']

            # Обновляем запись в БД
            async for session in get_db_session():
                try:
                    from sqlalchemy import update
                    await session.execute(
                        update(Lot).where(Lot.id == lot_id).values(deal_score=deal_score)
                    )
                    await session.commit()
                finally:
                    await session.close()
                    break

            logger.info(
                f"📊 Скоринг лота #{lot.get('lot_num')}: "
                f"deal={deal_score} inv={result['investment_score']} fraud={result['fraud_score']} "
                f"[{result['label']}]"
            )

            # Telegram уведомление для HOT DEAL (>= 80)
            if deal_score >= 80:
                alert_lot = {**lot, 'deal_score': deal_score, **result['breakdown']}
                await self.notifier.send_lot_alert(alert_lot)
                logger.info(f"🔥 HOT DEAL отправлен в Telegram: лот #{lot.get('lot_num')} score={deal_score}")

        except Exception as e:
            logger.error(f"❌ Ошибка скоринга лота {lot_id}: {e}", exc_info=True)

    async def start_monitoring(self):
        logger.info("🦅 Starting Fedresurs Monitoring Service...")

        # 🔍 Запуск Resource Monitor
        await self.resource_monitor.start()

        # 🔄 Восстановление необработанных лотов с диска
        await self._process_pending_lots_from_disk()

        try:
            while True:
                try:
                    # Проверяем когда последний раз запускали поиск
                    last_processed = await self.get_last_processed_date("trade_monitor", default_days_back=0)
                    now = datetime.now(timezone.utc)
                    logger.info(f"🔍 DEBUG: last_processed={last_processed}, type={type(last_processed).__name__}")

                    if last_processed is None:
                        # Первый запуск
                        logger.info("🆕 Первый запуск, начинаю поиск...")
                        await self.run_search()
                    elif now - last_processed < timedelta(hours=6):
                        # Запускаем поиск каждые 6 часов
                        sleep_seconds = int((timedelta(hours=6) - (now - last_processed)).total_seconds())
                        logger.info(f"💤 Следующий поиск через {sleep_seconds // 60} минут...")
                        await asyncio.sleep(max(1, min(sleep_seconds, 900)))  # Проверяем каждые 15 минут, минимум 1с
                        continue
                    else:
                        logger.info("⏰ Время для нового поиска")
                        await self.run_search()

                except Exception as e:
                    logger.error(f"❌ Critical Orchestrator Error: {e}", exc_info=True)
                    logger.info("⏳ Перезапуск через 60 секунд...")
                    await asyncio.sleep(60)

        finally:
            # 🛑 Остановка Resource Monitor при завершении
            await self.resource_monitor.stop()


# Глобальный экземпляр оркестратора для удобства
orchestrator = Orchestrator()