import asyncio
import logging
from typing import Optional, Dict, Any

from rosreestr_api.clients.rosreestr import PKKRosreestrAPIClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Lot
from src.database.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class RosreestrEnricher:
    """Обогащение данных через API Росреестра (ПКК)"""

    def __init__(self):
        self.client = PKKRosreestrAPIClient()

    def get_parcel_info(self, cadastral_number: str) -> Optional[Dict[str, Any]]:
        """Получает данные по кадастровому номеру участка"""
        try:
            data = self.client.get_parcel_by_cadastral_id(cadastral_number)
            if data:
                attrs = data.get('attrs', {})
                return {
                    'area': attrs.get('area_value'),
                    'cadastral_value': attrs.get('cad_cost'),
                    'address': attrs.get('address'),
                    'category': attrs.get('category_type'),
                    'vri': attrs.get('util_by_doc') or attrs.get('util_code'),
                }
        except Exception as e:
            logger.error(f"Error fetching parcel {cadastral_number}: {e}")
        return None

    def get_building_info(self, cadastral_number: str) -> Optional[Dict[str, Any]]:
        """Получает данные по кадастровому номеру здания"""
        try:
            data = self.client.get_building_by_cadastral_id(cadastral_number)
            if data:
                attrs = data.get('attrs', {})
                return {
                    'area': attrs.get('area_value'),
                    'cadastral_value': attrs.get('cad_cost'),
                    'address': attrs.get('address'),
                    'purpose': attrs.get('purpose'),
                    'floors': attrs.get('floors'),
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
        info = self.get_parcel_info(cadastral)
        if not info:
            info = self.get_building_info(cadastral)

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
                async with AsyncSessionLocal() as session:
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
