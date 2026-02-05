"""
Семантический классификатор для определения релевантности лотов.

Определяет:
1. is_relevant - подходит ли лот под критерии (коммерческая недвижимость)
2. semantic_tags - список тегов (земельный_участок, офис, etc.)
3. red_flags - список красных флагов (обременения, ОКН, etc.)
4. score - итоговый скор релевантности (0-100)
"""

import re
from dataclasses import dataclass
from typing import List


# Целевые ключевые слова (коммерческая недвижимость)
TARGET_KEYWORDS = {
    # Земля
    "земельный_участок": ["земельный участок", "земельные участки", "зу ", "зем. участок"],
    "мкд": ["многоквартирный дом", "жилой дом", "мкд"],
    "офисный_центр": ["офисное здание", "офисный центр", "бизнес-центр", "бц"],
    "торговая_недвижимость": ["торговый центр", "тц", "магазин", "торговое помещение"],
    "производство": ["производственное здание", "цех", "склад", "ангар"],
    "гостиница": ["гостиница", "отель", "хостел"],
    "апартаменты": ["апартаменты", "апарт-отель"],
}

# Мусорные ключевые слова (НЕ интересно)
TRASH_KEYWORDS = {
    "снт": ["снт", "садовое товарищество", "дачный участок", "сад"],
    "гараж": ["гараж", "машиноместо", "парковочное место"],
    "доля_в_праве": ["доля в праве", "1/2 доля", "1/3 доля", "долевая собственность"],
    "квартира": ["квартира", "комната"],
    "жилое_помещение": ["жилое помещение"],
    "транспорт": ["автомобиль", "машина", "транспортное средство", "авто"],
    "оборудование": ["оборудование", "станок", "инструмент"],
}

# Красные флаги (риски)
RED_FLAG_KEYWORDS = {
    "окн": ["объект культурного наследия", "окн", "памятник архитектуры", "выявленный объект"],
    "обременение": ["обременение", "залог", "ипотека", "арест"],
    "аварийное": ["аварийное состояние", "ветхое", "под снос"],
    "незавершенка": ["незавершенное строительство", "объект незавершенного"],
    "приказ_5": ["приказ №5", "приказ № 5", "приказ n5", "приказ no5"],
}


@dataclass
class ClassificationResult:
    """Результат классификации лота"""
    is_relevant: bool           # Подходит ли лот под критерии
    semantic_tags: List[str]    # Список тегов
    red_flags: List[str]        # Список красных флагов
    score: int                  # Скор релевантности 0-100


class SemanticClassifier:
    """YARA-подобный классификатор на основе ключевых слов"""

    @classmethod
    def classify(cls, description: str, category_code: str = "") -> ClassificationResult:
        """
        Классифицирует лот на основе описания и категории.

        Args:
            description: Текстовое описание лота
            category_code: Код категории из классификатора

        Returns:
            ClassificationResult с результатами классификации
        """
        if not description:
            return ClassificationResult(
                is_relevant=False,
                semantic_tags=[],
                red_flags=[],
                score=0
            )

        # Приводим к нижнему регистру для поиска
        text_lower = description.lower()
        category_lower = category_code.lower() if category_code else ""

        # 1. Поиск семантических тегов
        tags = []
        for tag_name, keywords in TARGET_KEYWORDS.items():
            if cls._contains_keywords(text_lower, keywords):
                tags.append(tag_name)

        # 2. Поиск мусорных ключевых слов
        trash_matches = []
        for trash_name, keywords in TRASH_KEYWORDS.items():
            if cls._contains_keywords(text_lower, keywords):
                trash_matches.append(trash_name)

        # 3. Поиск красных флагов
        red_flags = []
        for flag_name, keywords in RED_FLAG_KEYWORDS.items():
            if cls._contains_keywords(text_lower, keywords) or \
               cls._contains_keywords(category_lower, keywords):
                red_flags.append(flag_name)

        # 4. Определение релевантности
        # Релевантно если есть хотя бы один целевой тег И нет мусорных
        is_relevant = len(tags) > 0 and len(trash_matches) == 0

        # 5. Вычисление скора
        score = cls._calculate_score(tags, trash_matches, red_flags)

        return ClassificationResult(
            is_relevant=is_relevant,
            semantic_tags=tags,
            red_flags=red_flags,
            score=score
        )

    @staticmethod
    def _contains_keywords(text: str, keywords: List[str]) -> bool:
        """Проверяет наличие хотя бы одного ключевого слова в тексте"""
        for keyword in keywords:
            # Ищем как отдельное слово или с границами
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _calculate_score(tags: List[str], trash: List[str], red_flags: List[str]) -> int:
        """
        Вычисляет скор релевантности (0-100).

        Логика:
        - Каждый целевой тег: +20 баллов
        - Каждое мусорное слово: -30 баллов
        - Каждый красный флаг: -10 баллов
        """
        score = 0

        # Плюсы за целевые теги
        score += len(tags) * 20

        # Минусы за мусор
        score -= len(trash) * 30

        # Минусы за красные флаги
        score -= len(red_flags) * 10

        # Ограничиваем диапазон 0-100
        return max(0, min(100, score))

    @classmethod
    def is_high_value(cls, tags: List[str], zone: str) -> bool:
        """
        Определяет, является ли лот высокоценным.

        Критерии:
        - Коммерческая недвижимость (офис, мкд, торговля)
        - В зонах GARDEN_RING или TTK
        """
        high_value_tags = {"мкд", "офисный_центр", "торговая_недвижимость", "гостиница"}
        high_value_zones = {"GARDEN_RING", "TTK"}

        has_valuable_tag = any(tag in high_value_tags for tag in tags)
        in_valuable_zone = zone in high_value_zones

        return has_valuable_tag and in_valuable_zone