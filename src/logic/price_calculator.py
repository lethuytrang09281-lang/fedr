from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
import re
from bs4 import BeautifulSoup
from src.schemas import PriceCalculationResult


class PriceCalculator:
    """
    Калькулятор цены на основе графика снижения цены
    """
    
    @staticmethod
    def parse_public_offer_price(html_content: str) -> Optional[float]:
        """
        Парсинг графика цены (Публичное предложение)
        Возвращает актуальную цену на текущую дату из HTML-таблицы в теге <PriceReduction>
        
        Алгоритм:
        1. Используй BeautifulSoup для парсинга HTML
        2. Найди таблицу
        3. Пройдись по строкам
        4. Найди интервал дат, в который попадает datetime.utcnow()
        5. Верни цену из этого интервала
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
                        date_start = PriceCalculator._parse_date(date_start_str)
                        date_end = PriceCalculator._parse_date(date_end_str)
                        
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
            # В случае ошибки парсинга возвращаем None
            return None
    
    @staticmethod
    def is_target_lot(description: str, classifier_code: str) -> bool:
        """
        Семантический фильтр (Земля и МКД)
        Возвращает True, если лот соответствует целевым критериям
        
        Логика:
        1. Проверяй коды классификатора: '0108001' (Земля), '0402006' (Право аренды), '0101014' (Недострой)
        2. Если код подходит, ищи в описании ключевые слова (Regex): 
           "многоквартирн*", "жилая застройка", "МКД", "высотная"
        3. Исключай стоп-слова: "СНТ", "ЛПХ", "огород"
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
    
    @staticmethod
    def detect_hidden_data(xml_content: str) -> bool:
        """
        Обработка "Скрытых данных" (Постановление №5)
        Возвращает True, если в полях PublisherName или Participant встречается текст
        "Сведения скрыты в соответствии с требованиями постановления Правительства РФ от 12.01.2018 г. №5"
        """
        hidden_text = "Сведения скрыты в соответствии с требованиями постановления Правительства РФ от 12.01.2018 г. №5"
        return hidden_text in xml_content
    
    @staticmethod
    def calculate_current_price(
        start_price: float,
        schedule_html: Optional[str],
        start_date: datetime,
        current_date: Optional[datetime] = None
    ) -> PriceCalculationResult:
        """
        Рассчитывает текущую цену на основе графика снижения цены
        
        Args:
            start_price: Начальная цена
            schedule_html: HTML-представление графика снижения цены
            start_date: Дата начала действия графика
            current_date: Текущая дата (если не указана, используется текущая дата)
            
        Returns:
            PriceCalculationResult: Результат расчета цены
        """
        if current_date is None:
            current_date = datetime.now(timezone.utc)
        
        # Если нет графика, возвращаем начальную цену
        if not schedule_html:
            return PriceCalculationResult(
                current_price=start_price,
                schedule_status="not_started"
            )
        
        # Парсим HTML-график
        try:
            soup = BeautifulSoup(schedule_html, 'html.parser')
            
            # Ищем таблицу с графиком снижения цены
            schedule_table = soup.find('table')
            if not schedule_table:
                return PriceCalculationResult(
                    current_price=start_price,
                    schedule_status="not_started"
                )
            
            # Извлекаем данные из таблицы
            schedule_data = PriceCalculator._parse_schedule_table(schedule_table)
            
            if not schedule_data:
                return PriceCalculationResult(
                    current_price=start_price,
                    schedule_status="not_started"
                )
            
            # Рассчитываем текущую цену на основе графика
            current_price, next_reduction_date = PriceCalculator._calculate_from_schedule(
                start_price,
                schedule_data,
                current_date
            )
            
            # Определяем количество дней до следующего снижения
            days_to_next_reduction = None
            if next_reduction_date:
                days_to_next_reduction = (next_reduction_date - current_date).days
            
            # Определяем статус графика
            schedule_status = PriceCalculator._determine_schedule_status(
                current_date,
                schedule_data
            )
            
            return PriceCalculationResult(
                current_price=current_price,
                next_reduction_date=next_reduction_date,
                days_to_next_reduction=days_to_next_reduction,
                schedule_status=schedule_status
            )
            
        except Exception as e:
            # В случае ошибки парсинга возвращаем начальную цену
            return PriceCalculationResult(
                current_price=start_price,
                schedule_status="not_started"
            )
    
    @staticmethod
    def _parse_schedule_table(table) -> list:
        """
        Парсит HTML-таблицу графика снижения цены
        
        Args:
            table: BeautifulSoup объект таблицы
            
        Returns:
            Список кортежей (дата, цена, процент снижения)
        """
        schedule_data = []
        
        # Ищем строки таблицы
        rows = table.find_all('tr')[1:]  # Пропускаем заголовок
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:  # Ожидаем минимум дату, цену и процент
                try:
                    # Извлекаем дату
                    date_text = cells[0].get_text(strip=True)
                    reduction_date = PriceCalculator._parse_date(date_text)
                    
                    # Извлекаем цену
                    price_text = cells[1].get_text(strip=True)
                    price = PriceCalculator._parse_price(price_text)
                    
                    # Извлекаем процент снижения
                    percent_text = cells[2].get_text(strip=True)
                    percent = PriceCalculator._parse_percent(percent_text)
                    
                    if reduction_date and price is not None:
                        schedule_data.append((reduction_date, price, percent))
                        
                except Exception:
                    continue  # Пропускаем некорректные строки
        
        # Сортируем по дате
        schedule_data.sort(key=lambda x: x[0])
        return schedule_data
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """
        Парсит строку даты в объект datetime с часовым поясом UTC
        
        Args:
            date_str: Строка даты
            
        Returns:
            Объект datetime (aware, UTC) или None
        """
        # Поддерживаемые форматы дат
        date_formats = [
            '%d.%m.%Y',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d.%m.%y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ'
        ]
        
        date_str = re.sub(r'[^\d.-]', '', date_str).strip()
        
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
    
    @staticmethod
    def _parse_price(price_str: str) -> Optional[float]:
        """
        Парсит строку цены в число
        
        Args:
            price_str: Строка цены
            
        Returns:
            Число или None
        """
        # Убираем все символы кроме цифр, точки и запятой
        price_clean = re.sub(r'[^\d.,]', '', price_str)
        
        # Заменяем запятую на точку
        price_clean = price_clean.replace(',', '.')
        
        try:
            return float(price_clean)
        except ValueError:
            return None
    
    @staticmethod
    def _parse_percent(percent_str: str) -> Optional[float]:
        """
        Парсит строку процента в число
        
        Args:
            percent_str: Строка процента
            
        Returns:
            Число или None
        """
        # Извлекаем числовое значение из строки процента
        percent_match = re.search(r'[\d,.-]+', percent_str)
        if percent_match:
            percent_clean = percent_match.group().replace(',', '.')
            try:
                return float(percent_clean)
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def _calculate_from_schedule(
        start_price: float,
        schedule_data: list,
        current_date: datetime
    ) -> tuple[float, Optional[datetime]]:
        """
        Рассчитывает текущую цену на основе графика
        
        Args:
            start_price: Начальная цена
            schedule_data: Данные графика [(дата, цена, процент), ...]
            current_date: Текущая дата
            
        Returns:
            Кортеж (текущая цена, дата следующего снижения)
        """
        # Находим последнюю дату, которая <= текущей даты
        current_price = start_price
        next_reduction_date = None
        
        for reduction_date, price, percent in schedule_data:
            if reduction_date <= current_date:
                # Используем цену из графика, если она указана
                if price is not None:
                    current_price = price
            else:
                # Это будущее снижение цены
                if next_reduction_date is None:
                    next_reduction_date = reduction_date
                break
        
        # Если не нашли цену в графике, используем начальную
        if current_price == start_price and schedule_data:
            # Если график есть, но текущая дата еще не наступила
            first_reduction_date, first_price, _ = schedule_data[0]
            if current_date < first_reduction_date:
                current_price = start_price
            else:
                # Ищем ближайшую цену до текущей даты
                for reduction_date, price, percent in reversed(schedule_data):
                    if reduction_date <= current_date and price is not None:
                        current_price = price
                        break
        
        return current_price, next_reduction_date
    
    @staticmethod
    def _determine_schedule_status(
        current_date: datetime,
        schedule_data: list
    ) -> str:
        """
        Определяет статус графика
        
        Args:
            current_date: Текущая дата
            schedule_data: Данные графика
            
        Returns:
            Статус графика ('active', 'completed', 'not_started')
        """
        if not schedule_data:
            return "not_started"
        
        # Проверяем, есть ли даты в будущем
        future_dates = [date for date, _, _ in schedule_data if date > current_date]
        past_dates = [date for date, _, _ in schedule_data if date <= current_date]
        
        if not past_dates and future_dates:
            return "not_started"
        elif not future_dates and past_dates:
            return "completed"
        else:
            return "active"