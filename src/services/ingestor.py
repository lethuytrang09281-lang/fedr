import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import delete
from src.database.models import Auction, Lot, MessageHistory, PriceSchedule, LotStatus
from datetime import datetime

logger = logging.getLogger(__name__)

class IngestionService:
    @staticmethod
    async def save_parsed_data(session: AsyncSession, auction_dto: dict, lots_dto: list, message_dto: dict):
        """
        Сохраняет распарсенные данные по паттерну Upsert.
        auction_dto: {guid, number, etp_id, organizer_inn}
        lots_dto: list of {lot_number, description, start_price, category_code, cadastral_numbers, status}
        message_dto: {guid, type, date_publish, content_xml}
        """
        try:
            # 1. Upsert Auction
            stmt_auction = insert(Auction).values(
                guid=auction_dto['guid'],
                number=auction_dto['number'],
                etp_id=auction_dto.get('etp_id'),
                organizer_inn=auction_dto.get('organizer_inn')
            ).on_conflict_do_update(
                index_elements=[Auction.guid],
                set_=dict(
                    number=auction_dto['number'],
                    last_updated=datetime.utcnow()
                )
            )
            await session.execute(stmt_auction)

            # 2. Save Message (Audit trail)
            stmt_msg = insert(MessageHistory).values(
                guid=message_dto['guid'],
                auction_id=auction_dto['guid'],
                type=message_dto['type'],
                date_publish=message_dto['date_publish'],
                content_xml=message_dto['content_xml']
            ).on_conflict_do_nothing() # Сообщение уникально по GUID
            await session.execute(stmt_msg)

            # 3. Process Lots
            for lot_data in lots_dto:
                # Ищем существующий лот в рамках этих торгов по номеру лота
                # Так как GUID лота может меняться или отсутствовать в ранних стадиях
                stmt_lot = insert(Lot).values(
                    auction_id=auction_dto['guid'],
                    lot_number=lot_data.get('lot_number', 1),
                    description=lot_data['description'],
                    start_price=lot_data['start_price'],
                    category_code=lot_data.get('category_code'),
                    cadastral_numbers=lot_data.get('cadastral_numbers', []),
                    status=lot_data.get('status', LotStatus.ANNOUNCED.value)
                ).on_conflict_do_update(
                    # Для PostgreSQL используем индекс для конфликта
                    index_elements=['auction_id', 'lot_number'],
                    set_=dict(
                        description=lot_data['description'],
                        start_price=lot_data['start_price'],
                        category_code=lot_data.get('category_code'),
                        cadastral_numbers=lot_data.get('cadastral_numbers', []),
                        status=lot_data.get('status', LotStatus.ANNOUNCED.value),
                        guid=insert.excluded.guid  # Обновляем GUID, если он появился
                    )
                ).returning(Lot.id)
                
                result = await session.execute(stmt_lot)
                lot_id = result.scalar_one_or_none()

                # 4. Process Price Schedules (if any)
                if lot_data.get('price_schedules'):
                    # Удаляем старый график и записываем новый (актуальный для текущего сообщения)
                    # Это проще, чем матчить интервалы дат
                    await session.execute(delete(PriceSchedule).where(PriceSchedule.lot_id == lot_id))
                    
                    for sched in lot_data['price_schedules']:
                        new_sched = PriceSchedule(
                            lot_id=lot_id,
                            date_start=sched['date_start'],
                            date_end=sched['date_end'],
                            price=sched['price']
                        )
                        session.add(new_sched)
                
            await session.commit()
            logger.info(f"Successfully ingested auction {auction_dto['guid']} with {len(lots_dto)} lots")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to ingest data for auction {auction_dto.get('guid')}: {str(e)}")
            raise