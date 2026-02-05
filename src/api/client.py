import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from src.core.config import settings


class FedresursClient:
    """
    Клиент для работы с REST API ЕФРСБ (Единый Федеральный Реестр Сведений о Банкротстве).

    Критичные ограничения:
    - Rate Limit: Максимум 8 запросов в секунду с одного IP
    - Токен авторизации живет ~12 часов
    - Максимальное окно дат в запросе: 31 день
    """

    def __init__(self):
        self.api_url = settings.EFRSB_BASE_URL
        self.login = settings.EFRSB_LOGIN
        self.password = settings.EFRSB_PASSWORD

        # Rate limiting: 8 rps (строго!)
        self.semaphore = asyncio.Semaphore(8)
        self.min_delay = 0.125  # 1/8 секунды между запросами

        # HTTP клиент
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False,
            headers={
                "User-Agent": settings.USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )

        # Управление токеном
        self.token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        logger.info(f"🔧 FedresursClient initialized (API: {self.api_url})")

    async def authenticate(self) -> bool:
        """
        Авторизация в API ЕФРСБ через POST /v1/auth.

        Ожидаемый ответ:
        {
            "token": "Bearer eyJhbGc...",
            "expireDate": "2025-02-06T00:00:00"
        }

        Returns:
            bool: True если авторизация успешна
        """
        try:
            auth_url = f"{self.api_url}/v1/auth"
            payload = {
                "login": self.login,
                "password": self.password
            }

            logger.info(f"🔐 Authenticating as '{self.login}'...")

            response = await self.client.post(auth_url, json=payload)
            response.raise_for_status()

            data = response.json()
            self.token = data.get("token")

            # Парсим дату истечения токена
            expire_date_str = data.get("expireDate")
            if expire_date_str:
                # Формат: "2025-02-06T00:00:00" или "2025-02-06T00:00:00.000Z"
                expire_date_str = expire_date_str.replace("Z", "+00:00")
                try:
                    self.token_expires_at = datetime.fromisoformat(expire_date_str)
                except ValueError:
                    # Если не удалось распарсить, устанавливаем 12 часов от текущего времени
                    self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
            else:
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=12)

            # Обновляем заголовок с токеном
            self.client.headers["Authorization"] = self.token

            logger.success(f"✅ Authentication successful (token expires: {self.token_expires_at})")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Authentication failed: HTTP {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}", exc_info=True)
            return False

    async def ensure_authenticated(self):
        """
        Проверяет наличие валидного токена и обновляет его при необходимости.
        Вызывается автоматически перед каждым API-запросом.
        """
        now = datetime.now(timezone.utc)

        # Если токена нет или он истекает в течение 5 минут - обновляем
        if not self.token or not self.token_expires_at or (self.token_expires_at - now).total_seconds() < 300:
            logger.info("🔄 Token expired or missing, re-authenticating...")
            await self.authenticate()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=2, max=30)
    )
    async def get_trade_messages(
        self,
        date_start: str,
        date_end: str,
        include_content: bool = True,
        limit: int = 50,
        offset: int = 0,
        message_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение списка сообщений о торгах из API ЕФРСБ.

        Endpoint: GET /v1/trade-messages

        Args:
            date_start: Начало периода в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS)
            date_end: Конец периода в формате ISO 8601 (макс. 31 день от date_start)
            include_content: Включить XML контент в ответ (ОБЯЗАТЕЛЬНО для парсинга!)
            limit: Количество записей (макс. 500)
            offset: Смещение для пагинации
            message_type: Фильтр по типу (BiddingInvitation, Auction2, PublicOffer и т.д.)

        Returns:
            dict: {
                "total": int,
                "pageData": [
                    {
                        "guid": str,
                        "number": str,
                        "datePublish": str,
                        "type": str,
                        "content": str (XML),
                        "tradePlaceGuid": str,
                        "trade": {"number": str, "guid": str}
                    }
                ]
            }
        """
        await self.ensure_authenticated()

        # Соблюдаем rate limit (8 rps)
        async with self.semaphore:
            await asyncio.sleep(self.min_delay)

            try:
                url = f"{self.api_url}/v1/trade-messages"
                params = {
                    "datePublishBegin": date_start,
                    "datePublishEnd": date_end,
                    "includeContent": str(include_content).lower(),
                    "limit": limit,
                    "offset": offset
                }

                if message_type:
                    params["type"] = message_type

                logger.debug(f"📡 GET {url} (offset={offset}, limit={limit})")

                response = await self.client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                total = data.get("total", 0)
                page_items = data.get("pageData", [])

                logger.info(f"✅ Fetched {len(page_items)} messages (total: {total})")
                return data

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ API Error: HTTP {e.response.status_code} - {e.response.text}")

                # Если 401 - токен протух, пробуем переавторизоваться
                if e.response.status_code == 401:
                    logger.warning("⚠️  Token expired, re-authenticating...")
                    await self.authenticate()
                    raise  # Retry через tenacity

                return {"total": 0, "pageData": []}

            except Exception as e:
                logger.error(f"❌ Request error: {e}", exc_info=True)
                raise

    async def get_messages(
        self,
        date_start: str,
        date_end: str,
        include_content: bool = True,
        limit: int = 50,
        offset: int = 0,
        message_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение общего потока сообщений АУ (для стратегии "Shift Left").

        Endpoint: GET /v1/messages
        Используется для поиска InventoryResult и AppraiserReport (Pre-Market).

        Параметры аналогичны get_trade_messages().
        """
        await self.ensure_authenticated()

        async with self.semaphore:
            await asyncio.sleep(self.min_delay)

            try:
                url = f"{self.api_url}/v1/messages"
                params = {
                    "datePublishBegin": date_start,
                    "datePublishEnd": date_end,
                    "includeContent": str(include_content).lower(),
                    "limit": limit,
                    "offset": offset
                }

                if message_type:
                    params["type"] = message_type

                logger.debug(f"📡 GET {url} (offset={offset}, limit={limit})")

                response = await self.client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                total = data.get("total", 0)
                page_items = data.get("pageData", [])

                logger.info(f"✅ Fetched {len(page_items)} general messages (total: {total})")
                return data

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ API Error: HTTP {e.response.status_code}")
                if e.response.status_code == 401:
                    await self.authenticate()
                    raise
                return {"total": 0, "pageData": []}

            except Exception as e:
                logger.error(f"❌ Request error: {e}", exc_info=True)
                raise

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=2, max=10)
    )
    async def fetch_auction_xml(self, guid: str) -> str:
        """
        Legacy метод для обратной совместимости.
        Получение XML контента конкретного сообщения по GUID.
        """
        await self.ensure_authenticated()

        async with self.semaphore:
            await asyncio.sleep(self.min_delay)

            try:
                # Пытаемся получить через trade-messages
                url = f"{self.api_url}/v1/trade-messages/{guid}"
                response = await self.client.get(url)
                response.raise_for_status()

                data = response.json()
                content = data.get("content", "")

                logger.info(f"✅ Fetched XML for auction {guid}")
                return content

            except Exception as e:
                logger.error(f"❌ Error fetching auction XML {guid}: {e}")
                return "<xml>error</xml>"

    async def close(self):
        """Закрыть HTTP клиент и освободить ресурсы."""
        if self.client:
            await self.client.aclose()
            logger.info("✅ FedresursClient closed")