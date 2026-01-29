from typing import List
from lxml import etree
from src.database.models import Lot
from src.schemas import LotData
from datetime import datetime
import logging
import re


logger = logging.getLogger(__name__)


class XMLParserService:
    """
    Сервис для парсинга XML-данных из ЕФРСБ и преобразования их в объекты Trade и Lot
    """

    def parse_content(self, xml_content: str, message_guid: str) -> List[LotData]:
        """
        Парсит XML контент (игнорируя namespaces для надежности).
        """
        if not xml_content:
            return []

        # Удаляем declaration (<?xml...?>) если есть, чтобы lxml не ругался на кодировку
        if xml_content.startswith("<?xml"):
            xml_content = xml_content.split("?>", 1)[-1]

        try:
            # Парсим байты, чтобы lxml сам разобрался с кодировкой (обычно utf-8)
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            logger.error(f"XML Error parsing {message_guid}: {e}")
            return []

        # Стратегия очистки namespaces (самый надежный способ для Федресурса)
        for elem in root.getiterator():
            if not hasattr(elem.tag, 'find'): continue  # skip comments
            i = elem.tag.find('}')
            if i >= 0:
                elem.tag = elem.tag[i+1:]

        lots_data = []

        # 1. Ищем лоты. В разных типах сообщений они лежат по-разно
        # Обычно это LotTable/AuctionLot или LotList/Lot

        # XPath: ищем любой тег AuctionLot или Lot на любой глубине
        lot_nodes = root.xpath(".//AuctionLot") + root.xpath(".//Lot")

        for lot_node in lot_nodes:
            try:
                description = lot_node.findtext("Description") or lot_node.findtext("TradeObjectHtml") or ""

                # Обработка цены (StartPrice)
                price_str = lot_node.findtext("StartPrice") or "0"
                try:
                    price = float(price_str.replace(',', '.'))
                except ValueError:
                    price = 0.0

                # Ищем кадастровые номера в тексте (простой поиск для MVP)
                # Позже сюда можно подключить Regex
                cadastral_numbers = []

                # Классификатор (важно для фильтрации Земли)
                classifier_code = ""
                classifier_node = lot_node.find("Classifier")
                if classifier_node is not None:
                    classifier_code = classifier_node.findtext("Code")

                # Собираем объект
                lot = LotData(
                    description=description,
                    start_price=price,
                    cadastral_numbers=cadastral_numbers, # Пока пустой список, добавим Regex позже
                    message_guid=message_guid,
                    classifier_code=classifier_code,
                    lot_number=1  # По умолчанию
                )
                lots_data.append(lot)

            except Exception as e:
                logger.error(f"Error parsing lot in {message_guid}: {e}")
                continue

        return lots_data