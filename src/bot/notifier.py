import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.config import settings

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_lot_alert(self, lot: dict):
        """Отправляет уведомление о новом релевантном лоте"""

        # Формируем текст
        text = self._format_message(lot)

        # Кнопки
        keyboard = self._build_keyboard(lot)

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    def _format_message(self, lot: dict) -> str:
        zone_emoji = {
            "GARDEN_RING": "🔥 САДОВОЕ КОЛЬЦО",
            "TTK": "🏙 ТТК",
            "OUTSIDE": "📍 Прочее"
        }

        zone = zone_emoji.get(lot.get('location_zone', 'OUTSIDE'), '📍')

        # Формируем теги
        tags = lot.get('semantic_tags', [])
        tags_str = ' '.join([f"#{t.replace(' ', '_')}" for t in tags[:5]])

        # Красные флаги
        red_flags = lot.get('red_flags', [])
        flags_str = ""
        if red_flags:
            flags_str = f"\n⚠️ <b>Риски:</b> {', '.join(red_flags)}"

        # Цена
        price = lot.get('start_price', 0)
        price_str = f"{price:,.0f} ₽".replace(',', ' ') if price else "Не указана"

        # Площадь (если есть из Росреестра)
        area = lot.get('rosreestr_area')
        area_str = f"\n📐 <b>Площадь:</b> {area:,.0f} м²" if area else ""

        # Цена за метр
        price_per_m = ""
        if price and area and area > 0:
            ppm = price / area
            price_per_m = f" ({ppm:,.0f} ₽/м²)"

        # Кадастровые номера
        cadastrals = lot.get('cadastral_numbers', [])
        cadastral_str = cadastrals[0] if cadastrals else "Не указан"

        return f"""
{zone}

📋 <b>{lot.get('description', '')[:200]}...</b>

💰 <b>Цена:</b> {price_str}{price_per_m}{area_str}
🗺 <b>Кадастр:</b> <code>{cadastral_str}</code>
{flags_str}

{tags_str}
"""

    def _build_keyboard(self, lot: dict) -> InlineKeyboardMarkup:
        """Создаёт кнопки со ссылками"""
        buttons = []

        # Ссылка на Федресурс
        guid = lot.get('guid')
        if guid:
            buttons.append([InlineKeyboardButton(
                text="📄 Федресурс",
                url=f"https://bankrot.fedresurs.ru/MessageWindow.aspx?ID={guid}"
            )])

        # Ссылка на ПКК (Росреестр)
        cadastrals = lot.get('cadastral_numbers', [])
        if cadastrals:
            cn = cadastrals[0].replace(':', '%3A')
            buttons.append([InlineKeyboardButton(
                text="🗺 Карта ПКК",
                url=f"https://pkk.rosreestr.ru/#/search/{cn}/1"
            )])
            buttons.append([InlineKeyboardButton(
                text="🏗 ИСОГД Москва",
                url=f"https://isogd.mos.ru/isogd-portal/landing?cadnum={cadastrals[0]}"
            )])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def close(self):
        await self.bot.session.close()
