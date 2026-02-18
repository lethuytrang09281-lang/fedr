#!/usr/bin/env python3
"""
Тест поиска лотов ПЕРЕД запуском оркестратора
Потратит 1-3 запроса к fedresurs API
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, '/app')

from src.services.fedresurs_search import FedresursSearch

async def test_search():
    """Тест поиска лотов — потратит 1-3 запроса к fedresurs API"""

    api_key = os.getenv('PARSER_API_KEY')

    if not api_key:
        print("❌ ОШИБКА: PARSER_API_KEY не найден в окружении!")
        return

    print("=" * 60)
    print("🔍 ТЕСТОВЫЙ ПОИСК ЛОТОВ")
    print("=" * 60)
    print(f"API ключ: {api_key[:20]}...{api_key[-4:]}")
    print(f"Регион: Москва (77)")
    print(f"Цена: 1М - 300М ₽")
    print("=" * 60)

    search = FedresursSearch(api_key=api_key)

    try:
        print("\n🚀 Запускаю поиск...")
        lots = await search.search_lots()

        print("\n" + "=" * 60)
        print("✅ ПОИСК ЗАВЕРШЁН")
        print("=" * 60)
        print(f"🎯 Найдено лотов: {len(lots)}")
        print(f"📡 Потрачено запросов: {search.stats['requests_made']}")
        print(f"🏢 Организаций проверено: {search.stats['orgs_found']}")
        print(f"💬 Сообщений проверено: {search.stats['messages_checked']}")
        print(f"📋 Сообщений о торгах: {search.stats['trade_messages_found']}")
        print(f"📦 Всего лотов: {search.stats['lots_found']}")
        print(f"✅ Прошло фильтр: {search.stats['lots_passed_filter']}")

        if lots:
            print("\n" + "=" * 60)
            print("📦 ПЕРВЫЙ ЛОТ:")
            print("=" * 60)
            lot = lots[0]
            print(f"Номер лота: {lot.get('lot_num', 'N/A')}")
            print(f"Цена: {lot.get('start_price', 0):,.0f} ₽")
            print(f"Описание: {lot.get('description', 'N/A')[:150]}...")
            print(f"Должник: {lot.get('debtor_name', 'N/A')[:50]}...")
            print(f"ИНН: {lot.get('debtor_inn', 'N/A')}")
            print(f"Дело: {lot.get('case_num', 'N/A')}")
            print(f"Message ID: {lot.get('message_id', 'N/A')}")
            print(f"Ключевое слово: [{lot.get('found_keyword', 'N/A')}]")

            if len(lots) > 1:
                print(f"\n📋 Всего найдено: {len(lots)} лотов")
                print("\nПримеры других лотов:")
                for i, lot in enumerate(lots[1:min(4, len(lots))], 2):
                    print(f"\n  {i}. {lot.get('description', '')[:80]}...")
                    print(f"     Цена: {lot.get('start_price', 0):,.0f} ₽")
                    print(f"     Ключевое слово: [{lot.get('found_keyword')}]")
        else:
            print("\n" + "=" * 60)
            print("⚠️ ЛОТОВ НЕ НАЙДЕНО")
            print("=" * 60)
            print("\nВозможные причины:")
            print("  1. Сейчас нет подходящих торгов в Москве (норма)")
            print("  2. Фильтр слишком строгий (проверь ключевые слова)")
            print("  3. Все лоты дороже 300М или дешевле 1М")
            print("  4. Ошибка парсинга API (проверь логи выше)")

            print(f"\nСтатистика поиска:")
            print(f"  Организаций-банкротов найдено: {search.stats['orgs_found']}")
            print(f"  Сообщений проверено: {search.stats['messages_checked']}")
            print(f"  Сообщений о торгах: {search.stats['trade_messages_found']}")
            print(f"  Лотов всего (до фильтра): {search.stats['lots_found']}")
            print(f"  Лотов после фильтра: {search.stats['lots_passed_filter']}")

        print("\n" + "=" * 60)
        print("📊 ИТОГ ТЕСТА")
        print("=" * 60)

        if lots:
            print(f"✅ УСПЕХ! Найдено {len(lots)} лотов")
            print(f"✅ Потрачено {search.stats['requests_made']} запросов")
            print(f"✅ Можно запускать оркестратор")
        else:
            if search.stats['orgs_found'] > 0:
                print(f"⚠️ Организации найдены ({search.stats['orgs_found']}), но лоты не прошли фильтр")
                print(f"⚠️ Это нормально - можно запускать оркестратор")
            else:
                print(f"❌ Организации не найдены - возможна ошибка API")
                print(f"❌ Проверь логи выше!")

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 60)
        print(f"Ошибка: {e}")
        print("\nTraceback:")
        import traceback
        traceback.print_exc()
        print("\n⚠️ НЕ ЗАПУСКАЙ ОРКЕСТРАТОР! Сначала исправь ошибку!")

    finally:
        await search.close()
        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_search())
