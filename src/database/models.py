import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
from .base import Base  # Импортируем Base из базового файла


# Класс для поддержки UUID в разных диалектах SQL
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class RawMessage(Base):
    """Таблица для хранения сырых данных (Audit Trail)"""
    __tablename__ = "raw_messages"

    guid: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    message_type: Mapped[str] = mapped_column(String(100))
    raw_json: Mapped[dict] = mapped_column(Text)  # SQLite не поддерживает JSON тип напрямую
    xml_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Trade(Base):
    """Сущность Торгов (сообщение о проведении торгов)"""
    __tablename__ = "trades"

    guid: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, unique=True)
    trade_number: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    platform_name: Mapped[Optional[str]] = mapped_column(String(255))
    publish_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_annulled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="active")  # Добавлено поле статуса
    pub_date: Mapped[datetime] = mapped_column(DateTime)  # Дата публикации
    etp_name: Mapped[Optional[str]] = mapped_column(String(255))  # Название площадки

    # Связь с лотами
    lots: Mapped[List["Lot"]] = relationship("Lot", back_populates="trade", cascade="all, delete-orphan")


class Lot(Base):
    """Лоты внутри конкретных торгов"""
    __tablename__ = "lots"

    guid: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    trade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trades.guid", ondelete="CASCADE"))
    lot_number: Mapped[int] = mapped_column(default=1)
    description: Mapped[str] = mapped_column(Text)
    start_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    status: Mapped[Optional[str]] = mapped_column(String(100))
    cadastral_numbers: Mapped[Optional[str]] = mapped_column(Text)  # Кадастровые номера
    classifier_code: Mapped[Optional[str]] = mapped_column(String(50))  # Код классификатора

    # Уникальность: комбинация trade_id и lot_number
    __table_args__ = (UniqueConstraint('trade_id', 'lot_number', name='uq_trade_lot'),)

    trade: Mapped["Trade"] = relationship("Trade", back_populates="lots")