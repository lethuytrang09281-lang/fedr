"""
Сервис гео-зонирования для определения местоположения лота.

Приоритеты зон:
1. GARDEN_RING - Внутри Садового кольца (самый высокий приоритет)
2. TPU - Зоны транспортно-пересадочных узлов
3. TTK - Между Садовым и ТТК (весь ЦАО)
4. OUTSIDE - Всё остальное
"""

from typing import List
from src.database.models import LocationZone


class MoscowZoneService:
    """Определение зоны Москвы по кадастровому номеру"""

    # Кварталы внутри Садового кольца (77:01:0001xxx - 77:01:0004xxx)
    GARDEN_RING_PREFIXES = {
        "77:01:0001", "77:01:0002", "77:01:0003", "77:01:0004"
    }

    # Весь ЦАО (для ТТК)
    CAO_PREFIX = "77:01"

    # Список кварталов ТПУ (транспортно-пересадочные узлы)
    # TODO: Заполнить реальными кварталами около метро
    TPU_QUARTERS = {
        # Пример: "77:02:0012" — около метро в другом округе
        # Добавить сюда кадастровые кварталы около станций метро
    }

    @classmethod
    def determine_zone(cls, cadastral_numbers: List[str]) -> str:
        """
        Определяет зону с наивысшим приоритетом из списка кадастровых номеров.

        Args:
            cadastral_numbers: Список кадастровых номеров лота

        Returns:
            Код зоны (GARDEN_RING, TPU, TTK, OUTSIDE)
        """
        if not cadastral_numbers:
            return LocationZone.OUTSIDE.value

        for cn in cadastral_numbers:
            if not cn or not isinstance(cn, str):
                continue

            # Убираем пробелы и приводим к нижнему регистру для нормализации
            cn = cn.strip()

            # Проверяем только московские кадастры (77:)
            if not cn.startswith("77:"):
                continue

            parts = cn.split(":")
            if len(parts) < 3:
                continue

            # Формируем префикс квартала (77:01:0001)
            prefix = f"{parts[0]}:{parts[1]}:{parts[2]}"

            # Приоритет 1: Садовое кольцо
            if prefix in cls.GARDEN_RING_PREFIXES:
                return LocationZone.GARDEN_RING.value

            # Приоритет 2: ТПУ
            if prefix in cls.TPU_QUARTERS:
                return LocationZone.TPU.value

            # Приоритет 3: ТТК (остальной ЦАО)
            district_prefix = f"{parts[0]}:{parts[1]}"
            if district_prefix == cls.CAO_PREFIX:
                return LocationZone.TTK.value

        return LocationZone.OUTSIDE.value

    @classmethod
    def is_high_priority(cls, zone: str) -> bool:
        """Проверяет, является ли зона высокоприоритетной (Садовое или ТТК)"""
        return zone in [LocationZone.GARDEN_RING.value, LocationZone.TTK.value]

    @classmethod
    def get_priority_score(cls, zone: str) -> int:
        """
        Возвращает приоритет зоны (чем выше число, тем важнее зона).

        Returns:
            100 - GARDEN_RING
            80 - TPU
            60 - TTK
            0 - OUTSIDE
        """
        priority_map = {
            LocationZone.GARDEN_RING.value: 100,
            LocationZone.TPU.value: 80,
            LocationZone.TTK.value: 60,
            LocationZone.OUTSIDE.value: 0,
        }
        return priority_map.get(zone, 0)
