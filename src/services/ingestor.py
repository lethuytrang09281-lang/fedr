import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import delete
from src.database.models import Auction, Lot, MessageHistory, PriceSchedule, LotStatus, Document
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class IngestionService:
    @staticmethod
    async def save_parsed_data(session: AsyncSession, auction_dto: dict, lots_dto: list, message_dto: dict) -> list[int]:
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
                    last_updated=datetime.now(timezone.utc)
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

            saved_lot_ids = []
            # 3. Process Lots
            for lot_data in lots_dto:
                # Извлекаем статус корректно (если вдруг в DTO пришла строка, или Enum)
                status_value = lot_data.get('status', LotStatus.ANNOUNCED.value)
                if isinstance(status_value, LotStatus):
                    status_value = status_value.value
                elif isinstance(status_value, str):
                    # Если статус передан как строка, проверим, есть ли он в enum
                    try:
                        status_enum = LotStatus(status_value)
                        status_value = status_enum.value
                    except ValueError:
                        # Если строка не соответствует enum, используем как есть
                        pass

                stmt_lot = insert(Lot).values(
                    auction_id=auction_dto['guid'],
                    lot_number=lot_data.get('lot_number', 1),
                    description=lot_data['description'],
                    start_price=lot_data['start_price'],
                    category_code=lot_data.get('category_code'),
                    cadastral_numbers=list(lot_data.get('cadastral_numbers') or []),
                    status=status_value if isinstance(status_value, str) else status_value.value,
                    is_relevant=lot_data.get('is_relevant', False),
                    location_zone=lot_data.get('location_zone', 'OUTSIDE'),
                    semantic_tags=lot_data.get('semantic_tags', []),
                    red_flags=lot_data.get('red_flags', []),
                    is_restricted=lot_data.get('is_restricted', False)
                ).on_conflict_do_update(
                    # Теперь этот constraint существует в базе!
                    constraint='lots_auction_id_lot_number_key',
                    set_=dict(
                        description=lot_data['description'],
                        start_price=lot_data['start_price'],
                        category_code=lot_data.get('category_code'),
                        cadastral_numbers=list(lot_data.get('cadastral_numbers') or []),
                        status=status_value if isinstance(status_value, str) else status_value.value,
                        is_relevant=lot_data.get('is_relevant', False),
                        location_zone=lot_data.get('location_zone', 'OUTSIDE'),
                        semantic_tags=lot_data.get('semantic_tags', []),
                        red_flags=lot_data.get('red_flags', []),
                        is_restricted=lot_data.get('is_restricted', False)
                    )
                ).returning(Lot.id)

                result = await session.execute(stmt_lot)
                lot_id = result.scalar_one()
                saved_lot_ids.append(lot_id)

                # 4. Process Price Schedules (if any)
                if lot_data.get('price_schedules'):
                    # Удаляем старые
                    await session.execute(delete(PriceSchedule).where(PriceSchedule.lot_id == lot_id))

                    # Генератором создаем список объектов (быстрее чем add в цикле)
                    new_schedules = [
                        PriceSchedule(
                            lot_id=lot_id,
                            date_start=sched['date_start'].replace(tzinfo=timezone.utc) if sched['date_start'].tzinfo is None else sched['date_start'],
                            date_end=sched['date_end'].replace(tzinfo=timezone.utc) if sched['date_end'].tzinfo is None else sched['date_end'],
                            price=sched['price']
                        ) for sched in lot_data['price_schedules']
                    ]
                    session.add_all(new_schedules) # Используем add_all

            await session.commit()
            logger.info(f"Successfully ingested auction {auction_dto['guid']} with {len(lots_dto)} lots")
            return saved_lot_ids

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to ingest data for auction {auction_dto.get('guid')}: {str(e)}")
            raise

    @staticmethod
    async def process_attachments(
        session: AsyncSession,
        message_guid: str,
        lot_id: int,
        attachments: list,
        document_extractor
    ):
        """
        Process message attachments and extract structured data.

        Args:
            session: Database session
            message_guid: Message GUID
            lot_id: Associated lot ID
            attachments: List of attachment dicts with 'filename' and 'data'
            document_extractor: DocumentExtractor instance
        """
        if not attachments:
            return

        logger.info(f"Processing {len(attachments)} attachments for message {message_guid}")

        for attachment in attachments:
            try:
                filename = attachment.get('filename', 'unknown')
                file_data = attachment.get('data')  # bytes

                if not file_data:
                    logger.warning(f"No data for attachment {filename}")
                    continue

                # Detect document type
                doc_type = document_extractor.detect_document_type(filename)

                # Extract data
                extracted = await document_extractor.extract_from_attachment(
                    attachment_data=file_data,
                    filename=filename,
                    document_type=doc_type
                )

                # Save to database
                document = Document(
                    lot_id=lot_id,
                    message_guid=message_guid,
                    filename=filename,
                    document_type=doc_type,
                    file_size=len(file_data),
                    extracted_data=extracted,
                    downloaded_at=datetime.now(timezone.utc)
                )

                session.add(document)
                logger.info(f"Extracted data from {filename} (type: {doc_type})")

            except Exception as e:
                logger.error(f"Failed to process attachment {attachment.get('filename')}: {e}")
                # Continue with other attachments

        await session.commit()