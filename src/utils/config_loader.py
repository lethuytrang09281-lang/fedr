"""
Config Loader - загрузка search_config.yaml
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class SearchConfig:
    """Класс для работы с конфигом поиска"""

    def __init__(self, config_path: str = "/root/fedr/search_config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Загрузить конфиг из YAML файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"✅ Конфиг загружен: {self.config_path}")
        except FileNotFoundError:
            logger.warning(f"⚠️ Конфиг не найден: {self.config_path}, используются значения по умолчанию")
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфига: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Значения по умолчанию если конфиг не найден"""
        return {
            "region": {"id": 77, "name": "Москва"},
            "filters": {
                "max_price": 300000000,
                "keywords": ["здание", "мкд", "офис", "нежилое помещение"]
            },
            "search": {
                "max_organizations": 100,
                "max_organizations_deep": 50,
                "request_delay": 3,
                "scan_interval_hours": 6
            },
            "scoring": {
                "hot_deal_threshold": 80,
                "good_deal_threshold": 60,
                "review_threshold": 40
            }
        }

    # Удобные геттеры
    @property
    def region_id(self) -> int:
        return self._config.get("region", {}).get("id", 77)

    @property
    def max_price(self) -> int:
        return self._config.get("filters", {}).get("max_price", 300000000)

    @property
    def keywords(self) -> List[str]:
        return self._config.get("filters", {}).get("keywords", ["здание", "мкд"])

    @property
    def max_organizations(self) -> int:
        return self._config.get("search", {}).get("max_organizations", 100)

    @property
    def max_organizations_deep(self) -> int:
        return self._config.get("search", {}).get("max_organizations_deep", 50)

    @property
    def request_delay(self) -> int:
        return self._config.get("search", {}).get("request_delay", 3)

    @property
    def scan_interval_hours(self) -> int:
        return self._config.get("search", {}).get("scan_interval_hours", 6)

    @property
    def hot_deal_threshold(self) -> int:
        return self._config.get("scoring", {}).get("hot_deal_threshold", 80)

    @property
    def good_deal_threshold(self) -> int:
        return self._config.get("scoring", {}).get("good_deal_threshold", 60)

    @property
    def fedresurs_daily_limit(self) -> int:
        return self._config.get("api_limits", {}).get("fedresurs", {}).get("daily", 250)

    @property
    def mock_mode(self) -> bool:
        return self._config.get("debug", {}).get("mock_mode", False)

    def get(self, key: str, default=None):
        """Получить любое значение из конфига"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value


# Глобальный экземпляр
search_config = SearchConfig()
