import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.client.api import EfrsbClient
from src.services.xml_parser import XMLParserService
from src.database.models import Trade, Lot


async def main():
    client = EfrsbClient()

    try:
        # Пример получения данных за последний день
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        response = await client.get_trade_messages(start_date, end_date)
        print(f"Получено {response.total} сообщений")

        # Обработка каждого сообщения
        for message in response.pageItems:
            print(f"\nОбработка сообщения: {message.number}, тип: {message.type}")
            print(f"Дата публикации: {message.datePublish}")

            # Используем XML-парсер для обработки содержимого
            try:
                trade, lots = XMLParserService.parse_xml_content(message.content)

                print(f"  Обработано: Торги №{trade.trade_number}")
                print(f"  Найдено лотов: {len(lots)}")

                for i, lot in enumerate(lots):
                    print(f"    Лот {lot.lot_number}: {lot.description[:60]}..., Цена: {lot.start_price}")

            except Exception as e:
                print(f"  Ошибка при парсинге XML: {str(e)}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())