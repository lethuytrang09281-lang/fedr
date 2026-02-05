import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.bot = None
        self.chat_id = settings.TELEGRAM_CHAT_ID
        if settings.TELEGRAM_BOT_TOKEN:
            try:
                self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            except Exception as e:
                logger.warning(f"Invalid Telegram bot token: {e}")
                self.bot = None

    async def send_lot_alert(self, lot: dict):
        """Отправляет уведомление о новом релевантном лоте"""
        if not self.bot or not self.chat_id:
            logger.warning("Telegram токен или Chat ID не заданы. Уведомление пропущено.")
            return

        text = self._format_message(lot)
        keyboard = self._build_keyboard(lot)

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            logger.info(f"Alert sent for lot {lot.get('guid', 'N/A')}")
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

    def _format_message(self, lot: dict) -> str:
        zone_emoji = {
            "GARDEN_RING": "SADOVOE KOLTSO",
            "TTK": "TTK",
            "TPU": "TPU",
            "OUTSIDE": "Prochee"
        }

        zone = zone_emoji.get(lot.get('location_zone', 'OUTSIDE'), 'Prochee')

        # Теги
        tags = lot.get('semantic_tags', [])
        tags_str = ' '.join([f"#{t.replace(' ', '_')}" for t in tags[:5]])

        # Красные флаги
        red_flags = lot.get('red_flags', [])
        flags_str = ""
        if red_flags:
            flags_str = f"\n<b>Riski:</b> {', '.join(red_flags)}"

        # Цена
        price = lot.get('start_price', 0)
        if price:
            try:
                price = float(price)
                price_str = f"{price:,.0f} RUB".replace(',', ' ')
            except (ValueError, TypeError):
                price_str = "Ne ukazana"
        else:
            price_str = "Ne ukazana"

        # Площадь (если есть из Росреестра)
        area = lot.get('rosreestr_area')
        area_str = ""
        if area:
            try:
                area = float(area)
                area_str = f"\n<b>Ploshchad:</b> {area:,.0f} m2"
            except (ValueError, TypeError):
                pass

        # Цена за метр
        price_per_m = ""
        if price and area and area > 0:
            ppm = float(price) / float(area)
            price_per_m = f" ({ppm:,.0f} RUB/m2)"

        # Кадастровые номера
        cadastrals = lot.get('cadastral_numbers', [])
        cadastral_str = cadastrals[0] if cadastrals else "Ne ukazan"

        # Описание (обрезка + экранирование)
        description = lot.get('description', '')[:200]
        description = description.replace("<", "&lt;").replace(">", "&gt;")

        return (
            f"<b>{zone}</b>\n\n"
            f"<b>{description}...</b>\n\n"
            f"<b>Tsena:</b> {price_str}{price_per_m}{area_str}\n"
            f"<b>Kadastr:</b> <code>{cadastral_str}</code>"
            f"{flags_str}\n\n"
            f"{tags_str}"
        )

    def _build_keyboard(self, lot: dict) -> InlineKeyboardMarkup:
        """Создаёт кнопки со ссылками"""
        buttons = []

        # Ссылка на Федресурс
        guid = lot.get('guid')
        if guid:
            buttons.append([InlineKeyboardButton(
                text="Fedresurs",
                url=f"https://bankrot.fedresurs.ru/MessageWindow.aspx?ID={guid}"
            )])

        # Ссылка на ПКК (Росреестр)
        cadastrals = lot.get('cadastral_numbers', [])
        if cadastrals:
            cn = cadastrals[0].replace(':', '%3A')
            buttons.append([InlineKeyboardButton(
                text="Karta PKK",
                url=f"https://pkk.rosreestr.ru/#/search/{cn}/1"
            )])
            buttons.append([InlineKeyboardButton(
                text="ISOGD Moskva",
                url=f"https://isogd.mos.ru/isogd-portal/landing?cadnum={cadastrals[0]}"
            )])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def close(self):
        if self.bot:
            await self.bot.session.close()
