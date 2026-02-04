import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from src.core.config import settings

class FedresursClient:
    def __init__(self):
        self.api_url = settings.EFRSB_BASE_URL
        self.semaphore = asyncio.Semaphore(5)
        self.headers = {"User-Agent": settings.USER_AGENT, "Accept": "application/json"}
        self.client = httpx.AsyncClient(timeout=30.0, verify=False)

    @retry(retry=retry_if_exception_type(httpx.HTTPError), stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=10))
    async def fetch_auction_xml(self, guid: str) -> str:
        async with self.semaphore:
            await asyncio.sleep(0.15)
            # Эмуляция запроса
            return "<xml>placeholder</xml>"

    async def close(self):
        await self.client.aclose()