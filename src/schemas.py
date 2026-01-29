from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class EfrsbMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guid: UUID
    datePublish: datetime
    type: str
    isAnnulled: bool
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