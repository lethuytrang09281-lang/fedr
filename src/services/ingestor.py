import logging
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from src.database.models import Auction, Lot, MessageHistory, LotStatus
from src.services.notifier import TelegramNotifier
from src.services.classifier import SemanticFilter
from src.config import settings

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.classifier = SemanticFilter()

    async def save_parsed_data(self, session: AsyncSession, auction_dto: dict, lots_dto: list, message_dto: dict):
        try:
            stmt_auction = insert(Auction).values(
                guid=auction_dto['guid'],
                number=auction_dto['number'],
                etp_id=auction_dto.get('etp_id'),
                organizer_inn=auction_dto.get('organizer_inn')
            ).on_conflict_do_update(
                index_elements=[Auction.guid],
                set_=dict(
                    number=auction_dto['number'],
                    last_updated=datetime.datetime.utcnow()
                )
            ).returning(Auction.number, Auction.etp_id)
            
            auction_result = await session.execute(stmt_auction)
            auction_data = auction_result.first()
            auction_number = auction_data[0] if auction_data else auction_dto['number']
            platform_name = auction_data[1] if auction_data else "Н/Д"

            stmt_msg = insert(MessageHistory).values(
                guid=message_dto['guid'],
                auction_id=auction_dto['guid'],
                type=message_dto['type'],
                date_publish=message_dto['date_publish'],
                content_xml=message_dto['content_xml']
            ).on_conflict_do_nothing()
            await session.execute(stmt_msg)

            for lot_data in lots_dto:
                lot_values = {
                    "auction_id": auction_dto['guid'],
                    **lot_data
                }
                
                stmt_lot = insert(Lot).values(lot_values).on_conflict_do_update(
                    constraint='lots_auction_id_lot_number_key',
                    set_=dict(
                        description=lot_data['description'],
                        start_price=lot_data['start_price'],
                        status=lot_data.get('status', LotStatus.ANNOUNCED),
                        cadastral_numbers=lot_data.get('cadastral_numbers', [])
                    )
                ).returning(Lot)
                
                result = await session.execute(stmt_lot)
                saved_lot = result.scalar_one()

                now = datetime.datetime.utcnow()
                lot_created = saved_lot.created_at
                if lot_created.tzinfo:
                    lot_created = lot_created.replace(tzinfo=None)

                time_since_creation = now - lot_created
                is_newly_created = time_since_creation.total_seconds() < 60

                if is_newly_created:
                    analysis = self.classifier.analyze(saved_lot)

                    if analysis["is_interesting"]:
                        tags_str = ", ".join(analysis["tags"])
                        logger.info(f"🎯 Matched Rules: {analysis['matched_rules']} | Score: {analysis['total_score']}")
                        
                        await self.notifier.send_lot_alert(
                            lot=saved_lot, 
                            auction_number=auction_number, 
                            trade_place_name=platform_name,
                            tags=tags_str
                        )

            await session.commit()
            logger.info(f"✅ Ingested auction {auction_dto['guid']} ({len(lots_dto)} lots)")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Failed to ingest auction {auction_dto.get('guid')}: {e}")
            raise