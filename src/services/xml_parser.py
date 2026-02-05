from typing import List, Tuple, Optional
from lxml import etree
from src.database.models import Lot
from src.parser.schemas import LotData, PriceScheduleDTO
from datetime import datetime, timezone
import logging
import re
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class XMLParserService:
    """
    Сервис для парсинга XML-данных из ЕФРСБ и преобразования их в объекты Trade и Lot
    """

    def parse_content(self, xml_content: str, message_guid: str) -> tuple[List[LotData], List[PriceScheduleDTO]]:
        if not xml_content:
            return [], []

        if xml_content.startswith("<?xml"):
            xml_content = xml_content.split("?>", 1)[-1]

        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            logger.error(f"XML Error parsing {message_guid}: {e}")
            return [], []

        # Очистка namespaces
        for elem in root.getiterator():
            if not hasattr(elem.tag, 'find'): continue
            i = elem.tag.find('}')
            if i >= 0:
                elem.tag = elem.tag[i+1:]

        lots_data = []
        price_schedules = []

        # ЗАДАЧА 1: Проверка на санкции (скрытые данные)
        # Ищем текст в PublisherName или Participant
        is_restricted_msg = False
        restricted_pattern = "постановления Правительства РФ от 12.01.2018 г. №5"
        
        publisher = root.findtext(".//PublisherName") or ""
        if restricted_pattern in publisher:
            is_restricted_msg = True
            
        # Также проверяем участников, если они есть
        if not is_restricted_msg:
            participants = root.xpath(".//Participant")
            for p in participants:
                if restricted_pattern in (p.text or ""):
                    is_restricted_msg = True
                    break

        lot_nodes = root.xpath(".//AuctionLot") + root.xpath(".//Lot")

        for lot_node in lot_nodes:
            try:
                description = lot_node.findtext("Description") or lot_node.findtext("TradeObjectHtml") or ""
                
                # Классификатор
                classifier_code = ""
                classifier_node = lot_node.find("Classifier")
                if classifier_node is not None:
                    classifier_code = classifier_node.findtext("Code") or ""

                # ЗАДАЧА 3: Фильтрация (отсеиваем мусор)
                # Если это не целевой лот, пропускаем (если нужно экономить место в БД)
                # if not self._is_target_lot(description, classifier_code):
                #    continue 

                price_str = lot_node.findtext("StartPrice") or "0"
                try:
                    price = float(price_str.replace(',', '.'))
                except ValueError:
                    price = 0.0

                cadastral_numbers = self._extract_cadastral_numbers(description)

                schedule_html = self._extract_schedule_html(lot_node)

                lot = LotData(
                    description=description,
                    start_price=price,
                    cadastral_numbers=cadastral_numbers,
                    message_guid=message_guid,
                    classifier_code=classifier_code,
                    lot_number=1,
                    is_restricted=is_restricted_msg
                )
                
                lots_data.append(lot)

                if schedule_html:
                    schedule_dto = PriceScheduleDTO(
                        lot_id=hash(f"{message_guid}_{len(lots_data)}") % 1000000,
                        date_start=datetime.now(timezone.utc),
                        date_end=datetime.now(timezone.utc),
                        price=price,
                        schedule_html=schedule_html
                    )
                    price_schedules.append(schedule_dto)

            except Exception as e:
                logger.error(f"Error parsing lot in {message_guid}: {e}")
                continue

        return lots_data, price_schedules

    def _extract_schedule_html(self, lot_node) -> str:
        """
        Извлекает HTML-график снижения цены из узла лота
        """
        # Ищем возможные теги, содержащие график
        schedule_tags = ["PublicOfferSchedule", "Schedule", "PriceReductionSchedule", "PriceSchedule"]

        for tag_name in schedule_tags:
            schedule_node = lot_node.find(tag_name)
            if schedule_node is not None:
                # Извлекаем HTML-содержимое (часто в CDATA или вложенных тегах)
                html_content = etree.tostring(schedule_node, encoding='unicode', method='html')
                return html_content

        # Также проверяем наличие вложенных HTML-таблиц
        table_nodes = lot_node.xpath(".//table[contains(@class, 'schedule') or contains(@class, 'price')]")
        if table_nodes:
            html_content = "".join([etree.tostring(table, encoding='unicode', method='html') for table in table_nodes])
            return html_content

        return ""
    
    def _detect_hidden_data(self, xml_content: str) -> bool:
        """
        Обнаруживает скрытые данные по Постановлению №5
        Возвращает True, если в полях PublisherName или Participant встречается текст
        "Сведения скрыты в соответствии с требованиями постановления Правительства РФ от 12.01.2018 г. №5"
        """
        hidden_text = "Сведения скрыты в соответствии с требованиями постановления Правительства РФ от 12.01.2018 г. №5"
        return hidden_text in xml_content
    
    def parse_public_offer_price(self, html_content: str) -> Optional[float]:
        """
        Парсинг графика цены (Публичное предложение)
        Возвращает актуальную цену на текущую дату из HTML-таблицы в теге <PriceReduction>
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Ищем таблицу с графиком снижения цены
            table = soup.find('table')
            if not table:
                return None
            
            # Парсим строки таблицы
            rows = table.find_all('tr')
            if len(rows) < 2:  # заголовок + минимум одна строка
                return None
            
            current_date = datetime.now(timezone.utc)
            current_price = None
            
            for row in rows[1:]:  # пропускаем заголовок
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:  # ожидаем дата начала, дата окончания, цена
                    try:
                        # Парсим даты
                        date_start_str = cells[0].get_text(strip=True)
                        date_end_str = cells[1].get_text(strip=True)
                        
                        # Парсим даты (упрощенный парсинг)
                        date_start = self._parse_simple_date(date_start_str)
                        date_end = self._parse_simple_date(date_end_str)
                        
                        if date_start and date_end and date_start <= current_date <= date_end:
                            price_str = cells[2].get_text(strip=True)
                            # Очистка цены
                            price_clean = re.sub(r'[^\d.,]', '', price_str)
                            price_clean = price_clean.replace(',', '.')
                            try:
                                current_price = float(price_clean)
                                break  # нашли текущий интервал
                            except ValueError:
                                continue
                    except Exception:
                        continue
            
            return current_price
        except Exception as e:
            logger.error(f"Error parsing public offer price: {e}")
            return None
    
    def _parse_simple_date(self, date_str: str) -> Optional[datetime]:
        """
        Упрощенный парсинг даты из строки
        """
        date_formats = [
            '%d.%m.%Y',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d.%m.%y',
        ]
        
        # Очищаем строку от лишних символов
        date_str = re.sub(r'[^\d./\-]', '', date_str).strip()
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Добавляем часовой пояс UTC, если дата naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        return None
    
    def is_target_lot(self, description: str, classifier_code: str) -> bool:
        """
        Семантический фильтр (Земля и МКД)
        Возвращает True, если лот соответствует целевым критериям
        """
        # Целевые коды классификатора
        target_codes = {'0108001', '0402006', '0101014'}
        
        # Проверяем код классификатора
        if classifier_code not in target_codes:
            return False
        
        # Ищем ключевые слова в описании
        description_lower = description.lower()
        keywords = [
            r"многоквартирн",
            r"жилая застройка",
            r"мкд",
            r"высотная",
            r"жилое здание",
            r"многоквартирный дом"
        ]
        
        # Проверяем наличие ключевых слов
        has_keywords = any(re.search(keyword, description_lower) for keyword in keywords)
        if not has_keywords:
            return False
        
        # Исключаем стоп-слова
        stop_words = ["снт", "лпх", "огород", "садовый", "дачный", "земли сельхозназначения"]
        has_stop_words = any(stop_word in description_lower for stop_word in stop_words)
        
        return not has_stop_words
    
    def _is_target_lot(self, description: str, classifier_code: str) -> bool:
        """
        Фильтр целевых лотов (Земля, МКД, Недострой)
        """
        target_codes = ['0108001', '0402006', '0101014'] # Земля, Аренда земли, Недострой
        stop_words = ["снт", "лпх", "огород", "дача"]
        target_keywords = ["многоквартирн", "жилая застройка", "мкд", "высотная", "блокированная"]
        
        description_lower = description.lower()

        # 1. Проверка стоп-слов
        if any(word in description_lower for word in stop_words):
            return False

        # 2. Проверка по коду
        if classifier_code in target_codes:
            return True

        # 3. Проверка по ключевым словам (если код не подошел или отсутствует)
        if any(kw in description_lower for kw in target_keywords):
            return True

        return False

    def _extract_cadastral_numbers(self, text: str) -> List[str]:
        """
        Извлекает кадастровые номера из текста с помощью Regex
        Шаблон: \d{2}:\d{2}:\d{3,7}:\d+
        """
        pattern = r'\d{2}:\d{2}:\d{3,7}:\d+'
        return re.findall(pattern, text)
