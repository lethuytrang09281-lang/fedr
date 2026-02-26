# src/services/hunter/strategies/public_offer.py

"""
Public Offer Tracker - Стратегия "Падальщика"

Цель: Поймать лот на самой низкой цене (публичное предложение)
Логика: График снижения цены → прогноз "дна" → алерт за 2-3 дня

Механика публичного предложения:
- После неудачных торгов лот переходит в "Публичное предложение"
- Цена снижается каждые 7-10 дней (обычно на 10-20%)
- Минимум = 50% от начальной цены
- Покупатель может купить по текущей цене без конкурентов

Наша задача: Войти когда цена упала до ~60-70% от начальной (sweet spot)
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import asyncpg

logger = logging.getLogger(__name__)


class PublicOfferTracker:
    """
    Трекер публичных предложений
    
    Отслеживает:
    - График снижения цены
    - Прогнозирует дату достижения минимума
    - Рассчитывает оптимальную точку входа
    - Алертит за 2-3 дня до sweet spot
    """
    
    # Константы
    MIN_PRICE_PERCENT = 50  # Минимум = 50% от начальной
    SWEET_SPOT_PERCENT = 65  # Оптимальная точка входа = 65%
    ALERT_DAYS_BEFORE = 3    # Алерт за 3 дня
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
    
    async def track_public_offers(
        self,
        min_start_price: float = 5_000_000,
        limit: int = 50
    ) -> List[dict]:
        """
        Получить активные публичные предложения
        
        Args:
            min_start_price: Минимальная начальная цена
            limit: Максимум результатов
            
        Returns:
            Список лотов с прогнозом
        """
        
        # Лоты на стадии PublicOffer
        lots = await self.db.fetch("""
            SELECT 
                l.*,
                COUNT(ps.id) as periods_count,
                MIN(ps.price) as current_min_price,
                MAX(ps.price) as initial_price
            FROM lots l
            LEFT JOIN price_schedules ps ON ps.lot_id = l.id
            WHERE 
                l.stage = 'PublicOffer'
                AND l.start_price >= $1
            GROUP BY l.id
            HAVING COUNT(ps.id) > 0
            ORDER BY l.start_price DESC
            LIMIT $2
        """, min_start_price, limit)
        
        tracked_offers = []
        
        for lot in lots:
            lot_dict = dict(lot)
            
            # Получить полный график снижения
            price_schedule = await self._get_price_schedule(lot_dict["id"])
            
            # Прогноз
            prediction = self.predict_bottom(
                price_schedule=price_schedule,
                initial_price=lot_dict["initial_price"]
            )
            
            # Sweet spot анализ
            sweet_spot_info = self.calculate_sweet_spot(
                current_price=lot_dict["current_min_price"],
                initial_price=lot_dict["initial_price"],
                price_schedule=price_schedule
            )
            
            lot_dict["prediction"] = prediction
            lot_dict["sweet_spot"] = sweet_spot_info
            lot_dict["price_schedule"] = price_schedule
            
            # Алерт если близко к sweet spot
            if sweet_spot_info["alert"]:
                logger.warning(
                    f"⏰ PUBLIC OFFER ALERT: Лот {lot_dict['id']} "
                    f"достигнет sweet spot через {sweet_spot_info['days_to_sweet_spot']} дней!"
                )
            
            tracked_offers.append(lot_dict)
        
        return tracked_offers
    
    async def _get_price_schedule(self, lot_id: int) -> List[dict]:
        """
        Получить график снижения цены
        
        Returns:
            Список периодов с ценами и датами
        """
        
        schedule = await self.db.fetch("""
            SELECT 
                period_number,
                price,
                date_start,
                date_end
            FROM price_schedules
            WHERE lot_id = $1
            ORDER BY period_number ASC
        """, lot_id)
        
        return [dict(s) for s in schedule]
    
    def predict_bottom(
        self,
        price_schedule: List[dict],
        initial_price: float
    ) -> dict:
        """
        Прогноз достижения минимальной цены
        
        Args:
            price_schedule: График снижения
            initial_price: Начальная цена
            
        Returns:
            {
                "bottom_price": float,
                "predicted_bottom_date": datetime,
                "days_until_bottom": int,
                "current_discount_percent": float
            }
        """
        
        if not price_schedule:
            return {
                "bottom_price": None,
                "predicted_bottom_date": None,
                "days_until_bottom": None,
                "current_discount_percent": 0
            }
        
        # Минимальная цена = 50% от начальной (по закону)
        bottom_price = initial_price * (self.MIN_PRICE_PERCENT / 100)
        
        # Текущая цена (последний период)
        current_period = price_schedule[-1]
        current_price = current_period["price"]
        
        # Текущий дисконт
        current_discount = ((current_price - initial_price) / initial_price) * 100
        
        # Прогноз даты достижения минимума
        # Логика: Анализируем темп снижения
        if len(price_schedule) >= 2:
            # Средний темп снижения за период
            first_price = price_schedule[0]["price"]
            last_price = price_schedule[-1]["price"]
            periods_passed = len(price_schedule) - 1
            
            if periods_passed > 0:
                avg_drop_per_period = (first_price - last_price) / periods_passed
                
                # Сколько периодов до дна
                remaining_drop = current_price - bottom_price
                periods_to_bottom = remaining_drop / avg_drop_per_period if avg_drop_per_period > 0 else 0
                
                # Предполагаем 7 дней на период (стандарт)
                days_to_bottom = int(periods_to_bottom * 7)
                
                predicted_date = datetime.now() + timedelta(days=days_to_bottom)
            else:
                days_to_bottom = None
                predicted_date = None
        else:
            days_to_bottom = None
            predicted_date = None
        
        return {
            "bottom_price": bottom_price,
            "predicted_bottom_date": predicted_date,
            "days_until_bottom": days_to_bottom,
            "current_discount_percent": current_discount
        }
    
    def calculate_sweet_spot(
        self,
        current_price: float,
        initial_price: float,
        price_schedule: List[dict]
    ) -> dict:
        """
        Рассчитать оптимальную точку входа (sweet spot)
        
        Sweet spot = ~65% от начальной цены
        Логика: 
        - Ниже 70% = уже хорошая скидка
        - Выше 60% = не рискуем упустить (кто-то может купить)
        
        Returns:
            {
                "sweet_spot_price": float,
                "days_to_sweet_spot": int,
                "alert": bool,  # True если близко к sweet spot
                "recommendation": str
            }
        """
        
        sweet_spot_price = initial_price * (self.SWEET_SPOT_PERCENT / 100)
        
        # Текущий процент от начальной
        current_percent = (current_price / initial_price) * 100
        
        # Сколько дней до sweet spot
        if len(price_schedule) >= 2 and current_price > sweet_spot_price:
            # Темп снижения (₽/день)
            first_date = price_schedule[0]["date_start"]
            last_date = price_schedule[-1]["date_end"]
            days_passed = (last_date - first_date).days
            
            if days_passed > 0:
                drop_rate = (price_schedule[0]["price"] - current_price) / days_passed
                
                remaining_drop = current_price - sweet_spot_price
                days_to_sweet_spot = int(remaining_drop / drop_rate) if drop_rate > 0 else None
            else:
                days_to_sweet_spot = None
        else:
            days_to_sweet_spot = 0 if current_price <= sweet_spot_price else None
        
        # Алерт если близко
        alert = False
        recommendation = ""
        
        if current_price <= sweet_spot_price:
            alert = True
            recommendation = "🔥 ПОКУПАТЬ СЕЙЧАС! Достигнут sweet spot"
        elif days_to_sweet_spot and days_to_sweet_spot <= self.ALERT_DAYS_BEFORE:
            alert = True
            recommendation = f"⏰ ГОТОВИТЬСЯ! Sweet spot через {days_to_sweet_spot} дней"
        elif current_percent <= 75:
            recommendation = "✅ Хорошая цена, можно рассмотреть"
        elif current_percent <= 85:
            recommendation = "🤔 Подождать ещё немного"
        else:
            recommendation = "⏳ Рано, цена ещё высокая"
        
        return {
            "sweet_spot_price": sweet_spot_price,
            "days_to_sweet_spot": days_to_sweet_spot,
            "alert": alert,
            "recommendation": recommendation,
            "current_percent_of_initial": current_percent
        }
    
    async def get_price_drop_velocity(self, lot_id: int) -> dict:
        """
        Анализ скорости падения цены
        
        Полезно для определения: падает ли цена быстрее/медленнее обычного
        
        Returns:
            {
                "avg_drop_per_period": float,
                "avg_drop_percent": float,
                "is_fast_drop": bool,  # Падает быстрее обычного
                "is_slow_drop": bool   # Падает медленнее обычного
            }
        """
        
        schedule = await self._get_price_schedule(lot_id)
        
        if len(schedule) < 2:
            return {
                "avg_drop_per_period": 0,
                "avg_drop_percent": 0,
                "is_fast_drop": False,
                "is_slow_drop": False
            }
        
        # Расчёт среднего снижения
        drops = []
        for i in range(1, len(schedule)):
            prev_price = schedule[i-1]["price"]
            curr_price = schedule[i]["price"]
            drop = prev_price - curr_price
            drop_percent = (drop / prev_price) * 100
            drops.append({"abs": drop, "percent": drop_percent})
        
        avg_drop_abs = sum(d["abs"] for d in drops) / len(drops)
        avg_drop_percent = sum(d["percent"] for d in drops) / len(drops)
        
        # Классификация
        # Обычное падение: 10-20% за период
        is_fast_drop = avg_drop_percent > 25  # Быстрее обычного
        is_slow_drop = avg_drop_percent < 8   # Медленнее обычного
        
        return {
            "avg_drop_per_period": avg_drop_abs,
            "avg_drop_percent": avg_drop_percent,
            "is_fast_drop": is_fast_drop,
            "is_slow_drop": is_slow_drop
        }
    
    async def create_price_alert(
        self,
        lot_id: int,
        target_price: float,
        alert_method: str = "telegram"
    ) -> int:
        """
        Создать алерт на достижение целевой цены
        
        Args:
            lot_id: ID лота
            target_price: Целевая цена
            alert_method: Способ уведомления (telegram/email)
            
        Returns:
            ID созданного алерта
        """
        
        # TODO: Создать таблицу price_alerts
        alert_id = await self.db.fetchval("""
            INSERT INTO price_alerts (
                lot_id,
                target_price,
                alert_method,
                is_active,
                created_at
            ) VALUES ($1, $2, $3, TRUE, NOW())
            RETURNING id
        """, lot_id, target_price, alert_method)
        
        logger.info(
            f"Created price alert: lot_id={lot_id}, "
            f"target={target_price:,.0f}, method={alert_method}"
        )
        
        return alert_id
    
    async def check_price_alerts(self) -> List[dict]:
        """
        Проверить активные алерты
        
        Запускается периодически (например, каждый час)
        Проверяет: упала ли цена до целевого значения
        
        Returns:
            Список сработавших алертов
        """
        
        # TODO: Реализовать после создания таблицы price_alerts
        triggered_alerts = []
        
        return triggered_alerts
