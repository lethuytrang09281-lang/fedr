import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from src.core.config import settings
from loguru import logger

class CheckoClient:
    def __init__(self):
        self.api_key = settings.CHECKO_API_KEY
        self.base_url = "https://api.checko.ru/v2"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_company_info(self, inn: str) -> dict:
        if not self.api_key: return {}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/company", params={"key": self.api_key, "inn": inn})
                if resp.status_code == 200: return resp.json().get("data", {})
            except Exception as e:
                logger.error(f"Checko error: {e}")
        return {}