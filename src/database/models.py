import enum
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, Integer, Index, UniqueConstraint, Enum as SAEnum, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class LotStatus(enum.Enum):
    ANNOUNCED = "Announced"
    ACTIVE = "Active"
    FAILED = "Failed"
    SOLD = "Sold"
    CANCELLED = "Cancelled"

class SystemState(Base):
    """Таблица для хранения состояния системы (прогресс парсинга)"""
    __tablename__ = "system_state"

    # Ключ задачи (например, 'trade_monitor')
    task_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Дата, на которой остановился парсер
    last_processed_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Auction(Base):
    """Торги (Основание для лотов)"""
    __tablename__ = "auctions"

    guid: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True)
    number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    etp_id: Mapped[Optional[str]] = mapped_column(String(255))
    organizer_inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lots: Mapped[List["Lot"]] = relationship("Lot", back_populates="auction", cascade="all, delete-orphan")
    messages: Mapped[List["MessageHistory"]] = relationship("MessageHistory", back_populates="auction")

class Lot(Base):
    """Лоты торгов"""
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guid: Mapped[Optional[UUID]] = mapped_column(PG_UUID, index=True)
    auction_id: Mapped[UUID] = mapped_column(ForeignKey("auctions.guid", ondelete="CASCADE"))

    lot_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    start_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2))
    category_code: Mapped[Optional[str]] = mapped_column(Text, index=True)

    # Кадастровые номера (GIN индекс для поиска)
    cadastral_numbers: Mapped[List[str]] = mapped_column(ARRAY(String), server_default="{}")

    status: Mapped[str] = mapped_column(String(50), default=LotStatus.ANNOUNCED.value)
    
    # Флаг для скрытых данных (Постановление №5)
    is_restricted: Mapped[bool] = mapped_column(default=False)

    # Новые поля для Спринта 2
    is_relevant: Mapped[bool] = mapped_column(default=False)
    location_zone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    semantic_tags: Mapped[List[str]] = mapped_column(ARRAY(String), server_default="{}")
    red_flags: Mapped[List[str]] = mapped_column(ARRAY(String), server_default="{}")

    # Росреестр данные
    rosreestr_area: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    rosreestr_value: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    rosreestr_vri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    rosreestr_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    needs_enrichment: Mapped[bool] = mapped_column(default=True, index=True)

    # Данные должника (из Федресурс)
    debtor_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debtor_inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    debtor_ogrn: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    debtor_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Дело и управляющий
    case_num: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    manager_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Параметры торгов
    trade_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    trade_app_start: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trade_app_end: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trade_place: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    deposit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ЭТП данные
    etp_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    etp_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    application_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    application_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    organizer_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ссылка на сообщение Федресурс
    message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message_num: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Скоринг
    deal_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), nullable=True)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="lots")
    price_schedules: Mapped[List["PriceSchedule"]] = relationship("PriceSchedule", back_populates="lot", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="lot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_lots_cadastral_gin", "cadastral_numbers", postgresql_using="gin"),
        UniqueConstraint("auction_id", "lot_number", name="lots_auction_id_lot_number_key"),
    )

class MessageHistory(Base):
    """История полученных сообщений"""
    __tablename__ = "messages"

    guid: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True)
    auction_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("auctions.guid"))
    type: Mapped[str] = mapped_column(String(100))
    date_publish: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_xml: Mapped[str] = mapped_column(Text)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="messages")

class PriceSchedule(Base):
    """График снижения цены"""
    __tablename__ = "price_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"))

    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[float] = mapped_column(Numeric(20, 2))

    lot: Mapped["Lot"] = relationship("Lot", back_populates="price_schedules")

class Document(Base):
    """Extracted data from message attachments (ЕГРН, appraisal reports, etc.)"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    message_guid: Mapped[Optional[UUID]] = mapped_column(PG_UUID, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(50))  # egr_extract, appraisal_report, etc.
    file_size: Mapped[Optional[int]] = mapped_column(Integer)  # Bytes
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON)  # All structured data
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lot: Mapped[Optional["Lot"]] = relationship("Lot", back_populates="documents")


class Lead(Base):
    """Ранние лиды — объекты на стадии инвентаризации/оценки до публикации торгов"""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Должник
    debtor_guid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    debtor_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debtor_inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)

    # Тип сообщения: inventory / evaluation / trade
    message_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Описание объекта из сообщения
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Оценочная стоимость (если есть в сообщении)
    estimated_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Источник
    source_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Статус: new / monitoring / archived
    status: Mapped[str] = mapped_column(String(20), default='new', index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )