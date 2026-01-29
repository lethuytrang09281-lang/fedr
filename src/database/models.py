import enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, Integer, Index, UniqueConstraint, Enum as SAEnum
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
    last_processed_date: Mapped[datetime] = mapped_column(DateTime)

class Auction(Base):
    """Торги (Основание для лотов)"""
    __tablename__ = "auctions"

    guid: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True)
    number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    etp_id: Mapped[Optional[str]] = mapped_column(String(255))
    organizer_inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    category_code: Mapped[Optional[str]] = mapped_column(String(20), index=True)

    # Кадастровые номера (GIN индекс для поиска)
    cadastral_numbers: Mapped[List[str]] = mapped_column(ARRAY(String), server_default="{}")

    status: Mapped[LotStatus] = mapped_column(SAEnum(LotStatus), default=LotStatus.ANNOUNCED)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="lots")
    price_schedules: Mapped[List["PriceSchedule"]] = relationship("PriceSchedule", back_populates="lot", cascade="all, delete-orphan")

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
    date_publish: Mapped[datetime] = mapped_column(DateTime, index=True)
    content_xml: Mapped[str] = mapped_column(Text)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="messages")

class PriceSchedule(Base):
    """График снижения цены"""
    __tablename__ = "price_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"))

    date_start: Mapped[datetime] = mapped_column(DateTime)
    date_end: Mapped[datetime] = mapped_column(DateTime)
    price: Mapped[float] = mapped_column(Numeric(20, 2))

    lot: Mapped["Lot"] = relationship("Lot", back_populates="price_schedules")