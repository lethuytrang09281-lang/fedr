import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Lot
from src.database.base import async_session_factory
from src.services.rosreestr_client import RosreestrClient

logger = logging.getLogger(__name__)

class RosreestrEnricher:
    """Обогащение данных через API Росреестра (ПКК)"""

    def __init__(self):
        self.client = RosreestrClient()

    async def get_parcel_info(self, cadastral_number: str) -> Optional[Dict[str, Any]]:
        """Получает данные по кадастровому номеру участка"""
        try:
            data = await self.client.get_by_cadastral(cadastral_number)
            if data:
                return {
                    'area': data.get('area'),
                    'cadastral_value': data.get('cadastral_value'),
                    'address': data.get('address'),
                    'category': data.get('type'),
                    'vri': data.get('purpose'),
                }
        except Exception as e:
            logger.error(f"Error fetching parcel {cadastral_number}: {e}")
        return None

    async def get_building_info(self, cadastral_number: str) -> Optional[Dict[str, Any]]:
        """Получает данные по кадастровому номеру здания"""
        try:
            data = await self.client.get_by_cadastral(cadastral_number)
            if data:
                return {
                    'area': data.get('area'),
                    'cadastral_value': data.get('cadastral_value'),
                    'address': data.get('address'),
                    'purpose': data.get('purpose'),
                    'floors': data.get('floor_count'),
                }
        except Exception as e:
            logger.error(f"Error fetching building {cadastral_number}: {e}")
        return None

    async def enrich_lot(self, lot_id: int, session: AsyncSession) -> bool:
        """Обогащает конкретный лот данными из Росреестра"""
        result = await session.execute(select(Lot).where(Lot.id == lot_id))
        lot = result.scalar_one_or_none()

        if not lot or not lot.cadastral_numbers:
            return False

        cadastral = lot.cadastral_numbers[0]

        # Пробуем сначала как участок, потом как здание
        info = await self.get_parcel_info(cadastral)
        if not info:
            info = await self.get_building_info(cadastral)

        if info:
            lot.rosreestr_area = info.get('area')
            lot.rosreestr_value = info.get('cadastral_value')
            lot.rosreestr_vri = info.get('vri') or info.get('purpose')
            lot.rosreestr_address = info.get('address')
            lot.needs_enrichment = False
            await session.commit()
            logger.info(f"Enriched lot {lot_id}: area={info.get('area')}")
            return True

        lot.needs_enrichment = False  # Помечаем как обработанный
        await session.commit()
        return False

    async def close(self):
        """Закрывает HTTP сессию клиента"""
        await self.client.close()


class EnrichmentWorker:
    """Фоновый воркер для обогащения лотов"""

    def __init__(self):
        self.enricher = RosreestrEnricher()
        self.running = False

    async def run(self, batch_size: int = 5, sleep_seconds: int = 30):
        """Запускает бесконечный цикл обогащения"""
        self.running = True
        logger.info("Starting Rosreestr Enrichment Worker...")

        while self.running:
            try:
                async with async_session_factory() as session:
                    # Берём лоты, которые нужно обогатить
                    # Приоритет: GARDEN_RING и TTK
                    query = (
                        select(Lot)
                        .where(Lot.needs_enrichment == True)
                        .where(Lot.location_zone.in_(['GARDEN_RING', 'TTK', 'TPU']))
                        .where(Lot.cadastral_numbers != None)
                        .limit(batch_size)
                    )

                    result = await session.execute(query)
                    lots = result.scalars().all()

                    if not lots:
                        logger.debug("No lots to enrich, sleeping...")
                        await asyncio.sleep(60)
                        continue

                    for lot in lots:
                        await self.enricher.enrich_lot(lot.id, session)
                        # Пауза между запросами чтобы не забанили
                        await asyncio.sleep(2)

                    logger.info(f"Enriched {len(lots)} lots")

                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"Enrichment worker error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        self.running = False
