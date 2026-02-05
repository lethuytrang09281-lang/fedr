import re
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bs4 import BeautifulSoup
from datetime import datetime


class LotDTO(BaseModel):
    """DTO для лота из XML"""
    model_config = ConfigDict(populate_by_name=True)
    lot_number: int = Field(alias="Order", default=1)
    description: str = Field(alias="Description")
    start_price: float = Field(alias="StartPrice")
    classifier_code: str = ""
    cadastral_numbers: List[str] = []

    @field_validator("description", mode='before')
    @classmethod
    def clean_html(cls, v: Any) -> str:
        if not v:
            return ""
        soup = BeautifulSoup(str(v), "lxml")
        return " ".join(soup.get_text(separator=" ").split())


class PriceScheduleDTO(BaseModel):
    """DTO для графика снижения цены (PublicOffer)"""
    lot_guid: str
    period_number: int
    price: float
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


# Alias for backwards compatibility
LotData = LotDTO
