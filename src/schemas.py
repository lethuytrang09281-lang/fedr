from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class EfrsbMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guid: UUID
    datePublish: datetime
    type: str
    isAnnulled: Optional[bool] = None  # Сделали поле опциональным
    content: str  # XML string
    number: Optional[str] = None


class TradeResponseSchema(BaseModel):
    total: int
    pageItems: List[EfrsbMessageSchema] = Field(alias="pageData")


class AuthToken(BaseModel):
    jwt: str


class LotData(BaseModel):
    description: str
    start_price: float
    cadastral_numbers: List[str]
    message_guid: str
    classifier_code: str
    lot_number: int = 1  # Добавляем номер лота по умолчанию


class AuctionDTO(BaseModel):
    guid: UUID
    number: str
    etp_id: Optional[str] = None
    organizer_inn: Optional[str] = None


class LotDTO(BaseModel):
    lot_number: int = 1
    description: str
    start_price: float
    category_code: Optional[str] = None
    cadastral_numbers: List[str] = []
    status: Optional[str] = "Announced"
    price_schedules: List[dict] = []


class MessageDTO(BaseModel):
    guid: UUID
    type: str
    date_publish: datetime
    content_xml: str


class PriceScheduleDTO(BaseModel):
    """DTO для графика снижения цены"""
    lot_id: int
    date_start: datetime
    date_end: datetime
    price: float
    schedule_html: Optional[str] = None  # HTML-представление графика


class PriceCalculationResult(BaseModel):
    """Результат расчета цены на текущий момент"""
    current_price: float
    next_reduction_date: Optional[datetime] = None
    days_to_next_reduction: Optional[int] = None
    schedule_status: str  # active, completed, not_started