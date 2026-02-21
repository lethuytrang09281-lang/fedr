"""
Fedresurs Search — поиск торгов по недвижимости в банкротных делах
Pipeline: search_ur → get_org_messages → get_message → фильтрация → БД

Автор: Fedresurs Pro
Документация API: https://parser-api.com/documentation/fedresurs-api.txt
"""

import asyncio
import aiohttp
import logging
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# СЕМАНТИЧЕСКИЙ ФИЛЬТР
# ============================================================

PROPERTY_KEYWORDS = [
    "нежилое здание", "офисное здание", "торговое здание",
    "бизнес-центр", "торговый центр", "административное здание",
    "офисный центр", "многоквартирный дом", "жилой дом", "мкд", "здание",
]

GEO_KEYWORDS = [
    "москва", "московск",
    "цао", "центральный административный округ",
    "тверской", "арбат", "пресненский", "басманный",
    "замоскворечье", "китай-город", "мещанский", "таганский", "якиманка",
    "хамовники", "якиманка", "лефортово", "красносельский",
]

CADASTRAL_PATTERN = re.compile(r'\b77:\d{2}:\d+')


def semantic_match(text: str) -> tuple[bool, bool, bool]:
    """
    Возвращает (property_match, geo_match, cadastral_match).
    Проходит если: (property_match AND geo_match) OR cadastral_match
    """
    t = text.lower()
    prop = any(kw in t for kw in PROPERTY_KEYWORDS)
    geo = any(kw in t for kw in GEO_KEYWORDS)
    cadastral = bool(CADASTRAL_PATTERN.search(text))
    return prop, geo, cadastral


# ============================================================
# КОНФИГУРАЦИЯ ПОИСКА (МЕНЯТЬ ТОЛЬКО ЗДЕСЬ!)
# ============================================================
SEARCH_CONFIG = {
    # География
    "region_id": 77,              # 77 = Москва

    # Цена
    "max_price": 700_000_000,     # 700 млн рублей
    "min_price": 1_000_000,       # 1 млн (отсекаем мусор)

    # Ключевые слова для фильтрации лотов (в описании) — используем PROPERTY_KEYWORDS
    "keywords": PROPERTY_KEYWORDS,

    # Тип сообщения о торгах
    "trade_message_types": [
        "объявление о проведении торгов",
        "сообщение о торгах",
        "торги",
    ],

    # Типы сообщений раннего захвата (инвентаризация / оценка)
    "early_message_types": [
        "сведения о результатах инвентаризации",
        "результатах инвентаризации имущества",
        "инвентаризация имущества",
        "сведения о привлечении оценщика",
        "привлечении оценщика",
        "оценщик",
        "PropertyInventoryResult",
        "PropertyEvaluationReport",
    ],

    # Пагинация (экономим запросы)
    "orgs_per_request": 1000,     # организаций за один search_ur
    "msgs_per_request": 1000,     # сообщений за один get_org_messages

    # Лимиты
    "daily_limit": 240,           # 250/день с запасом
    "request_delay": 2,           # секунд между запросами

    # Хранение статистики
    "usage_file": "/app/data/api_usage.json",
}
# ============================================================


