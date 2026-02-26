"""
Market Benchmark Service for Antifraud v2.0
Compares lot prices against market data from Sberbank dataset.
"""

from typing import Optional
import asyncpg
from .models import MarketBenchmark, PriceDeviation, RiskLevel


class MarketBenchmarkService:
    """Service for comparing lot prices with market benchmarks."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def get_benchmark(
        self,
        district: str,
        data_source: str = "sberbank",
    ) -> Optional[MarketBenchmark]:
        """Get market benchmark for a district.

        Args:
            district: District name (e.g. "Hamovniki")
            data_source: Data source ("sberbank", "cian", "internal")

        Returns:
            MarketBenchmark or None if not found.
        """
        result = await self.db.fetchrow(
            """
            SELECT
                cadastral_quarter as district,
                median_price_per_sqm,
                mean_price_per_sqm,
                sample_size,
                zone,
                data_source
            FROM market_benchmarks
            WHERE cadastral_quarter = $1
            AND data_source = $2
            ORDER BY last_updated DESC
            LIMIT 1
            """,
            district,
            data_source,
        )

        if result:
            return MarketBenchmark(**dict(result))
        return None

    async def calculate_deviation(
        self,
        lot_price_per_sqm: float,
        district: str,
    ) -> PriceDeviation:
        """Calculate price deviation from market benchmark.

        Args:
            lot_price_per_sqm: Lot price per sqm (RUB)
            district: District name

        Returns:
            PriceDeviation with risk level.
        """
        result = await self.db.fetchrow(
            "SELECT * FROM calculate_price_deviation($1, $2)",
            lot_price_per_sqm,
            district,
        )

        if result and result["deviation_percent"] is not None:
            risk_score = self._risk_level_to_score(result["risk_level"])
            return PriceDeviation(
                lot_price_per_sqm=lot_price_per_sqm,
                market_price_per_sqm=float(result["market_price"]),
                deviation_percent=float(result["deviation_percent"]),
                risk_level=RiskLevel(result["risk_level"]),
                risk_score=risk_score,
            )

        return PriceDeviation(
            lot_price_per_sqm=lot_price_per_sqm,
            market_price_per_sqm=None,
            deviation_percent=None,
            risk_level=RiskLevel.UNKNOWN,
            risk_score=0,
        )

    async def analyze_lot(
        self,
        lot_price: float,
        lot_area: float,
        district: str,
    ) -> PriceDeviation:
        """Full lot price analysis.

        Args:
            lot_price: Total lot price (RUB)
            lot_area: Lot area (sqm)
            district: District name

        Returns:
            PriceDeviation with risk assessment.

        Raises:
            ValueError: If lot_area <= 0.
        """
        if lot_area <= 0:
            raise ValueError("Площадь должна быть > 0")

        lot_price_per_sqm = lot_price / lot_area
        return await self.calculate_deviation(lot_price_per_sqm, district)

    @staticmethod
    def _risk_level_to_score(risk_level: str) -> int:
        """Convert risk level string to numeric score (0-100)."""
        mapping = {
            "LOW": 0,
            "MEDIUM": 10,
            "HIGH": 25,
            "CRITICAL": 40,
            "UNKNOWN": 0,
        }
        return mapping.get(risk_level, 0)
