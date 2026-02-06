import httpx
import logging
from typing import Optional, Dict, Any, List
from src.config import settings

logger = logging.getLogger(__name__)

class ParserAPIClient:
    """Клиент для работы с parser-api.com"""

    BASE_URL = "https://parser-api.com/parser"

    def __init__(self):
        self.api_key = settings.PARSER_API_KEY

    async def check_pledges_by_name(self, name: str) -> Optional[Dict]:
        """Проверка в реестре залогов по имени"""
        url = f"{self.BASE_URL}/reestr_api/search_by_name"
        params = {
            "key": self.api_key,
            "name": name
        }
        return await self._make_request(url, params)

    async def check_pledges_by_vin(self, vin: str) -> Optional[Dict]:
        """Проверка залога по VIN"""
        url = f"{self.BASE_URL}/reestr_api/search_by_vin"
        params = {
            "key": self.api_key,
            "vin": vin
        }
        return await self._make_request(url, params)

    async def get_arbitr_case(self, case_number: str) -> Optional[Dict]:
        """Получить детали арбитражного дела"""
        url = f"{self.BASE_URL}/arbitr_api/details_by_number"
        params = {
            "key": self.api_key,
            "CaseNumber": case_number
        }
        return await self._make_request(url, params)

    async def search_arbitr_by_inn(self, inn: str) -> Optional[Dict]:
        """Поиск арбитражных дел по ИНН"""
        url = f"{self.BASE_URL}/arbitr_api/search"
        params = {
            "key": self.api_key,
            "Inn": inn
        }
        return await self._make_request(url, params)

    async def search_bankrupt_fiz(
        self,
        last_name: str,
        first_name: str,
        patronymic: str = "",
        region_id: int = -1
    ) -> Optional[Dict]:
        """Поиск банкрота физлица в Федресурсе"""
        url = f"{self.BASE_URL}/fedresurs_api/search_fiz"
        params = {
            "key": self.api_key,
            "lastName": last_name,
            "firstName": first_name,
            "patronymic": patronymic,
            "regionID": region_id
        }
        return await self._make_request(url, params)

    async def search_bankrupt_ur(self, inn: str) -> Optional[Dict]:
        """Поиск банкрота юрлица по ИНН"""
        url = f"{self.BASE_URL}/fedresurs_api/search_ur"
        params = {
            "key": self.api_key,
            "inn": inn
        }
        return await self._make_request(url, params)

    async def search_mosgorsud(self, participant: str) -> Optional[Dict]:
        """Поиск дел в Мосгорсуде"""
        url = f"{self.BASE_URL}/mosgorsud_api/"
        params = {
            "key": self.api_key,
            "participant": participant
        }
        return await self._make_request(url, params)

    async def get_api_stats(self) -> Optional[Dict]:
        """Получить статистику использования API"""
        url = f"https://parser-api.com/stat/"
        params = {"key": self.api_key}
        return await self._make_request(url, params)

    async def _make_request(self, url: str, params: Dict) -> Optional[Dict]:
        """Выполняет HTTP запрос"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
        return None
