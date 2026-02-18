#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Telegram бота
"""
import asyncio
import sys
import os

sys.path.insert(0, '/app')

from aiogram import Bot
from aiogram.enums import ParseMode
from src.config import settings

async def test_bot():
    """Тест отправки сообщения в Telegram"""
    print(f"🔍 Проверка Telegram бота...")
    print(f"   Token: {settings.TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"   Chat ID: {settings.TELEGRAM_CHAT_ID}")
    
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print("❌ Telegram не настроен!")
        return False
    
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        print(f"   Имя: {me.first_name}")
        print(f"   ID: {me.id}")
        
        # Отправляем тестовое сообщение
        message = await bot.send_message(
            chat_id=settings.TELEGRAM_CHAT_ID,
            text="🤖 <b>Тестовое сообщение</b>\n\n"
                 "✅ Fedresurs Radar Bot успешно настроен!\n"
                 "📊 Resource Monitor активен\n"
                 "🚀 Система готова к работе",
            parse_mode=ParseMode.HTML
        )
        
        print(f"✅ Сообщение отправлено! (ID: {message.message_id})")
        
        await bot.session.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_bot())
    sys.exit(0 if result else 1)
