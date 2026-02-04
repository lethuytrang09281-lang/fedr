import httpx
import logging
from typing import Optional, List
from src.database.models import Lot
from src.config import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else None

    async def send_lot_alert(self, lot: Lot, auction_number: str, trade_place_name: str = "Н/Д", tags: str = None):
        if not self.api_url or not self.chat_id:
            logger.warning("Telegram токен или Chat ID не заданы. Уведомление пропущено.")
            return

        efrsb_url = f"https://bankrot.fedresurs.ru/MessageWindow.aspx?ID={lot.auction_id}"
        
        geo_url = ""
        cadastral_list = lot.cadastral_numbers
        if isinstance(cadastral_list, list) and len(cadastral_list) > 0:
            first_cad = cadastral_list[0] 
            geo_url = f"\n📍 <a href='https://pkk.rosreestr.ru/#/search/{first_cad}'>На карту (ПКК)</a>"
        elif isinstance(cadastral_list, str) and cadastral_list:
             geo_url = f"\n📍 <a href='https://pkk.rosreestr.ru/#/search/{cadastral_list}'>На карту (ПКК)</a>"

        description_preview = lot.description[:300] + "..." if len(lot.description) > 300 else lot.description
        
        # Экранирование (HARDCODED CORRECTLY)
        description_preview = description_preview.replace("<", "&lt;").replace(">", "&gt;")

        tags_line = f"🏷 <b>{tags}</b>\n" if tags else ""

        text = (
            f"🎯 <b>Найден целевой актив!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{tags_line}"
            f"📦 <b>Лот №{lot.lot_number}</b>\n"
            f"💰 Цена: {lot.start_price:,.2f} ₽\n"
            f"🏗 Статус: {lot.status}\n"
            f"📝 {description_preview}\n\n"
            f"📑 Торги: {auction_number}\n"
            f"🏛 Площадка: {trade_place_name}\n"
            f"🌍 Кадастр: {', '.join(lot.cadastral_numbers) if isinstance(lot.cadastral_numbers, list) else 'не указан'}"
            f"{geo_url}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='{efrsb_url}'>Открыть карточку на ЕФРСБ</a>"
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.api_url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                })
                resp.raise_for_status()
                logger.info(f"🔔 Alert sent for lot {lot.id}")
        except Exception as e:
            logger.error(f"❌ Telegram send error: {e}")