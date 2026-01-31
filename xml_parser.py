"""
FEDRESURS RADAR - XML Parser
Извлечение структурированных данных из XML-контента сообщений
"""

import re
from typing import Optional, List, Dict, Any
from lxml import etree
from loguru import logger

from src.config import settings


class XMLParser:
    """
    Парсер XML-сообщений ЕФРСБ
    
    Поддерживаемые типы:
    - Auction2 (сообщения АУ)
    - BiddingInvitation (сообщения ЭТП)
    - PropertyInventoryResult (инвентаризация)
    - MeetingResult (собрания кредиторов)
    """
    
    # Regex для извлечения кадастровых номеров
    CADASTRAL_NUMBER_PATTERN = re.compile(r'\b\d{2}:\d{2}:\d{3,7}:\d+\b')
    
    def __init__(self):
        self.target_codes = set(settings.land_codes + settings.building_codes)
        self.include_keywords = settings.include_keywords
        self.exclude_keywords = settings.exclude_keywords
    
    def parse_message(self, xml_content: str, message_type: str) -> Optional[Dict[str, Any]]:
        """
        Универсальный метод парсинга сообщения
        
        Args:
            xml_content: XML-строка из поля content
            message_type: Тип сообщения (BiddingInvitation, Auction2, etc.)
        
        Returns:
            Dict с извлечёнными данными или None
        """
        try:
            # Очистка от CDATA и пустых namespaces
            xml_content = self._clean_xml(xml_content)
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Выбор стратегии парсинга по типу
            if message_type in ["BiddingInvitation", "BiddingInvitation2"]:
                return self._parse_etp_message(root)
            elif message_type in ["Auction", "Auction2"]:
                return self._parse_au_message(root)
            elif message_type == "PropertyInventoryResult":
                return self._parse_inventory(root)
            else:
                logger.debug(f"Unsupported message type: {message_type}")
                return None
                
        except etree.XMLSyntaxError as e:
            logger.error(f"XML parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected parsing error: {e}")
            return None
    
    def _clean_xml(self, xml: str) -> str:
        """Очистка XML от артефактов"""
        # Удаление CDATA обёрток
        xml = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', xml, flags=re.DOTALL)
        # Удаление пустых namespace declarations
        xml = re.sub(r'xmlns:\w+=""', '', xml)
        return xml
    
    def _parse_etp_message(self, root: etree._Element) -> Dict[str, Any]:
        """
        Парсинг сообщения с ЭТП (BiddingInvitation)
        
        Структура:
        <BiddingInvitation>
            <LotList>
                <Lot>
                    <Number>1</Number>
                    <StartPrice>1000000</StartPrice>
                    <TradeObjectHtml>...</TradeObjectHtml>
                </Lot>
            </LotList>
        </BiddingInvitation>
        """
        result = {
            "trade_type": self._get_text(root, ".//TradeType") or "Unknown",
            "lots": []
        }
        
        # Извлечение лотов
        lot_list = root.find(".//LotList")
        if lot_list is None:
            return result
        
        for lot_elem in lot_list.findall(".//Lot"):
            lot = self._extract_lot_data(lot_elem)
            if lot and self._filter_lot(lot):
                result["lots"].append(lot)
        
        return result if result["lots"] else None
    
    def _parse_au_message(self, root: etree._Element) -> Dict[str, Any]:
        """
        Парсинг сообщения АУ (Auction2)
        
        Структура:
        <Auction2>
            <LotTable>
                <AuctionLot>
                    <Order>1</Order>
                    <StartPrice>1000000</StartPrice>
                    <Description>...</Description>
                </AuctionLot>
            </LotTable>
        </Auction2>
        """
        result = {
            "trade_type": self._get_text(root, ".//TradeType") or "Auction",
            "lots": []
        }
        
        # Извлечение лотов
        lot_table = root.find(".//LotTable")
        if lot_table is None:
            return result
        
        for lot_elem in lot_table.findall(".//AuctionLot"):
            lot = self._extract_lot_data(lot_elem, is_au=True)
            if lot and self._filter_lot(lot):
                result["lots"].append(lot)
        
        return result if result["lots"] else None
    
    def _parse_inventory(self, root: etree._Element) -> Dict[str, Any]:
        """
        Парсинг инвентаризации (Shift Left стратегия)
        
        Ищем имущество на ранней стадии (до торгов)
        """
        result = {
            "trade_type": "Inventory",
            "lots": []
        }
        
        # Поиск блоков имущества
        for inventory in root.findall(".//InventoryByDebtor") + root.findall(".//InventoryByFinanceManager"):
            for item in inventory.findall(".//Item"):
                description = self._get_text(item, ".//Name") or self._get_text(item, ".//Description")
                address = self._get_text(item, ".//Address")
                value = self._get_text(item, ".//Value")
                
                if description:
                    lot = {
                        "lot_number": 0,  # Инвентаризация не имеет номеров лотов
                        "description": description,
                        "address": address,
                        "start_price": self._parse_decimal(value),
                        "cadastral_numbers": self.extract_cadastral_numbers(description),
                        "category_code": None
                    }
                    
                    if self._filter_lot(lot):
                        result["lots"].append(lot)
        
        return result if result["lots"] else None
    
    def _extract_lot_data(self, lot_elem: etree._Element, is_au: bool = False) -> Dict[str, Any]:
        """
        Извлечение данных лота (универсальная функция)
        
        Args:
            lot_elem: XML элемент лота
            is_au: True для Auction2, False для BiddingInvitation
        """
        # Номер лота
        lot_number = self._get_text(lot_elem, ".//Order" if is_au else ".//Number")
        
        # Описание
        if is_au:
            description = self._get_text(lot_elem, ".//Description")
        else:
            description = self._get_text(lot_elem, ".//TradeObjectHtml")
            if not description:
                description = self._get_text(lot_elem, ".//Description")
        
        # Адрес
        address = self._get_text(lot_elem, ".//Location") or self._get_text(lot_elem, ".//Address")
        
        # Цены
        start_price = self._get_text(lot_elem, ".//StartPrice")
        step_price = self._get_text(lot_elem, ".//StepPrice") or self._get_text(lot_elem, ".//Step")
        advance = self._get_text(lot_elem, ".//Advance")
        
        # Классификатор
        classifier_code = self._get_text(lot_elem, ".//Classifier/Code") or \
                         self._get_text(lot_elem, ".//AuctionLotClassifier/Code")
        
        # Кадастровые номера
        full_text = (description or "") + " " + (address or "")
        cadastral_numbers = self.extract_cadastral_numbers(full_text)
        
        return {
            "lot_number": int(lot_number) if lot_number else 0,
            "description": description,
            "address": address,
            "start_price": self._parse_decimal(start_price),
            "step_price": self._parse_decimal(step_price),
            "advance": self._parse_decimal(advance),
            "category_code": classifier_code,
            "cadastral_numbers": cadastral_numbers
        }
    
    def _filter_lot(self, lot: Dict[str, Any]) -> bool:
        """
        Фильтрация лота по семантическому ядру
        
        Проверки:
        1. Код классификатора (0108001, 0402006, etc.)
        2. Ключевые слова (include)
        3. Стоп-слова (exclude)
        """
        # Фильтр 1: Код классификатора
        if lot.get("category_code") and lot["category_code"] in self.target_codes:
            logger.debug(f"Lot matched by classifier code: {lot['category_code']}")
            # Даже при совпадении кода проверяем стоп-слова
            pass
        
        # Фильтр 2: Текстовый поиск
        text = (lot.get("description") or "").lower()
        
        # Проверка стоп-слов (отсев мусора)
        for exclude_word in self.exclude_keywords:
            if exclude_word in text:
                logger.debug(f"Lot excluded by stop-word: {exclude_word}")
                return False
        
        # Проверка include-слов ИЛИ код подошёл
        if lot.get("category_code") in self.target_codes:
            return True
        
        for include_word in self.include_keywords:
            if include_word in text:
                logger.debug(f"Lot matched by keyword: {include_word}")
                return True
        
        return False
    
    def extract_cadastral_numbers(self, text: str) -> List[str]:
        """
        Извлечение кадастровых номеров через Regex
        
        Паттерн: XX:XX:XXXXXXX:XXX (77:01:0001001:123)
        """
        if not text:
            return []
        
        matches = self.CADASTRAL_NUMBER_PATTERN.findall(text)
        # Дедупликация
        return list(set(matches))
    
    def _get_text(self, element: etree._Element, xpath: str) -> Optional[str]:
        """Безопасное извлечение текста по XPath"""
        try:
            found = element.find(xpath)
            if found is not None and found.text:
                return found.text.strip()
        except Exception:
            pass
        return None
    
    def _parse_decimal(self, value: Optional[str]) -> Optional[float]:
        """Парсинг денежных значений"""
        if not value:
            return None
        try:
            # Удаление пробелов и замена запятой на точку
            value = value.replace(" ", "").replace(",", ".")
            return float(value)
        except (ValueError, AttributeError):
            return None


# ============================================================================
# Quick Test
# ============================================================================

if __name__ == "__main__":
    # Тестовый XML (Auction2)
    test_xml = """
    <Auction2>
        <TradeType>Auction</TradeType>
        <LotTable>
            <AuctionLot>
                <Order>1</Order>
                <StartPrice>5000000.00</StartPrice>
                <Description>Земельный участок под строительство многоквартирного жилого дома, 
                кадастровый номер 77:01:0001001:456, зона Ж-1, площадь 2000 кв.м</Description>
                <Classifier>
                    <Code>0108001</Code>
                </Classifier>
            </AuctionLot>
        </LotTable>
    </Auction2>
    """
    
    parser = XMLParser()
    result = parser.parse_message(test_xml, "Auction2")
    
    print("=== XML Parser Test ===")
    print(f"Lots found: {len(result['lots']) if result else 0}")
    if result and result['lots']:
        lot = result['lots'][0]
        print(f"Lot #: {lot['lot_number']}")
        print(f"Price: {lot['start_price']:,.0f} RUB")
        print(f"Category: {lot['category_code']}")
        print(f"Cadastral: {lot['cadastral_numbers']}")
        print(f"Description: {lot['description'][:100]}...")
