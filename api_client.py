"""
FEDRESURS RADAR - API Client
Асинхронный клиент с rate limiting и автоматическим обновлением JWT
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import aiohttp
from aiolimiter import AsyncLimiter
from loguru import logger

from src.config import settings


class EfrsbClient:
    """
    Асинхронный HTTP-клиент для работы с REST API ЕФРСБ
    
    Ключевые фичи:
    - Rate Limiting (6-7 req/sec с учётом джиттера)
    - Автоматическое обновление JWT токена (живёт ~12 часов)
    - Retry logic с exponential backoff
    - Обработка ошибок 401 (Unauthorized), 429 (Too Many Requests)
    """
    
    def __init__(self):
        self.base_url = settings.api_base_url
        self.login = settings.api_login
        self.password = settings.api_password
        
        # Rate Limiter: безопасное значение с запасом на джиттер
        self.limiter = AsyncLimiter(
            max_rate=settings.max_reqs_per_second,
            time_period=1.0
        )
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._jwt_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def initialize(self):
        """Инициализация сессии и получение токена"""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=settings.api_timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
        
        # Получаем JWT токен
        await self._ensure_auth()
        logger.info(f"EfrsbClient initialized: {self.base_url}")
    
    async def close(self):
        """Закрытие сессии"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("EfrsbClient closed")
    
    async def _ensure_auth(self):
        """Проверка и обновление JWT токена"""
        now = datetime.now(timezone.utc)
        
        # Токен отсутствует или истёк
        if not self._jwt_token or not self._token_expires_at or now >= self._token_expires_at:
            await self._refresh_token()
    
    async def _refresh_token(self):
        """Получение нового JWT токена"""
        url = f"{self.base_url}/v1/auth"
        payload = {
            "login": self.login,
            "password": self.password
        }
        
        try:
            async with self._session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Токен может быть в поле "jwt" или "JWT"
                self._jwt_token = data.get("jwt") or data.get("JWT")
                
                if not self._jwt_token:
                    raise ValueError("JWT token not found in auth response")
                
                # Токен живёт ~12 часов, обновляем за час до истечения
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=11)
                
                logger.info("JWT token refreshed successfully")
                
        except Exception as e:
            logger.error(f"Failed to refresh JWT token: {e}")
            raise
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Базовый метод для HTTP-запросов с retry logic
        
        Args:
            method: HTTP метод (GET, POST)
            endpoint: API endpoint (например, /v1/messages)
            params: Query параметры
            json: JSON body для POST
            retry_count: Счётчик попыток (для рекурсии)
        
        Returns:
            Dict с ответом API
        """
        await self._ensure_auth()
        
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._jwt_token}"}
        
        # Rate limiting: ждём своей очереди
        async with self.limiter:
            try:
                async with self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers
                ) as response:
                    
                    # 401: Токен протух, обновляем и повторяем
                    if response.status == 401:
                        logger.warning("401 Unauthorized - refreshing token")
                        await self._refresh_token()
                        return await self._request(method, endpoint, params, json, retry_count)
                    
                    # 429: Превысили лимит, ждём exponential backoff
                    if response.status == 429:
                        if retry_count < settings.max_retries:
                            wait_time = (retry_count + 1) * settings.retry_backoff_factor
                            logger.warning(f"429 Too Many Requests - waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            return await self._request(method, endpoint, params, json, retry_count + 1)
                        else:
                            raise Exception("Max retries reached for 429 error")
                    
                    # 5xx: Server error, повторяем с backoff
                    if 500 <= response.status < 600:
                        if retry_count < settings.max_retries:
                            wait_time = (retry_count + 1) * settings.retry_backoff_factor
                            logger.warning(f"{response.status} Server Error - waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            return await self._request(method, endpoint, params, json, retry_count + 1)
                        else:
                            raise Exception(f"Max retries reached for {response.status} error")
                    
                    response.raise_for_status()
                    return await response.json()
                    
            except aiohttp.ClientError as e:
                logger.error(f"Request failed: {method} {url} - {e}")
                
                # Retry на сетевых ошибках
                if retry_count < settings.max_retries:
                    wait_time = (retry_count + 1) * settings.retry_backoff_factor
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await self._request(method, endpoint, params, json, retry_count + 1)
                
                raise
    
    async def get_trade_messages(
        self,
        date_begin: datetime,
        date_end: datetime,
        include_content: bool = True,
        limit: int = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получение списка сообщений о торгах
        
        Endpoint: GET /v1/trade-messages
        
        Args:
            date_begin: Начало периода
            date_end: Конец периода (макс +31 день от date_begin)
            include_content: Включить XML-контент
            limit: Размер страницы (макс 500)
            offset: Смещение для пагинации
        
        Returns:
            {
                "total": int,
                "pageData": [
                    {
                        "guid": "...",
                        "type": "BiddingInvitation",
                        "datePublish": "2024-01-31T12:00:00",
                        "content": "<xml>...</xml>",
                        "isAnnulled": false,
                        "isLocked": false
                    }
                ]
            }
        """
        limit = limit or settings.api_page_limit
        
        params = {
            "datePublishBegin": f"gte:{date_begin.strftime('%Y-%m-%dT%H:%M:%S')}",
            "datePublishEnd": f"lte:{date_end.strftime('%Y-%m-%dT%H:%M:%S')}",
            "includeContent": str(include_content).lower(),
            "isAnnulled": "false",  # Только активные
            "isLocked": "false",    # Только незаблокированные
            "limit": limit,
            "offset": offset
        }
        
        return await self._request("GET", "/v1/trade-messages", params=params)
    
    async def get_messages(
        self,
        date_begin: datetime,
        date_end: datetime,
        message_types: Optional[List[str]] = None,
        include_content: bool = True,
        limit: int = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получение списка сообщений (общая лента, не только торги)
        
        Endpoint: GET /v1/messages
        
        Используется для "Shift Left" стратегии:
        - PropertyInventoryResult (инвентаризация)
        - MeetingResult (собрания кредиторов)
        - PropertyEvaluationReport (оценка)
        """
        limit = limit or settings.api_page_limit
        
        params = {
            "datePublishBegin": f"gte:{date_begin.strftime('%Y-%m-%dT%H:%M:%S')}",
            "datePublishEnd": f"lte:{date_end.strftime('%Y-%m-%dT%H:%M:%S')}",
            "includeContent": str(include_content).lower(),
            "isAnnulled": "false",
            "limit": limit,
            "offset": offset
        }
        
        if message_types:
            params["type"] = ",".join(message_types)
        
        return await self._request("GET", "/v1/messages", params=params)
    
    async def get_message_by_guid(self, guid: str) -> Dict[str, Any]:
        """Получение конкретного сообщения по GUID"""
        return await self._request("GET", f"/v1/messages/{guid}")
    
    async def get_linked_messages(self, guid: str) -> List[Dict[str, Any]]:
        """Получение связанных сообщений (цепочка торгов)"""
        result = await self._request("GET", f"/v1/messages/{guid}/linked")
        return result.get("pageData", [])


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_client() -> EfrsbClient:
    """Factory function для создания клиента"""
    client = EfrsbClient()
    await client.initialize()
    return client


# ============================================================================
# Quick Test
# ============================================================================

async def test_client():
    """Быстрый тест авторизации и запроса"""
    async with EfrsbClient() as client:
        # Тест авторизации
        logger.info(f"Token: {client._jwt_token[:20]}...")
        
        # Тест запроса (последние 7 дней)
        date_end = datetime.now(timezone.utc)
        date_begin = date_end - timedelta(days=7)
        
        result = await client.get_trade_messages(
            date_begin=date_begin,
            date_end=date_end,
            limit=5
        )
        
        logger.info(f"Total messages: {result.get('total', 0)}")
        logger.info(f"Retrieved: {len(result.get('pageData', []))}")


if __name__ == "__main__":
    # Настройка логирования
    logger.add(
        settings.log_file,
        rotation="100 MB",
        level=settings.log_level
    )
    
    # Запуск теста
    asyncio.run(test_client())