class RequestCounter:
    """Счётчик запросов с дневным лимитом + сохранение в файл"""

    def __init__(self, storage_file: str):
        self.storage_file = storage_file
        self._today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r") as f:
                    data = json.load(f)
                    last_reset = data.get("last_reset", "")
                    self._today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    if last_reset != self._today:
                        self.count = 0
                    else:
                        self.count = data.get("fedresurs_today", 0)
            else:
                self.count = 0
        except Exception:
            self.count = 0

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            data = {
                "fedresurs_today": self.count,
                "last_reset": self._today,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Не могу сохранить счётчик: {e}")

    def can_request(self) -> bool:
        # Сбрасываем счётчик если наступил новый день (работаем без перезапуска)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._today:
            self._today = today
            self.count = 0
            self._save()
            logger.info(f"🔄 Новый день ({today}), счётчик запросов сброшен")
        return self.count < SEARCH_CONFIG["daily_limit"]

    def increment(self):
        self.count += 1
        self._save()
        remaining = SEARCH_CONFIG["daily_limit"] - self.count
        logger.info(f"📡 Fedresurs запрос #{self.count} | осталось сегодня: {remaining}")

    @property
    def remaining(self) -> int:
        return SEARCH_CONFIG["daily_limit"] - self.count


class FedresursSearch:
    """
    Поиск торгов по недвижимости в банкротных делах Москвы.

    Pipeline:
    1. search_ur (регион=77) → список организаций-банкротов
    2. get_org_messages → сообщения каждой организации
    3. get_message → детали: лоты, цены, описания
    4. Фильтрация: здание + цена до 300М
    """

    BASE_URL = "https://parser-api.com/parser/fedresurs_api"

    def __init__(self, api_key: str, resource_monitor=None):
        self.api_key = api_key
        self.monitor = resource_monitor  # ResourceMonitor (опционально)
        self.counter = RequestCounter(SEARCH_CONFIG["usage_file"])
        self.lock = asyncio.Lock()       # один запрос за раз!
        self.session: Optional[aiohttp.ClientSession] = None

        # Статистика сессии
        self.stats = {
            "orgs_found": 0,
            "messages_checked": 0,
            "trade_messages_found": 0,
            "lots_found": 0,
            "lots_passed_filter": 0,
            "requests_made": 0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _request(self, endpoint: str, params: dict) -> Optional[dict]:
        """
        Базовый метод запроса к Parser API.
        Один запрос за раз (asyncio.Lock).
        """
        async with self.lock:

            # Проверка дневного лимита
            if not self.counter.can_request():
                logger.error(
                    f"❌ Дневной лимит исчерпан! {self.counter.count}/250. "
                    f"Попробуй завтра."
                )
                return None

            # Проверка ресурсов сервера
            if self.monitor and self.monitor.should_pause():
                logger.warning("⏸️ Высокая нагрузка сервера, ждём...")
                await self.monitor.wait_if_needed()

            url = f"{self.BASE_URL}/{endpoint}"
            params["key"] = self.api_key

            session = await self._get_session()

            try:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:

                    if resp.status == 403:
                        body = await resp.json()
                        error_code = body.get("error_code")
                        error_msg = body.get("error", "403 Forbidden")

                        if error_code == 40304:
                            logger.error("❌ Дневной лимит исчерпан (40304)")
                        elif error_code == 40305:
                            logger.error("❌ Месячный лимит исчерпан (40305)")
                        elif error_code == 40302:
                            logger.error("❌ Подписка истекла (40302)")
                        else:
                            logger.error(f"❌ 403: {error_msg}")
                        return None

                    if resp.status != 200:
                        logger.error(f"❌ HTTP {resp.status} для {endpoint}")
                        return None

                    data = await resp.json()

                    # Успешный запрос — считаем только success=1
                    if data.get("success") == 1:
                        self.counter.increment()
                        self.stats["requests_made"] += 1
                    else:
                        logger.warning(f"⚠️ success=0 для {endpoint}, не считаем")

                    return data

            except asyncio.TimeoutError:
                logger.error(f"⏱️ Timeout для {endpoint}")
                return None
            except Exception as e:
                logger.error(f"❌ Ошибка запроса {endpoint}: {e}")
                return None

            finally:
                # Задержка между запросами
                await asyncio.sleep(SEARCH_CONFIG["request_delay"])

    # ------------------------------------------------------------------
    # ШАГ 1: Поиск организаций-банкротов в Москве
    # ------------------------------------------------------------------

    async def _get_orgs_page(self, from_record: int = 0) -> tuple[list, int]:
        """
        Одна страница поиска организаций.
        Возвращает: (список организаций, total_count)
        """
        data = await self._request("search_ur", {
            "orgRegionID": SEARCH_CONFIG["region_id"],
            "from_record": from_record,
            "limit": SEARCH_CONFIG["orgs_per_request"],
            "includeBankruptInfo": "true",
        })

        if not data or data.get("success") != 1:
            return [], 0

        records = data.get("records", [])
        total = int(data.get("total_count", 0))
        return records, total

    async def get_all_orgs(self) -> list:
        """
        Получить все организации-банкроты Москвы.
        С пагинацией.
        """
        logger.info(f"🔍 ШАГ 1: Поиск организаций-банкротов (регион=77 Москва)")

        all_orgs = []
        from_record = 0

        # Первый запрос — узнаём total_count
        orgs, total = await self._get_orgs_page(from_record=0)

        if not orgs:
            logger.error("❌ Не получили организации на первой странице")
            return []

        all_orgs.extend(orgs)
        logger.info(f"📊 Всего организаций-банкротов в Москве: {total}")
        logger.info(f"📦 Получено: {len(orgs)} (страница 1)")

        from_record = len(orgs)

        # Остальные страницы
        while from_record < total:
            if not self.counter.can_request():
                logger.warning(f"⚠️ Лимит! Остановились на {from_record}/{total}")
                break

            orgs, _ = await self._get_orgs_page(from_record=from_record)
            if not orgs:
                break

            all_orgs.extend(orgs)
            from_record += len(orgs)
            logger.info(f"📦 Получено: {len(all_orgs)}/{total}")

        self.stats["orgs_found"] = len(all_orgs)
        logger.info(f"✅ ШАГ 1 завершён: {len(all_orgs)} организаций")
        return all_orgs

    # ------------------------------------------------------------------
    # ШАГ 2: Сообщения организации
    # ------------------------------------------------------------------

    async def _get_org_messages(self, org_id: str, from_record: int = 0) -> tuple[list, int]:
        """Сообщения одной организации (одна страница)"""
        data = await self._request("get_org_messages", {
            "id": org_id,
            "from_record": from_record,
            "limit": SEARCH_CONFIG["msgs_per_request"],
        })

        if not data or data.get("success") != 1:
            return [], 0

        records = data.get("records", [])
        total = int(data.get("total_count", 0))
        return records, total

    def _is_trade_message(self, msg: dict) -> bool:
        """Это сообщение о торгах?"""
        msg_type = (msg.get("type") or "").lower()
        return any(t in msg_type for t in SEARCH_CONFIG["trade_message_types"])

    def _is_early_message(self, msg: dict) -> bool:
        """Это сообщение раннего захвата (инвентаризация/оценка)?"""
        msg_type = (msg.get("type") or "").lower()
        return any(t.lower() in msg_type for t in SEARCH_CONFIG["early_message_types"])

    async def get_message_ids_by_type(self, org: dict) -> dict:
        """
        Из сообщений организации выбрать торги и ранние сообщения.
        Возвращает {"trade": [...], "early": [...]}
        """
        org_id = org.get("id")
        org_name = org.get("debtor", "Неизвестно")

        messages, total = await self._get_org_messages(org_id, from_record=0)

        if not messages:
            return {"trade": [], "early": []}

        trade_ids = []
        early_ids = []
        self.stats["messages_checked"] += len(messages)

        for msg in messages:
            if self._is_trade_message(msg):
                trade_ids.append(msg["id"])
            elif self._is_early_message(msg):
                early_ids.append(msg["id"])

        if trade_ids or early_ids:
            logger.info(
                f"🏢 {org_name[:40]}: "
                f"{len(trade_ids)} торгов, {len(early_ids)} ранних из {total}"
            )

        return {"trade": trade_ids, "early": early_ids}

    # Backward compat
    async def get_trade_message_ids(self, org: dict) -> list:
        result = await self.get_message_ids_by_type(org)
        return result["trade"]

    # ------------------------------------------------------------------
    # ШАГ 3: Детали сообщения о торгах
    # ------------------------------------------------------------------

    async def get_message_details(self, msg_id: str) -> Optional[dict]:
        """Детальная информация о сообщении (с лотами)"""
        data = await self._request("get_message", {"id": msg_id})

        if not data or data.get("success") != 1:
            return None

        return data.get("record")

    # ------------------------------------------------------------------
    # ЭТП методы
    # ------------------------------------------------------------------

    async def get_trade_messages(self, published_after: str, region_id: int = 77, limit: int = 1000) -> list:
        """
        Получить сообщения о торгах через ЭТП.
        
        Args:
            published_after: Дата в формате YYYY-MM-DD
            region_id: Код региона (77 = Москва)
            limit: Максимальное количество записей
        
        Returns:
            Список сообщений о торгах
        """
        data = await self._request("trade_messages", {
            "published_after": published_after,
            "region_id": region_id,
            "limit": limit,
        })

        if not data or data.get("success") != 1:
            return []

        return data.get("records", [])

    async def get_trade_message_content(self, guid: str) -> Optional[dict]:
        """
        Получить содержимое сообщения о торгах по GUID.
        
        Args:
            guid: GUID сообщения
        
        Returns:
            Детальная информация о сообщении
        """
        data = await self._request("trade_message_content", {
            "guid": guid,
        })

        if not data or data.get("success") != 1:
            return None

        return data.get("record")

    # ------------------------------------------------------------------
    # ФИЛЬТРАЦИЯ
    # ------------------------------------------------------------------

    def _filter_lot(self, lot: dict, org: dict, message: dict) -> Optional[dict]:
        """
        Проверяем: это нужный нам лот?
        Возвращает обогащённый лот или None.
        """
        description = (lot.get("description") or "").lower()
        lot_type = (lot.get("type") or "").lower()
        text_to_search = description + " " + lot_type
        lot_num = lot.get("num", "?")
        org_name = org.get("debtor", "?")[:40]

        # Фильтр по ключевым словам
        found_keyword = next(
            (kw for kw in SEARCH_CONFIG["keywords"] if kw in text_to_search),
            None
        )
        if not found_keyword:
            logger.info(
                f"⏭️ Лот #{lot_num} [{org_name}] — нет ключевых слов. "
                f"description={description[:80]!r}, type={lot_type!r}"
            )
            return None

        # Фильтр по цене
        try:
            price_str = str(lot.get("start_price", "0"))
            # Убираем пробелы, запятые и т.д.
            price_str = price_str.replace(" ", "").replace(",", ".").replace("\xa0", "")
            price = float(price_str) if price_str else 0
        except (ValueError, TypeError):
            price = 0

        if price <= SEARCH_CONFIG["min_price"]:
            logger.info(
                f"⏭️ Лот #{lot_num} [{org_name}] — цена слишком низкая: {price:,.0f} ₽ "
                f"(мин {SEARCH_CONFIG['min_price']:,})"
            )
            return None

        if price > SEARCH_CONFIG["max_price"]:
            logger.info(
                f"⏭️ Лот #{lot_num} [{org_name}] — цена слишком высокая: {price:,.0f} ₽ "
                f"(макс {SEARCH_CONFIG['max_price']:,})"
            )
            return None

        # Фильтр по географии — только Москва
        # Проверяем описание лота и адрес должника
        description_orig = (lot.get("description") or "")
        debtor_address = (org.get("address") or "")
        geo_text = (description_orig + " " + debtor_address).lower()
        is_moscow = (
            "москв" in geo_text or          # Москва / московск...
            "77:" in description_orig or     # кадастровый номер Москвы
            "г. москва" in geo_text or
            "г москва" in geo_text
        )
        if not is_moscow:
            logger.info(
                f"⏭️ Лот #{lot_num} [{org_name}] — не Москва. "
                f"address={debtor_address[:60]!r}, desc={description_orig[:60]!r}"
            )
            return None

        # Лот прошёл фильтры!
        result = {
            # Данные лота
            "lot_num": lot.get("num"),
            "description": lot.get("description"),
            "start_price": price,
            "step": lot.get("step"),
            "deposit": lot.get("deposit"),
            "lot_type": lot.get("type"),
            "found_keyword": found_keyword,

            # Данные торгов
            "trade_type": message.get("trade_type"),
            "trade_app_start": message.get("trade_app_start_date"),
            "trade_app_end": message.get("trade_app_end_date"),
            "trade_place": message.get("trade_place"),
            "message_id": message.get("id"),
            "message_num": message.get("num"),
            "message_date": message.get("date_published"),

            # Данные должника
            "debtor_name": org.get("debtor"),
            "debtor_inn": org.get("inn"),
            "debtor_ogrn": org.get("ogrn"),
            "debtor_address": org.get("address"),
            "debtor_region": org.get("region"),
            "debtor_id": org.get("id"),

            # Метаданные
            "found_at": datetime.now(timezone.utc).isoformat(),
            "case_num": message.get("case_num"),
            "manager_name": message.get("manager_name"),
        }

        # ЭТП данные (если есть в сообщении)
        if "etp_url" in message:
            result["etp_url"] = message.get("etp_url")
        if "etp_name" in message:
            result["etp_name"] = message.get("etp_name")
        if "application_start" in message:
            result["application_start"] = message.get("application_start")
        if "application_end" in message:
            result["application_end"] = message.get("application_end")
        if "organizer_name" in message:
            result["organizer_name"] = message.get("organizer_name")

        return result

    # ------------------------------------------------------------------
    # ЛИДЫ (ранний захват)
    # ------------------------------------------------------------------

    def _parse_lead(self, message: dict, org: dict, msg_type_label: str) -> Optional[dict]:
        """
        Из сообщения инвентаризации/оценки извлекаем лид.
        Применяет семантический фильтр: (property AND geo) OR cadastral.
        Возвращает dict лида или None.
        """
        org_name = org.get("debtor", "?")[:40]
        msg_id = message.get("id") or message.get("num", "?")

        # Собираем текст для анализа
        description = message.get("description") or message.get("text") or ""
        address = org.get("address") or ""
        full_text = description + " " + address

        # Если лоты есть — берём описание из первого лота
        lots = message.get("lots") or []
        if lots and not description:
            description = lots[0].get("description", "")
            full_text = description + " " + address

        prop_match, geo_match, cad_match = semantic_match(full_text)
        passes = (prop_match and geo_match) or cad_match

        if not passes:
            logger.info(
                f"⏭️ Лид [{org_name}] msg={msg_id} — семантика не прошла "
                f"(property={prop_match}, geo={geo_match}, cadastral={cad_match})"
            )
            return None

        # Пытаемся извлечь стоимость из первого лота или поля message
        estimated_value = None
        if lots:
            try:
                price_str = str(lots[0].get("start_price", "") or "")
                price_str = price_str.replace(" ", "").replace(",", ".").replace("\xa0", "")
                if price_str:
                    estimated_value = int(float(price_str))
            except (ValueError, TypeError):
                pass

        # Определяем тип сообщения
        msg_api_type = (message.get("type") or "").lower()
        if "инвентаризац" in msg_api_type:
            stage = "inventory"
        elif "оценщик" in msg_api_type or "оценк" in msg_api_type:
            stage = "evaluation"
        else:
            stage = msg_type_label

        logger.info(
            f"🌱 ЛИДCATCHER: [{org_name}] {stage} | "
            f"property={prop_match} geo={geo_match} cad={cad_match} | "
            f"desc={description[:60]!r}"
        )

        return {
            "debtor_guid": org.get("id"),
            "debtor_name": org.get("debtor"),
            "debtor_inn": org.get("inn"),
            "message_type": stage,
            "description": description[:2000] if description else None,
            "address": address[:500] if address else None,
            "estimated_value": estimated_value,
            "source_message_id": str(message.get("id") or ""),
            "published_at": message.get("date_published"),
        }

    async def search_by_message_type(self, message_type: str, orgs: list) -> list:
        """
        Поиск лидов по типу сообщения среди уже полученных организаций.
        message_type: 'PropertyInventoryResult' | 'PropertyEvaluationReport' | 'TradeMessage'
        """
        leads = []

        for org in orgs:
            if not self.counter.can_request():
                break

            ids_map = await self.get_message_ids_by_type(org)
            target_ids = ids_map["early"] if message_type != "TradeMessage" else ids_map["trade"]

            for msg_id in target_ids:
                if not self.counter.can_request():
                    break

                message = await self.get_message_details(msg_id)
                if not message:
                    continue

                lead = self._parse_lead(message, org, message_type.lower())
                if lead:
                    leads.append(lead)

        return leads

    # ------------------------------------------------------------------
    # ГЛАВНЫЙ МЕТОД
    # ------------------------------------------------------------------

    async def search_lots(self) -> list:
        """
        Главный метод поиска.

        Pipeline:
        1. Получить все организации-банкроты Москвы
        2. Для каждой — найти сообщения о торгах
        3. Для каждого сообщения — получить лоты
        4. Фильтровать: здание + цена до 300М

        Returns: список отфильтрованных лотов
        """
        logger.info("=" * 60)
        logger.info("🚀 FEDRESURS PRO — ПОИСК ТОРГОВ")
        logger.info(f"📍 Регион: Москва (77)")
        logger.info(f"💰 Цена: {SEARCH_CONFIG['min_price']:,} — {SEARCH_CONFIG['max_price']:,} ₽")
        logger.info(f"🏢 Типы: {', '.join(SEARCH_CONFIG['keywords'])}")
        logger.info(f"📡 Осталось запросов сегодня: {self.counter.remaining}")
        logger.info("=" * 60)

        result_lots = []
        result_leads = []

        # ШАГ 1: Все организации-банкроты Москвы
        orgs = await self.get_all_orgs()

        if not orgs:
            logger.error("❌ Нет организаций, останавливаемся")
            return {"lots": [], "leads": []}

        # ШАГ 2 + 3: Для каждой организации — торги + ранние сообщения — лоты/лиды
        for idx, org in enumerate(orgs):

            if not self.counter.can_request():
                logger.warning(
                    f"⚠️ Лимит запросов! Обработано {idx}/{len(orgs)} организаций. "
                    f"Продолжим завтра."
                )
                break

            # Получаем ID сообщений: торги + ранние
            ids_map = await self.get_message_ids_by_type(org)
            trade_msg_ids = ids_map["trade"]
            early_msg_ids = ids_map["early"]

            self.stats["trade_messages_found"] += len(trade_msg_ids)

            # --- Торги → Лоты ---
            for msg_id in trade_msg_ids:
                if not self.counter.can_request():
                    break

                message = await self.get_message_details(msg_id)
                if not message:
                    continue

                lots = message.get("lots", [])
                self.stats["lots_found"] += len(lots)

                for lot in lots:
                    filtered = self._filter_lot(lot, org, message)
                    if filtered:
                        self.stats["lots_passed_filter"] += 1
                        result_lots.append(filtered)
                        logger.info(
                            f"🎯 НАЙДЕН ЛОТ!\n"
                            f"   Должник: {filtered['debtor_name'][:50]}\n"
                            f"   Описание: {filtered['description'][:80]}\n"
                            f"   Цена: {filtered['start_price']:,.0f} ₽\n"
                            f"   Ключевое слово: [{filtered['found_keyword']}]\n"
                            f"   Дело: {filtered['case_num']}"
                        )

            # --- Ранние сообщения → Лиды ---
            for msg_id in early_msg_ids:
                if not self.counter.can_request():
                    break

                message = await self.get_message_details(msg_id)
                if not message:
                    continue

                lead = self._parse_lead(message, org, "early")
                if lead:
                    result_leads.append(lead)

        # Итоги
        logger.info("=" * 60)
        logger.info("📊 ИТОГИ ПОИСКА:")
        logger.info(f"   Организаций проверено:     {self.stats['orgs_found']}")
        logger.info(f"   Сообщений проверено:       {self.stats['messages_checked']}")
        logger.info(f"   Сообщений о торгах:        {self.stats['trade_messages_found']}")
        logger.info(f"   Лотов всего:               {self.stats['lots_found']}")
        logger.info(f"   Лотов после фильтра:       {self.stats['lots_passed_filter']}")
        logger.info(f"   Лидов найдено:             {len(result_leads)}")
        logger.info(f"   Запросов потрачено:        {self.stats['requests_made']}")
        logger.info(f"   Осталось на сегодня:       {self.counter.remaining}")
        logger.info("=" * 60)

        return {"lots": result_lots, "leads": result_leads}

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# ------------------------------------------------------------------
# ЗАПУСК ДЛЯ ТЕСТА
# ------------------------------------------------------------------

async def _test():
    """Тестовый запуск"""
    import os

    api_key = os.getenv("PARSER_API_KEY")
    if not api_key:
        print("❌ Нет PARSER_API_KEY в окружении!")
        return

    search = FedresursSearch(api_key=api_key)

    try:
        lots = await search.search_lots()
        print(f"\n✅ Найдено {len(lots)} лотов")

        # Показать топ-5
        for lot in lots[:5]:
            print(f"\n--- ЛОТ ---")
            print(f"Должник: {lot['debtor_name']}")
            print(f"Описание: {lot['description'][:100]}")
            print(f"Цена: {lot['start_price']:,.0f} ₽")
            print(f"Дело: {lot['case_num']}")

    finally:
        await search.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(_test())