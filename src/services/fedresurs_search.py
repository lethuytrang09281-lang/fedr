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
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# КОНФИГУРАЦИЯ ПОИСКА (МЕНЯТЬ ТОЛЬКО ЗДЕСЬ!)
# ============================================================
SEARCH_CONFIG = {
    # География
    "region_id": 77,              # 77 = Москва

    # Цена
    "max_price": 300_000_000,     # 300 млн рублей
    "min_price": 1_000_000,       # 1 млн (отсекаем мусор)

    # Ключевые слова для фильтрации лотов (в описании)
    "keywords": [
        "здание",
        "нежилое здание",
        "административное здание",
        "офисное здание",
        "бизнес-центр",
        "офисный центр",
        "мкд",
        "многоквартирный дом",
        "жилой дом",
    ],

    # Тип сообщения о торгах
    "trade_message_types": [
        "объявление о проведении торгов",
        "сообщение о торгах",
        "торги",
    ],

    # Пагинация (экономим запросы)
    "orgs_per_request": 20,       # организаций за один search_ur
    "msgs_per_request": 20,       # сообщений за один get_org_messages

    # Лимиты
    "daily_limit": 30,            # ОТЛАДКА: минимум, поднять до 240 когда стабильно
    "request_delay": 2,           # секунд между запросами

    # Хранение статистики
    "usage_file": "/app/data/api_usage.json",
}
# ============================================================


class RequestCounter:
    """Счётчик запросов с дневным лимитом + сохранение в файл"""

    def __init__(self, storage_file: str):
        self.storage_file = storage_file
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r") as f:
                    data = json.load(f)
                    self.count = data.get("fedresurs_today", 0)
                    last_reset = data.get("last_reset", "")
                    # Сброс если новый день
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    if last_reset != today:
                        self.count = 0
            else:
                self.count = 0
        except Exception:
            self.count = 0

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            data = {
                "fedresurs_today": self.count,
                "last_reset": today,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Не могу сохранить счётчик: {e}")

    def can_request(self) -> bool:
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
                    timeout=aiohttp.ClientTimeout(total=30)
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

    async def get_trade_message_ids(self, org: dict) -> list:
        """
        Из сообщений организации выбрать только о торгах.
        Возвращает список id сообщений.
        """
        org_id = org.get("id")
        org_name = org.get("debtor", "Неизвестно")

        messages, total = await self._get_org_messages(org_id, from_record=0)

        if not messages:
            return []

        trade_ids = []
        self.stats["messages_checked"] += len(messages)

        for msg in messages:
            if self._is_trade_message(msg):
                trade_ids.append(msg["id"])

        # Если торгов нет на первой странице и сообщений больше — не листаем
        # (экономим запросы)
        if trade_ids:
            logger.info(
                f"🏢 {org_name[:40]}: "
                f"{len(trade_ids)} сообщений о торгах из {total}"
            )

        return trade_ids

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

        # Фильтр по ключевым словам
        found_keyword = next(
            (kw for kw in SEARCH_CONFIG["keywords"] if kw in text_to_search),
            None
        )
        if not found_keyword:
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
            return None

        if price > SEARCH_CONFIG["max_price"]:
            return None

        # Лот прошёл фильтры!
        return {
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

        # ШАГ 1: Все организации-банкроты Москвы
        orgs = await self.get_all_orgs()

        if not orgs:
            logger.error("❌ Нет организаций, останавливаемся")
            return []

        # ШАГ 2 + 3: Для каждой организации — торги — лоты
        for idx, org in enumerate(orgs):

            if not self.counter.can_request():
                logger.warning(
                    f"⚠️ Лимит запросов! Обработано {idx}/{len(orgs)} организаций. "
                    f"Продолжим завтра."
                )
                break

            # Сообщения о торгах этой организации
            trade_msg_ids = await self.get_trade_message_ids(org)

            if not trade_msg_ids:
                continue

            self.stats["trade_messages_found"] += len(trade_msg_ids)

            # Детали каждого сообщения о торгах
            for msg_id in trade_msg_ids:

                if not self.counter.can_request():
                    break

                message = await self.get_message_details(msg_id)

                if not message:
                    continue

                lots = message.get("lots", [])
                self.stats["lots_found"] += len(lots)

                # Фильтрация лотов
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

        # Итоги
        logger.info("=" * 60)
        logger.info("📊 ИТОГИ ПОИСКА:")
        logger.info(f"   Организаций проверено:     {self.stats['orgs_found']}")
        logger.info(f"   Сообщений проверено:       {self.stats['messages_checked']}")
        logger.info(f"   Сообщений о торгах:        {self.stats['trade_messages_found']}")
        logger.info(f"   Лотов всего:               {self.stats['lots_found']}")
        logger.info(f"   Лотов после фильтра:       {self.stats['lots_passed_filter']}")
        logger.info(f"   Запросов потрачено:        {self.stats['requests_made']}")
        logger.info(f"   Осталось на сегодня:       {self.counter.remaining}")
        logger.info("=" * 60)

        return result_lots

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