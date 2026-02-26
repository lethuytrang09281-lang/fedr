# src/services/hunter/models.py

"""
Pydantic модели для Investment Hunter Engine
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class InvestmentFactorType(str, Enum):
    """Типы факторов инвестиционной привлекательности"""
    GEOGRAPHY = "geography"
    DISCOUNT = "discount"
    LIQUIDITY = "liquidity"
    TIMING = "timing"
    EARLY_BIRD = "early_bird"
    HIDDEN_GEM = "hidden_gem"


class DealRecommendation(str, Enum):
    """Рекомендации по сделке"""
    HOT_DEAL = "HOT_DEAL"           # 🔥 70+
    GOOD_OPPORTUNITY = "GOOD_OPPORTUNITY"  # ✅ 50-70
    CONSIDER = "CONSIDER"           # 🤔 30-50
    PASS = "PASS"                   # ⛔ <30


class InvestmentFactor(BaseModel):
    """Один фактор привлекательности"""
    type: InvestmentFactorType
    score: int = Field(ge=0, le=50)
    reason: str
    details: Optional[dict] = None


class InvestmentScore(BaseModel):
    """Результат оценки инвестиционной привлекательности"""
    investment_score: int = Field(ge=0, le=100)
    factors: List[InvestmentFactor]
    discount_percent: Optional[float] = None
    
    # География
    district: str
    zone: Optional[str] = None
    
    # Ликвидность
    asset_type: Optional[str] = None
    liquidity_category: Optional[str] = None


class DealScore(BaseModel):
    """Финальная оценка сделки (Investment - Fraud)"""
    deal_score: int = Field(ge=0, le=100)
    recommendation: DealRecommendation
    
    # Компоненты
    investment_score: int
    fraud_risk_score: int
    fraud_penalty: int
    
    # Детали
    investment_factors: List[InvestmentFactor]
    fraud_factors: Optional[List[dict]] = None
    
    # Объяснение
    explanation: str


class HuntingOpportunity(BaseModel):
    """Возможность для охотника"""
    lot_id: int
    deal_score: int
    recommendation: DealRecommendation
    
    # Ключевые данные
    district: str
    start_price: float
    area: float
    price_per_sqm: float
    market_price_per_sqm: Optional[float] = None
    discount_percent: Optional[float] = None
    
    # Стратегия обнаружения
    hunting_strategy: str  # "Early Bird", "Hidden Gem", "Bottom Fisher", etc.
    
    # Причины
    why_interesting: List[str]
    risks: Optional[List[str]] = None
