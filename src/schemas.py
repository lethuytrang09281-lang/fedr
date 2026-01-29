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