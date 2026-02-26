"""
Pydantic models for Antifraud v2.0
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class MarketBenchmark(BaseModel):
    district: str
    median_price_per_sqm: float
    mean_price_per_sqm: Optional[float] = None
    sample_size: int
    zone: Optional[str] = None
    data_source: str = "sberbank"


class PriceDeviation(BaseModel):
    lot_price_per_sqm: float
    market_price_per_sqm: Optional[float] = None
    deviation_percent: Optional[float] = None
    risk_level: RiskLevel
    risk_score: int = Field(ge=0, le=100)


class FraudFactor(BaseModel):
    type: str  # "market_benchmark", "nlp", "velocity", "manager_karma"
    score: int = Field(ge=0, le=100)
    reason: str
    details: Optional[dict] = None


class FraudAnalysisResult(BaseModel):
    lot_id: int
    fraud_risk_score: int = Field(ge=0, le=100)
    fraud_risk_level: RiskLevel
    factors: List[FraudFactor]

    market_benchmark: Optional[PriceDeviation] = None
    velocity_analysis: Optional[dict] = None
    nlp_red_flags: Optional[List[str]] = None
    manager_karma: Optional[dict] = None
