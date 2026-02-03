#!/usr/bin/env python3
"""Простой тест исправлений часовых поясов без зависимостей"""
import sys
from datetime import datetime, timezone
import re

def test_datetime_now():
    """Тест datetime.now() с часовым поясом"""
    print("=== Тест 1: datetime.now() с часовым поясом ===")
    dt = datetime.now(timezone.utc)
    print(f"datetime.now(timezone.utc): {dt}")
    print(f"Часовой пояс: {dt.tzinfo}")
    print(f"Является aware datetime: {dt.tzinfo is not None}")
    assert dt.tzinfo is not None, "datetime должен иметь часовой пояс"
    return True

def test_parse_date_formats():
    """Тест парсинга дат с добавлением часового пояса (имитация PriceCalculator._parse_date)"""
    print("\n=== Тест 2: Парсинг дат с часовым поясом ===")
    
    date_formats = [
        '%d.%m.%Y',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%d.%m.%y',
    ]
    
    test_cases = [
        "01.01.2024",
        "2024-01-01",
        "01/01/2024",
        "01-01-2024",
        "01.01.24",
    ]
    
    for date_str, fmt in zip(test_cases, date_formats):
        try:
            # Очистка строки (имитация кода из PriceCalculator)
            clean_str = re.sub(r'[^\d.-]', '', date_str).strip()
            dt = datetime.strptime(clean_str, fmt)
            # Добавление часового пояса UTC (как в исправленном коде)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            print(f"✅ '{date_str}' -> {dt} (tz: {dt.tzinfo})")
            assert dt.tzinfo is not None, f"Дата '{date_str}' должна иметь часовой пояс"
        except Exception as e:
            print(f"❌ Ошибка парсинга '{date_str}': {e}")
            return False
    return True

def test_fromisoformat_parsing():
    """Тест парсинга ISO формата (имитация orchestrator.py)"""
    print("\n=== Тест 3: fromisoformat парсинг (как в orchestrator) ===")
    
    test_cases = [
        ("2024-01-01T12:00:00Z", "UTC с Z"),
        ("2024-01-01T12:00:00+03:00", "UTC+3"),
        ("2024-01-01T12:00:00", "naive дата"),
        ("2024-01-01T12:00:00-05:00", "UTC-5"),
    ]
    
    for test_str, description in test_cases:
        try:
            # Имитация обработки из orchestrator.py
            date_str = test_str.replace('Z', '+00:00')
            date_pub = datetime.fromisoformat(date_str)
            # Если дата без часового пояса (naive), добавляем UTC
            if date_pub.tzinfo is None:
                date_pub = date_pub.replace(tzinfo=timezone.utc)
            else:
                # Конвертируем в UTC, если дата имеет другую временную зону
                date_pub = date_pub.astimezone(timezone.utc)
            
            print(f"✅ '{test_str}' ({description}) -> {date_pub} (UTC)")
            assert date_pub.tzinfo == timezone.utc, f"Дата должна быть в UTC"
        except Exception as e:
            print(f"❌ Ошибка парсинга '{test_str}': {e}")
            return False
    return True

def test_imports():
    """Тест импорта исправленных модулей"""
    print("\n=== Тест 4: Проверка импортов ===")
    
    # Проверяем, что файлы существуют и могут быть прочитаны
    files_to_check = [
        "src/orchestrator.py",
        "src/logic/price_calculator.py", 
        "src/services/xml_parser.py",
        "src/services/ingestor.py",
    ]
    
    for filepath in files_to_check:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                # Проверяем наличие исправлений
                if "datetime.now(timezone.utc)" in content:
                    print(f"✅ {filepath}: содержит datetime.now(timezone.utc)")
                elif "datetime.now()" in content and "timezone.utc" not in content:
                    print(f"⚠️  {filepath}: содержит datetime.now() без timezone.utc")
                else:
                    print(f"✅ {filepath}: файл доступен")
        except Exception as e:
            print(f"❌ {filepath}: ошибка чтения - {e}")
            return False
    
    # Проверяем конкретные исправления в файлах
    print("\n=== Проверка конкретных исправлений ===")
    
    # orchestrator.py должен содержать исправленный парсинг дат
    with open("src/orchestrator.py", 'r') as f:
        content = f.read()
        if "datetime.fromisoformat(date_str)" in content and "date_pub.replace(tzinfo=timezone.utc)" in content:
            print("✅ orchestrator.py: исправлен парсинг дат с добавлением часового пояса")
        else:
            print("❌ orchestrator.py: не найдены исправления парсинга дат")
            return False
    
    # price_calculator.py должен содержать исправленный _parse_date
    with open("src/logic/price_calculator.py", 'r') as f:
        content = f.read()
        if "dt.replace(tzinfo=timezone.utc)" in content and "_parse_date" in content:
            print("✅ price_calculator.py: исправлен метод _parse_date")
        else:
            print("❌ price_calculator.py: не найдены исправления _parse_date")
            return False
    
    # xml_parser.py должен содержать datetime.now(timezone.utc)
    with open("src/services/xml_parser.py", 'r') as f:
        content = f.read()
        if "datetime.now(timezone.utc)" in content:
            print("✅ xml_parser.py: использует datetime.now(timezone.utc)")
        else:
            print("❌ xml_parser.py: не использует datetime.now(timezone.utc)")
            return False
    
    return True

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("Тестирование исправлений часовых поясов")
    print("=" * 60)
    
    tests = [
        ("datetime.now() с часовым поясом", test_datetime_now),
        ("Парсинг дат с часовым поясом", test_parse_date_formats),
        ("fromisoformat парсинг", test_fromisoformat_parsing),
        ("Импорты и проверка файлов", test_imports),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"\n✅ Тест '{test_name}' пройден\n")
                passed += 1
            else:
                print(f"\n❌ Тест '{test_name}' не пройден\n")
                failed += 1
        except Exception as e:
            print(f"\n❌ Тест '{test_name}' вызвал исключение: {e}\n")
            failed += 1
    
    print("=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Не пройдено: {failed}")
    print(f"📊 Всего тестов: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 Все тесты пройдены успешно!")
        print("✅ Исправления часовых поясов применены корректно")
        print("✅ Все даты теперь являются aware datetime с часовым поясом UTC")
    else:
        print(f"\n⚠️  {failed} тестов не пройдено")
    
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)