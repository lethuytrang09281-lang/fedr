"""
Тест FedresursSearchService с mock данными

Использование:
    python test_fedresurs_search.py
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from src.services.fedresurs_search import FedresursSearchService
from src.services.external_api import ParserAPIClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Mock данные для тестирования
MOCK_ORGANIZATIONS = [
    {
        "id": "org_001",
        "debtor": "ООО 'Стройинвест Плюс'",
        "inn": "7701234567",
        "address": "г. Москва, ул. Тверская, д. 10"
    },
    {
        "id": "org_002",
        "debtor": "ОАО 'Московская недвижимость'",
        "inn": "7702345678",
        "address": "г. Москва, Садовое кольцо, д. 5"
    },
    {
        "id": "org_003",
        "debtor": "ЗАО 'Торговый дом Центр'",
        "inn": "7703456789",
        "address": "г. Москва, ул. Арбат, д. 15"
    }
]

MOCK_MESSAGES = {
    "org_001": [
        {
            "id": "msg_001_1",
            "type": "Объявление о проведении торгов",
            "date": "2026-02-10"
        },
        {
            "id": "msg_001_2",
            "type": "Сообщение о результатах торгов",
            "date": "2026-02-12"
        }
    ],
    "org_002": [
        {
            "id": "msg_002_1",
            "type": "Объявление о проведении торгов",
            "date": "2026-02-08"
        }
    ],
    "org_003": []  # Нет торгов
}

MOCK_TRADE_DETAILS = {
    "msg_001_1": {
        "trade_type": "Публичное предложение",
        "trade_app_start_date": "2026-02-15",
        "trade_app_end_date": "2026-03-15",
        "lots": [
            {
                "num": "1",
                "description": "Административное здание, общей площадью 500 кв.м, расположенное по адресу: г. Москва, ул. Тверская, д. 10",
                "start_price": "150000000",  # 150M - проходит фильтр
                "step": "5000000",
                "deposit": "15000000",
                "type": "Недвижимое имущество"
            },
            {
                "num": "2",
                "description": "Земельный участок для садоводства, 10 соток",
                "start_price": "5000000",  # Не проходит фильтр по ключевым словам
                "step": "250000",
                "deposit": "500000",
                "type": "Земельный участок"
            }
        ]
    },
    "msg_002_1": {
        "trade_type": "Аукцион",
        "trade_app_start_date": "2026-02-20",
        "trade_app_end_date": "2026-03-20",
        "lots": [
            {
                "num": "1",
                "description": "Офисное здание класса B+, 1200 кв.м, в центре Москвы",
                "start_price": "280000000",  # 280M - проходит фильтр
                "step": "10000000",
                "deposit": "28000000",
                "type": "Недвижимое имущество"
            }
        ]
    },
    "msg_001_2": {
        "trade_type": "Результаты торгов",
        "lots": []  # Нет лотов
    }
}


async def create_mock_api_client():
    """Создать mock ParserAPIClient"""
    mock_client = AsyncMock(spec=ParserAPIClient)

    # Mock search_ur
    async def mock_search_ur(org_region_id=77, from_record=0):
        # Простая пагинация: возвращаем все организации на первой странице
        if from_record == 0:
            return {
                "count": len(MOCK_ORGANIZATIONS),
                "result": MOCK_ORGANIZATIONS
            }
        return {"count": 0, "result": []}

    # Mock get_org_messages
    async def mock_get_org_messages(org_id, from_record=0):
        messages = MOCK_MESSAGES.get(org_id, [])
        if from_record == 0:
            return {
                "count": len(messages),
                "result": messages
            }
        return {"count": 0, "result": []}

    # Mock get_message
    async def mock_get_message(message_id):
        return MOCK_TRADE_DETAILS.get(message_id, {"lots": []})

    mock_client.search_ur = mock_search_ur
    mock_client.get_org_messages = mock_get_org_messages
    mock_client.get_message = mock_get_message

    return mock_client


async def test_search():
    """Тестирование полного цикла поиска"""
    logger.info("=" * 60)
    logger.info("ТЕСТ: FedresursSearchService с mock данными")
    logger.info("=" * 60)

    # Создаем сервис
    service = FedresursSearchService(
        region_id=77,
        max_price=300_000_000,
        keywords=["здание", "офис", "административное", "торговый центр"]
    )

    # Подменяем API клиент на mock
    service.api_client = await create_mock_api_client()

    # Убираем задержки для быстрого теста
    service.request_delay = 0

    # Запускаем поиск
    lots = await service.run_full_search(
        max_orgs=10,
        max_orgs_with_messages=10
    )

    # Проверка результатов
    logger.info("")
    logger.info("=" * 60)
    logger.info("РЕЗУЛЬТАТЫ ТЕСТА")
    logger.info("=" * 60)

    assert len(lots) == 2, f"Ожидалось 2 лота, получено {len(lots)}"
    logger.info(f"✅ Найдено лотов: {len(lots)}")

    # Проверяем первый лот
    lot1 = lots[0]
    assert "Административное здание" in lot1["description"]
    assert lot1["start_price"] == "150000000"
    assert lot1["org_inn"] == "7701234567"
    logger.info(f"✅ Лот 1: {lot1['description'][:50]}... - {lot1['start_price']} ₽")

    # Проверяем второй лот
    lot2 = lots[1]
    assert "Офисное здание" in lot2["description"]
    assert lot2["start_price"] == "280000000"
    assert lot2["org_inn"] == "7702345678"
    logger.info(f"✅ Лот 2: {lot2['description'][:50]}... - {lot2['start_price']} ₽")

    # Проверяем статистику
    logger.info("")
    logger.info("Проверка статистики:")
    assert service.stats["orgs_scanned"] == 3, "Должно быть просканировано 3 организации"
    logger.info(f"  ✅ Организаций: {service.stats['orgs_scanned']}")

    assert service.stats["lots_found"] == 3, "Всего должно быть найдено 3 лота"
    logger.info(f"  ✅ Лотов найдено: {service.stats['lots_found']}")

    assert service.stats["lots_filtered"] == 2, "После фильтров должно остаться 2 лота"
    logger.info(f"  ✅ Лотов после фильтров: {service.stats['lots_filtered']}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    logger.info("=" * 60)


async def test_filters():
    """Тест фильтров"""
    logger.info("")
    logger.info("ТЕСТ: Проверка фильтров")

    service = FedresursSearchService()

    # Тест фильтра ключевых слов
    assert service._filter_lot_by_keywords("Административное здание в центре")
    assert service._filter_lot_by_keywords("МКД 5 этажей")
    assert service._filter_lot_by_keywords("Офисное помещение")
    assert not service._filter_lot_by_keywords("Земельный участок для садоводства")
    logger.info("  ✅ Фильтр ключевых слов работает")

    # Тест фильтра цены
    assert service._filter_lot_by_price("150000000")
    assert service._filter_lot_by_price("299999999")
    assert not service._filter_lot_by_price("350000000")
    logger.info("  ✅ Фильтр цены работает")


if __name__ == "__main__":
    async def main():
        await test_filters()
        await test_search()

    asyncio.run(main())
