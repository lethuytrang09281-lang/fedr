import asyncio
import logging
from typing import Optional, Dict, Any
from aiolimiter import AsyncLimiter
import aiohttp
from src.config import settings
from src.schemas import AuthToken, TradeResponseSchema


logger = logging.getLogger(__name__)


class EfrsbClient:
    def __init__(self):
        self.base_url = settings.base_url
        self.limiter = AsyncLimiter(settings.MAX_REQS_PER_SECOND, 1)
        self._token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"}
            )
        return self._session

    async def login(self):
        """Авторизация и получение JWT"""
        url = f"{self.base_url}/v1/auth"
        payload = {"login": settings.EFRSB_LOGIN, "password": settings.EFRSB_PASSWORD}

        session = await self._get_session()
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            self._token = AuthToken(**data).jwt
            logger.info("Successfully authenticated in EFRSB")

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Обертка над запросом с лимитами и retry-логикой"""
        if not self._token:
            await self.login()

        session = await self._get_session()
        url = f"{self.base_url}{path}"

        for attempt in range(3):  # Retry policy
            async with self.limiter:
                headers = kwargs.pop("headers", {})
                headers["Authorization"] = f"Bearer {self._token}"

                try:
                    async with session.request(method, url, headers=headers, **kwargs) as resp:
                        if resp.status == 401:
                            await self.login()
                            continue
                        if resp.status == 429:
                            wait_time = (attempt + 1) * 2
                            logger.warning(f"Rate limited. Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        resp.raise_for_status()
                        return await resp.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == 2:
                        raise
                    logger.error(f"Request failed: {e}. Retrying...")
                    await asyncio.sleep(1)

    async def get_trade_messages(
        self,
        date_start: str,
        date_end: str,
        offset: int = 0,
        limit: int = 500
    ) -> TradeResponseSchema:
        """Получение списка торгов с пагинацией"""
        params = {
            "datePublishBegin": date_start,
            "datePublishEnd": date_end,
            "includeContent": "true",
            "offset": offset,
            "limit": limit
        }

        data = await self._request("GET", "/v1/trade-messages", params=params)
        return TradeResponseSchema(**data)

    async def close(self):
        if self._session:
            await self._session.close()