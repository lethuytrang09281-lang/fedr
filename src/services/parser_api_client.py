"""
Parser API Client для работы с parser-api.com
Документация: https://parser-api.com/bankrot-fedresurs-ru
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from aiolimiter import AsyncLimiter
import aiohttp
from src.config import settings

logger = logging.getLogger(__name__)


class ParserAPIClient:
    """Клиент для Parser API (fedresurs_api)"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.PARSER_API_KEY
        self.base_url = "https://parser-api.com/parser/fedresurs_api"
        self.limiter = AsyncLimiter(1, 1)  # 1 запрос в секунду (чтобы не превысить лимиты)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Базовый метод для запросов к Parser API"""
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"

        # Добавляем API ключ в параметры
        params["key"] = self.api_key

        async with self.limiter:
            try:
                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    logger.info(f"Parser API {endpoint}: OK")
                    return data
            except aiohttp.ClientResponseError as e:
                logger.error(f"Parser API {endpoint} error: {e.status} - {e.message}")
                raise
            except Exception as e:
                logger.error(f"Parser API {endpoint} failed: {str(e)}")
                raise

    async def search_fiz(
        self,
        last_name: str = "",
        first_name: str = "",
        patronymic: str = "",
        region_id: int = -1  # -1 = все регионы
    ) -> List[Dict[str, Any]]:
        """
        Поиск физических лиц-банкротов

        Документация: https://parser-api.com/bankrot-fedresurs-ru#documentation
        """
        params = {
            "regionID": region_id,
            "lastName": last_name,
            "firstName": first_name,
            "patronymic": patronymic
        }

        # Убираем пустые параметры
        params = {k: v for k, v in params.items() if v}

        result = await self._request("search_fiz", params)
        return result.get("result", [])

    async def search_yur(
        self,
        company_name: str = "",
        inn: str = "",
        ogrn: str = "",
        region_id: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Поиск юридических лиц-банкротов

        Args:
            company_name: Название компании
            inn: ИНН
            ogrn: ОГРН
            region_id: ID региона (-1 = все регионы)
        """
        params = {
            "regionID": region_id,
            "companyName": company_name,
            "inn": inn,
            "ogrn": ogrn
        }

        # Убираем пустые параметры
        params = {k: v for k, v in params.items() if v}

        result = await self._request("search_yur", params)
        return result.get("result", [])

    async def get_trade_messages(
        self,
        date_from: str = "",
        date_to: str = "",
        region_id: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Получение сообщений о торгах

        ВАЖНО: Parser API может не иметь прямого endpoint для trade_messages.
        Используйте search_yur/search_fiz для поиска банкротов,
        затем обогащайте данными через другие источники.

        Args:
            date_from: Дата начала (формат YYYY-MM-DD)
            date_to: Дата окончания (формат YYYY-MM-DD)
            region_id: ID региона
        """
        # TODO: Уточнить есть ли такой endpoint в Parser API
        # Пока возвращаем пустой список
        logger.warning("Parser API: get_trade_messages not implemented - use search_yur/search_fiz instead")
        return []

    async def close(self):
        """Закрыть сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Parser API client session closed")
