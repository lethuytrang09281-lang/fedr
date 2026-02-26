# src/services/hunter/strategies/hidden_gem.py

"""
Hidden Gem Strategy - Стратегия "Мутного лота"

Цель: Найти ценные активы с плохим маркетингом
Логика: Управляющий поленился → описание плохое → конкуренция низкая → цена упадёт

Признаки Hidden Gem:
1. Короткое описание (<300 символов)
2. Нет фото/документов
3. Нет упоминаний коммуникаций (газ, вода, электричество)
4. Нет технических характеристик
5. НО: высокая рыночная стоимость (актив ценный!)

Парадокс: Плохое описание = Меньше конкурентов = Выгоднее цена
"""

import logging
import re
from typing import Optional, List
import asyncpg

logger = logging.getLogger(__name__)


class HiddenGemDetector:
    """
    Детектор скрытых алмазов
    
    Находит активы где:
    - Маркетинг плохой (короткое описание, нет деталей)
    - Но актив ценный (рыночная стоимость высокая, хорошая локация)
    """
    
    # Пороги для оценки
    SHORT_DESCRIPTION_THRESHOLD = 300  # символов
    MIN_MARKET_VALUE = 5_000_000       # 5 млн ₽
    
    # Ключевые слова которые ДОЛЖНЫ быть в хорошем описании
    EXPECTED_KEYWORDS = {
        # Коммуникации
        "коммуникации": ["газ", "вода", "электричество", "канализация", "отопление"],
        
        # Транспортная доступность
        "транспорт": ["метро", "остановка", "транспорт", "мкад", "минут пешком"],
        
        # Техническое состояние
        "состояние": ["ремонт", "состояние", "площадь", "этаж", "год постройки"],
        
        # Документы
        "документы": ["документы", "правоустанавливающ", "кадастровый паспорт"]
    }
    
    def __init__(self, db_pool: asyncpg.Pool, market_benchmark_service=None):
        self.db = db_pool
        self.market_service = market_benchmark_service
    
    async def detect_hidden_gems(
        self,
        min_market_value: float = MIN_MARKET_VALUE,
        limit: int = 50
    ) -> List[dict]:
        """
        Поиск Hidden Gems в базе
        
        Args:
            min_market_value: Минимальная рыночная стоимость
            limit: Максимум результатов
            
        Returns:
            Список найденных скрытых алмазов
        """
        
        # Запрос: Лоты с коротким описанием + высокая цена
        lots = await self.db.fetch("""
            SELECT 
                l.*,
                mb.median_price_per_sqm as market_price_per_sqm
            FROM lots l
            LEFT JOIN market_benchmarks mb ON mb.cadastral_quarter = l.district
            WHERE 
                l.description_length < $1
                AND l.start_price >= $2
                AND l.stage IN ('Auction', 'PublicOffer')
            ORDER BY l.start_price DESC
            LIMIT $3
        """, self.SHORT_DESCRIPTION_THRESHOLD, min_market_value, limit)
        
        hidden_gems = []
        
        for lot in lots:
            lot_dict = dict(lot)
            
            # Расчёт Hidden Gem Score
            gem_score = self.calculate_gem_score(
                description=lot_dict["description"],
                description_length=lot_dict["description_length"],
                market_value=lot_dict.get("market_price_per_sqm", 0) * lot_dict.get("area", 0),
                has_photos=bool(lot_dict.get("photos")),
                has_documents=bool(lot_dict.get("documents"))
            )
            
            if gem_score >= 30:  # Порог для Hidden Gem
                lot_dict["gem_score"] = gem_score
                lot_dict["gem_factors"] = self._explain_gem_score(lot_dict)
                hidden_gems.append(lot_dict)
                
                logger.info(
                    f"💎 Hidden Gem: Лот {lot_dict['id']} "
                    f"(score: {gem_score}, район: {lot_dict['district']})"
                )
        
        return hidden_gems
    
    def calculate_gem_score(
        self,
        description: str,
        description_length: int,
        market_value: float,
        has_photos: bool = False,
        has_documents: bool = False
    ) -> int:
        """
        Рассчитать Hidden Gem Score [0-100]
        
        Логика: Чем хуже описание + выше ценность = больше скор
        
        Args:
            description: Текст описания
            description_length: Длина описания
            market_value: Рыночная стоимость
            has_photos: Есть ли фото
            has_documents: Есть ли документы
            
        Returns:
            gem_score [0-100]
        """
        
        score = 0
        
        # === ФАКТОР 1: Короткое описание ===
        if description_length < 200:
            score += 30
        elif description_length < 300:
            score += 20
        elif description_length < 500:
            score += 10
        
        # === ФАКТОР 2: Отсутствие фото ===
        if not has_photos:
            score += 20
        
        # === ФАКТОР 3: Отсутствие ключевых слов ===
        desc_lower = description.lower()
        
        # Нет упоминаний коммуникаций
        has_communications = any(
            word in desc_lower 
            for word in self.EXPECTED_KEYWORDS["коммуникации"]
        )
        if not has_communications:
            score += 15
        
        # Нет упоминаний транспорта
        has_transport = any(
            word in desc_lower 
            for word in self.EXPECTED_KEYWORDS["транспорт"]
        )
        if not has_transport:
            score += 10
        
        # Нет технических характеристик
        has_specs = any(
            word in desc_lower 
            for word in self.EXPECTED_KEYWORDS["состояние"]
        )
        if not has_specs:
            score += 10
        
        # === ФАКТОР 4: Высокая рыночная стоимость ===
        if market_value >= 50_000_000:  # 50 млн+
            score += 15
        elif market_value >= 20_000_000:  # 20 млн+
            score += 10
        elif market_value >= 10_000_000:  # 10 млн+
            score += 5
        
        # === ФАКТОР 5: Отсутствие документов ===
        if not has_documents:
            score += 5
        
        return min(100, score)
    
    def _explain_gem_score(self, lot: dict) -> List[str]:
        """
        Объяснить почему это Hidden Gem
        
        Returns:
            Список причин
        """
        
        reasons = []
        desc_lower = lot["description"].lower()
        
        if lot["description_length"] < 200:
            reasons.append(f"📝 Очень короткое описание ({lot['description_length']} символов)")
        elif lot["description_length"] < 300:
            reasons.append(f"📝 Короткое описание ({lot['description_length']} символов)")
        
        if not lot.get("photos"):
            reasons.append("📷 Нет фотографий")
        
        # Проверка на отсутствие ключевых слов
        missing_categories = []
        for category, keywords in self.EXPECTED_KEYWORDS.items():
            if not any(word in desc_lower for word in keywords):
                missing_categories.append(category)
        
        if missing_categories:
            reasons.append(f"❌ Не упомянуты: {', '.join(missing_categories)}")
        
        if lot.get("start_price", 0) >= 10_000_000:
            reasons.append(f"💰 Высокая стоимость ({lot['start_price']:,.0f} ₽)")
        
        reasons.append("🎯 Низкая конкуренция из-за плохого маркетинга")
        
        return reasons
    
    async def enrich_with_external_data(self, lot_id: int) -> dict:
        """
        Обогатить Hidden Gem данными из внешних источников
        
        Если управляющий плохо описал лот, мы сами найдём данные:
        - Кадастровая карта (характеристики участка)
        - Яндекс.Карты (транспортная доступность)
        - Росреестр (документы)
        
        Args:
            lot_id: ID лота
            
        Returns:
            Обогащённые данные
        """
        
        lot = await self.db.fetchrow("""
            SELECT * FROM lots WHERE id = $1
        """, lot_id)
        
        if not lot:
            raise ValueError(f"Лот {lot_id} не найден")
        
        enriched = dict(lot)
        
        # 1. Кадастровые данные (из нашей базы 584K записей)
        if lot["cadastral_numbers"]:
            cadastral_info = await self.db.fetch("""
                SELECT * FROM cadastral_index
                WHERE cad_num = ANY($1::text[])
            """, lot["cadastral_numbers"])
            
            enriched["cadastral_details"] = [dict(c) for c in cadastral_info]
        
        # 2. TODO: Геокодинг через Moscow API
        # if lot["address"]:
        #     coords = await moscow_api.geocode(lot["address"])
        #     enriched["coordinates"] = coords
        
        # 3. TODO: Транспортная доступность
        # if coords:
        #     metro = await moscow_api.nearest_metro(coords)
        #     enriched["nearest_metro"] = metro
        
        return enriched
    
    @staticmethod
    def generate_marketing_description(enriched_data: dict) -> str:
        """
        Генерация "правильного" описания для Hidden Gem
        
        Используем собранные данные чтобы создать то описание,
        которое ДОЛЖЕН БЫЛ написать управляющий
        
        Args:
            enriched_data: Обогащённые данные лота
            
        Returns:
            Улучшенное описание
        """
        
        parts = []
        
        # Базовая информация
        if enriched_data.get("area"):
            parts.append(f"Площадь: {enriched_data['area']} м²")
        
        # Кадастровые данные
        if enriched_data.get("cadastral_details"):
            cad = enriched_data["cadastral_details"][0]
            if cad.get("address"):
                parts.append(f"Адрес: {cad['address']}")
            if cad.get("layer_name"):
                parts.append(f"Назначение: {cad['layer_name']}")
        
        # Локация
        if enriched_data.get("district"):
            parts.append(f"Район: {enriched_data['district']}")
        
        if enriched_data.get("nearest_metro"):
            metro = enriched_data["nearest_metro"]
            parts.append(f"Метро: {metro['name']} ({metro['distance']} м)")
        
        # Стоимость
        if enriched_data.get("start_price"):
            parts.append(f"Начальная цена: {enriched_data['start_price']:,.0f} ₽")
        
        if enriched_data.get("market_price_per_sqm") and enriched_data.get("area"):
            market_value = enriched_data["market_price_per_sqm"] * enriched_data["area"]
            discount = ((enriched_data["start_price"] - market_value) / market_value) * 100
            parts.append(f"Рыночная цена: ~{market_value:,.0f} ₽ (дисконт {abs(discount):.1f}%)")
        
        description = "\n".join(parts)
        
        return f"""
🔍 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ (собрана автоматически):

{description}

⚠️ Примечание: Оригинальное описание от управляющего неполное. 
Данные собраны из открытых источников для вашего удобства.
        """.strip()
