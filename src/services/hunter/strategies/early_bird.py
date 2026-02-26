# src/services/hunter/strategies/early_bird.py

"""
Early Bird Strategy - Стратегия "Снайпера"

Цель: Обнаружить актив на стадии Инвентаризации/Оценки (за 3-6 месяцев до торгов)
Преимущество: Фора перед конкурентами, время на due diligence

Стадии мониторинга:
1. InventoryResult (Инвентаризация) - самая ранняя стадия
2. AppraiserReport (Оценка) - стадия оценки имущества
3. (Ожидание 3-6 месяцев)
4. BiddingInvitation (Объявление торгов) - уже поздно для конкурентов
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
import asyncpg

from ..models import HuntingOpportunity

logger = logging.getLogger(__name__)


class EarlyBirdStrategy:
    """
    Стратегия раннего обнаружения активов
    
    Мониторит:
    - /v1/messages (не trade-messages!) с типами InventoryResult, AppraiserReport
    - Фильтрует по целевым активам (земля, МКД)
    - Добавляет в Watchlist с прогнозом даты торгов
    """
    
    # Целевые коды классификаторов ОКОФ
    TARGET_CADASTRAL_TYPES = [
        "0108001",  # Земли населённых пунктов
        "002003",   # Многоквартирные дома
        "002001",   # Жилые здания
    ]
    
    # Целевые районы (приоритет)
    PRIORITY_DISTRICTS = [
        "Хамовники", "Арбат", "Пресненский", "Тверской",
        "Басманный", "Таганский", "Замоскворечье"
    ]
    
    def __init__(self, db_pool: asyncpg.Pool, client=None, parser=None):
        self.db = db_pool
        self.client = client  # EfrsbClient для запросов
        self.parser = parser  # XMLParserService для парсинга
    
    async def monitor_inventories(
        self,
        date_start: datetime,
        date_end: datetime,
        limit: int = 100
    ) -> List[dict]:
        """
        Мониторинг инвентаризаций и оценок
        
        Args:
            date_start: Начало периода
            date_end: Конец периода
            limit: Максимум сообщений
            
        Returns:
            Список найденных возможностей
        """
        
        if not self.client:
            raise ValueError("EfrsbClient not initialized")
        
        opportunities = []
        
        try:
            # Запрос к /v1/messages (НЕ trade-messages!)
            # Тип сообщения: InventoryResult или AppraiserReport
            messages = await self.client.get_messages(
                date_start=date_start.isoformat(),
                date_end=date_end.isoformat(),
                message_types=["InventoryResult", "AppraiserReport"],
                limit=limit
            )
            
            for msg in messages.get("items", []):
                # Парсим XML
                if not self.parser:
                    logger.warning("Parser not initialized, skipping")
                    continue
                
                parsed = self.parser.parse_inventory(msg.get("content", ""))
                
                # Фильтр: целевые активы
                if not self._is_target_asset(parsed):
                    continue
                
                # Фильтр: приоритетные районы (опционально)
                district = parsed.get("district", "")
                is_priority = district in self.PRIORITY_DISTRICTS
                
                # Прогноз даты торгов
                estimated_auction_date = self._estimate_auction_date(
                    msg.get("datePublish")
                )
                
                # Добавляем в Watchlist
                watchlist_id = await self._add_to_watchlist(
                    parsed=parsed,
                    message_guid=msg.get("guid"),
                    stage=msg.get("type"),
                    estimated_auction_date=estimated_auction_date
                )
                
                opportunity = {
                    "watchlist_id": watchlist_id,
                    "message_guid": msg.get("guid"),
                    "stage": msg.get("type"),
                    "district": district,
                    "is_priority": is_priority,
                    "cadastral_numbers": parsed.get("cadastral_numbers", []),
                    "estimated_auction_date": estimated_auction_date,
                    "discovered_at": datetime.now()
                }
                
                opportunities.append(opportunity)
                
                logger.info(
                    f"🎯 Early Bird: Found asset in {district} "
                    f"(stage: {msg.get('type')}, auction ~{estimated_auction_date})"
                )
        
        except Exception as e:
            logger.error(f"Early Bird monitoring error: {e}", exc_info=True)
        
        return opportunities
    
    def _is_target_asset(self, parsed: dict) -> bool:
        """
        Проверка: является ли актив целевым
        
        Целевые активы:
        - Земля под застройку (ИЖС, МКД)
        - Многоквартирные дома
        - Жилые здания в приоритетных районах
        """
        
        # Проверка по коду классификатора
        cadastral_type = parsed.get("cadastral_type", "")
        if any(target in cadastral_type for target in self.TARGET_CADASTRAL_TYPES):
            return True
        
        # Проверка по описанию (ключевые слова)
        description = parsed.get("description", "").lower()
        
        # Земля
        if "земельный участок" in description:
            if any(word in description for word in ["ижс", "под застройку", "мкд"]):
                return True
        
        # МКД
        if any(word in description for word in ["мкд", "многоквартирн", "жилой дом"]):
            return True
        
        return False
    
    @staticmethod
    def _estimate_auction_date(publish_date: str) -> datetime:
        """
        Прогноз даты торгов
        
        Логика:
        - Инвентаризация → Торги через 4-6 месяцев
        - Оценка → Торги через 2-4 месяца
        """
        
        try:
            pub_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        except:
            pub_date = datetime.now()
        
        # Консервативный прогноз: +5 месяцев
        estimated = pub_date + timedelta(days=150)
        return estimated
    
    async def _add_to_watchlist(
        self,
        parsed: dict,
        message_guid: str,
        stage: str,
        estimated_auction_date: datetime
    ) -> int:
        """
        Добавить актив в Watchlist
        
        Returns:
            ID записи в watchlist
        """
        
        # Создаём "виртуальный" лот для инвентаризации
        # (реальный лот появится позже, на стадии торгов)
        
        async with self.db.acquire() as conn:
            # Проверяем: есть ли уже в БД
            existing_lot = await conn.fetchrow("""
                SELECT id FROM lots
                WHERE cadastral_numbers && $1::text[]
                LIMIT 1
            """, parsed.get("cadastral_numbers", []))
            
            lot_id = None
            
            if existing_lot:
                lot_id = existing_lot["id"]
            else:
                # Создаём placeholder лот
                lot_id = await conn.fetchval("""
                    INSERT INTO lots (
                        description,
                        district,
                        cadastral_numbers,
                        stage,
                        created_at
                    ) VALUES ($1, $2, $3, $4, NOW())
                    RETURNING id
                """, 
                    parsed.get("description", "")[:1000],
                    parsed.get("district", ""),
                    parsed.get("cadastral_numbers", []),
                    stage
                )
            
            # Добавляем в watchlist
            watchlist_id = await conn.fetchval("""
                INSERT INTO watchlist (
                    lot_id,
                    stage,
                    discovered_at,
                    estimated_auction_date,
                    investment_score,
                    notes,
                    is_active
                ) VALUES ($1, $2, NOW(), $3, $4, $5, TRUE)
                ON CONFLICT (lot_id) DO UPDATE SET
                    stage = EXCLUDED.stage,
                    estimated_auction_date = EXCLUDED.estimated_auction_date,
                    investment_score = EXCLUDED.investment_score
                RETURNING id
            """,
                lot_id,
                stage,
                estimated_auction_date,
                50,  # Базовый investment_score для Early Bird
                f"Early Bird: обнаружено на стадии {stage}"
            )
            
            return watchlist_id
    
    async def get_watchlist_items(
        self,
        min_investment_score: int = 0,
        only_active: bool = True,
        limit: int = 100
    ) -> List[dict]:
        """
        Получить активные элементы Watchlist
        
        Args:
            min_investment_score: Минимальный скор
            only_active: Только активные (торги ещё не прошли)
            limit: Максимум записей
            
        Returns:
            Список элементов watchlist с деталями
        """
        
        query = """
            SELECT 
                w.*,
                l.district,
                l.cadastral_numbers,
                l.description,
                l.start_price,
                l.area
            FROM watchlist w
            JOIN lots l ON l.id = w.lot_id
            WHERE 
                w.investment_score >= $1
                AND ($2 = FALSE OR w.is_active = TRUE)
            ORDER BY w.investment_score DESC, w.discovered_at DESC
            LIMIT $3
        """
        
        items = await self.db.fetch(query, min_investment_score, only_active, limit)
        return [dict(item) for item in items]
    
    async def update_watchlist_progress(self, lot_id: int, new_stage: str):
        """
        Обновить прогресс лота в watchlist
        
        Вызывается когда лот переходит на новую стадию:
        InventoryResult → AppraiserReport → BiddingInvitation
        """
        
        await self.db.execute("""
            UPDATE watchlist
            SET 
                stage = $1,
                notes = notes || E'\n' || $2
            WHERE lot_id = $3
        """,
            new_stage,
            f"[{datetime.now()}] Переход на стадию {new_stage}",
            lot_id
        )
        
        logger.info(f"Watchlist: Лот {lot_id} перешёл на стадию {new_stage}")
    
    async def archive_completed_watchlist(self):
        """
        Архивировать завершённые лоты из Watchlist
        
        Лот считается завершённым если:
        - Прошла предполагаемая дата торгов + 1 месяц
        - Или лот перешёл в стадию "Результат торгов"
        """
        
        archived_count = await self.db.execute("""
            UPDATE watchlist
            SET is_active = FALSE
            WHERE 
                is_active = TRUE
                AND (
                    estimated_auction_date < NOW() - INTERVAL '30 days'
                    OR lot_id IN (
                        SELECT id FROM lots 
                        WHERE stage IN ('BiddingResult', 'BiddingFail', 'Cancelled')
                    )
                )
        """)
        
        if archived_count:
            logger.info(f"Archived {archived_count} completed watchlist items")
        
        return archived_count
