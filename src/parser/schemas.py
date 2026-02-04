import re
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bs4 import BeautifulSoup

class LotDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    lot_number: int = Field(alias="Order")
    description: str = Field(alias="Description")
    start_price: float = Field(alias="StartPrice")
    cadastral_numbers: List[str] = []
    
    @field_validator("description", mode='before')
    @classmethod
    def clean_html(cls, v: Any) -> str:
        if not v: return ""
        soup = BeautifulSoup(str(v), "lxml")
        return " ".join(soup.get_text(separator=" ").split())