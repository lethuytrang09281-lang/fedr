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

        # Используем обновленный метод для поиска всех типов сообщений
        response = await client.search_messages(start_date, end_date)
        print(f"Получено {response.total} сообщений")

        # Обработка каждого сообщения
        for message in response.pageItems:
            print(f"\nОбработка сообщения: {message.number}, тип: {message.type}")
            print(f"Дата публикации: {message.datePublish}")

            # Используем обновленный XML-парсер для обработки содержимого
            try:
                parser = XMLParserService()
                lots_data = parser.parse_content(message.content, str(message.guid))

                print(f"  Найдено лотов: {len(lots_data)}")

                for i, lot_data in enumerate(lots_data):
                    print(f"    Лот: {lot_data.description[:60]}..., Цена: {lot_data.start_price}, Классификатор: {lot_data.classifier_code}")

            except Exception as e:
                print(f"  Ошибка при парсинге XML: {str(e)}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())