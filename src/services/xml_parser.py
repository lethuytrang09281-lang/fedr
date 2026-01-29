from typing import List
from lxml import etree
from src.database.models import Trade, Lot
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
                    classifier_code=classifier_code
                )
                lots_data.append(lot)

            except Exception as e:
                logger.error(f"Error parsing lot in {message_guid}: {e}")
                continue

        return lots_data
    
    @staticmethod
    def parse_xml_content(xml_content: str) -> tuple[Trade, List[Lot]]:
        """
        Парсит XML-контент и возвращает объект Trade и список объектов Lot
        
        Args:
            xml_content: Строка XML-контента из поля content
            
        Returns:
            Кортеж из объекта Trade и списка объектов Lot
        """
        # Преобразуем строку XML в дерево элементов
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Определяем тип сообщения
        message_type = root.get('type') or root.tag
        
        # Извлекаем общую информацию о торгах
        trade_info = XMLParserService._extract_trade_info(root, message_type)
        
        # Извлекаем информацию о лотах
        lots = XMLParserService._extract_lots_info(root, message_type)
        
        # Создаем объект Trade
        trade = Trade(
            guid=trade_info['guid'],
            trade_number=trade_info['trade_number'],
            platform_name=trade_info['platform_name'],
            publish_date=trade_info['publish_date'],
            is_annulled=trade_info['is_annulled']
        )
        
        return trade, lots
    
    @staticmethod
    def _extract_trade_info(root, message_type: str) -> dict:
        """
        Извлекает информацию о торгах из XML
        
        Args:
            root: Корневой элемент XML
            message_type: Тип сообщения (BiddingInvitation или Auction2)
            
        Returns:
            Словарь с информацией о торгах
        """
        # Инициализируем значения по умолчанию
        trade_info = {
            'guid': None,
            'trade_number': None,
            'platform_name': None,
            'publish_date': datetime.utcnow(),
            'is_annulled': False
        }
        
        # В зависимости от типа сообщения извлекаем соответствующие данные
        if message_type.lower() == 'biddinginvitation':
            # Для типа BiddingInvitation
            trade_info['trade_number'] = root.xpath('//notificationNumber/text() | //tradeNumber/text()')
            if trade_info['trade_number']:
                trade_info['trade_number'] = trade_info['trade_number'][0][:50]  # Ограничение по длине
            
            # Ищем дату публикации
            publish_dates = root.xpath('//publishDate/text() | //createDate/text()')
            if publish_dates:
                try:
                    trade_info['publish_date'] = datetime.fromisoformat(publish_dates[0].replace('Z', '+00:00'))
                except ValueError:
                    # Если формат даты не подходит, используем текущую дату
                    pass
                    
        elif message_type.lower() == 'auction2':
            # Для типа Auction2
            trade_info['trade_number'] = root.xpath('//tradeNumber/text() | //number/text()')
            if trade_info['trade_number']:
                trade_info['trade_number'] = trade_info['trade_number'][0][:50]  # Ограничение по длине
                
            # Ищем дату публикации
            publish_dates = root.xpath('//publishDate/text() | //createDate/text()')
            if publish_dates:
                try:
                    trade_info['publish_date'] = datetime.fromisoformat(publish_dates[0].replace('Z', '+00:00'))
                except ValueError:
                    # Если формат даты не подходит, используем текущую дату
                    pass
        
        return trade_info
    
    @staticmethod
    def _extract_lots_info(root, message_type: str) -> List[Lot]:
        """
        Извлекает информацию о лотах из XML
        
        Args:
            root: Корневой элемент XML
            message_type: Тип сообщения (BiddingInvitation или Auction2)
            
        Returns:
            Список объектов Lot
        """
        lots = []
        
        # В зависимости от типа сообщения ищем лоты по разным XPath
        if message_type.lower() == 'biddinginvitation':
            # Поиск лотов для BiddingInvitation
            lot_elements = root.xpath('//lot | //lots/lot | //item')
        elif message_type.lower() == 'auction2':
            # Поиск лотов для Auction2
            lot_elements = root.xpath('//lot | //lots/lot | //item')
        else:
            # Общий случай
            lot_elements = root.xpath('//lot | //lots/lot | //item')
        
        for idx, lot_element in enumerate(lot_elements):
            lot_info = XMLParserService._parse_lot_element(lot_element, idx + 1)
            
            lot = Lot(
                lot_number=lot_info['lot_number'],
                description=lot_info['description'],
                start_price=lot_info['start_price'],
                status=lot_info['status']
            )
            
            lots.append(lot)
        
        return lots
    
    @staticmethod
    def _parse_lot_element(lot_element, lot_number: int) -> dict:
        """
        Парсит отдельный элемент лота
        
        Args:
            lot_element: Элемент лота из XML
            lot_number: Номер лота
            
        Returns:
            Словарь с информацией о лоте
        """
        lot_info = {
            'lot_number': lot_number,
            'description': '',
            'start_price': None,
            'status': None
        }
        
        # Извлекаем описание лота
        descriptions = lot_element.xpath('.//description/text() | .//name/text() | .//subject/text() | .//info/text()')
        if descriptions:
            lot_info['description'] = descriptions[0][:255]  # Ограничение по длине
            
            # Проверяем наличие ключевых слов "МКД" и "Земля"
            desc_lower = lot_info['description'].lower()
            if 'мкд' in desc_lower or 'жилой фонд' in desc_lower or 'жилое помещение' in desc_lower:
                # Добавляем категоризацию к описанию
                lot_info['description'] = f"[Категория: Жилая недвижимость] {lot_info['description']}"
            elif 'земля' in desc_lower or 'земельный участок' in desc_lower:
                # Добавляем категоризацию к описанию
                lot_info['description'] = f"[Категория: Земельный участок] {lot_info['description']}"
        
        # Извлекаем стартовую цену
        prices = lot_element.xpath('.//startPrice/text() | .//initialPrice/text() | .//price/text()')
        if prices:
            try:
                lot_info['start_price'] = float(prices[0])
            except ValueError:
                # Если цена не является числом, пропускаем
                pass
        
        # Извлекаем статус
        statuses = lot_element.xpath('.//status/text() | .//state/text()')
        if statuses:
            lot_info['status'] = statuses[0][:100]  # Ограничение по длине
        
        return lot_info