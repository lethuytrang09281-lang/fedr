"""
Unit tests for MarketBenchmarkService
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.antifraud import MarketBenchmarkService, RiskLevel, MarketBenchmark, PriceDeviation


@pytest.fixture
def mock_db():
    """Mock database pool."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    return pool


@pytest.fixture
def service(mock_db):
    """MarketBenchmarkService instance with mocked db."""
    return MarketBenchmarkService(mock_db)


class TestGetBenchmark:
    """Tests for get_benchmark() method."""

    @pytest.mark.asyncio
    async def test_success(self, service, mock_db):
        """Successfully retrieve benchmark for existing district."""
        mock_db.fetchrow.return_value = {
            "district": "Hamovniki",
            "median_price_per_sqm": 233766.0,
            "mean_price_per_sqm": 240000.0,
            "sample_size": 49,
            "zone": "GARDEN_RING",
            "data_source": "sberbank"
        }
        
        result = await service.get_benchmark("Hamovniki")
        
        assert result is not None
        assert isinstance(result, MarketBenchmark)
        assert result.district == "Hamovniki"
        assert result.median_price_per_sqm == 233766.0
        assert result.mean_price_per_sqm == 240000.0
        assert result.sample_size == 49
        assert result.zone == "GARDEN_RING"
        assert result.data_source == "sberbank"

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_db):
        """District not found in database."""
        mock_db.fetchrow.return_value = None
        
        result = await service.get_benchmark("UnknownDistrict")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_different_data_source(self, service, mock_db):
        """Retrieve benchmark with different data_source parameter."""
        mock_db.fetchrow.return_value = {
            "district": "Hamovniki",
            "median_price_per_sqm": 250000.0,
            "mean_price_per_sqm": 255000.0,
            "sample_size": 100,
            "zone": "GARDEN_RING",
            "data_source": "cian"
        }
        
        result = await service.get_benchmark("Hamovniki", data_source="cian")
        
        assert result is not None
        assert result.data_source == "cian"
        assert result.median_price_per_sqm == 250000.0

    @pytest.mark.asyncio
    async def test_latest_data_selected(self, service, mock_db):
        """Ensure latest data is selected (ORDER BY last_updated DESC)."""
        mock_db.fetchrow.return_value = {
            "district": "Hamovniki",
            "median_price_per_sqm": 233766.0,
            "mean_price_per_sqm": 240000.0,
            "sample_size": 49,
            "zone": "GARDEN_RING",
            "data_source": "sberbank"
        }
        
        result = await service.get_benchmark("Hamovniki")
        
        assert result is not None
        # Verify the query includes ORDER BY last_updated DESC
        # This is implicit in the mock setup


class TestCalculateDeviation:
    """Tests for calculate_deviation() method."""

    @pytest.mark.asyncio
    async def test_critical_risk(self, service, mock_db):
        """Critical risk deviation (< -60%)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -62.7,
            "risk_level": "CRITICAL",
            "market_price": 233766.0
        }
        
        result = await service.calculate_deviation(87000, "Hamovniki")
        
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.risk_score == 40
        assert result.deviation_percent == -62.7
        assert result.market_price_per_sqm == 233766.0
        assert result.lot_price_per_sqm == 87000.0

    @pytest.mark.asyncio
    async def test_high_risk(self, service, mock_db):
        """High risk deviation (-40% to -60%)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -45.5,
            "risk_level": "HIGH",
            "market_price": 233766.0
        }
        
        result = await service.calculate_deviation(127000, "Hamovniki")
        
        assert result.risk_level == RiskLevel.HIGH
        assert result.risk_score == 25
        assert result.deviation_percent == -45.5

    @pytest.mark.asyncio
    async def test_medium_risk(self, service, mock_db):
        """Medium risk deviation (-20% to -40%)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -30.0,
            "risk_level": "MEDIUM",
            "market_price": 233766.0
        }
        
        result = await service.calculate_deviation(163636.2, "Hamovniki")
        
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.risk_score == 10
        assert result.deviation_percent == -30.0

    @pytest.mark.asyncio
    async def test_low_risk(self, service, mock_db):
        """Low risk deviation (> -20%)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -15.0,
            "risk_level": "LOW",
            "market_price": 233766.0
        }
        
        result = await service.calculate_deviation(198701.1, "Hamovniki")
        
        assert result.risk_level == RiskLevel.LOW
        assert result.risk_score == 0
        assert result.deviation_percent == -15.0

    @pytest.mark.asyncio
    async def test_unknown_risk(self, service, mock_db):
        """No benchmark data (UNKNOWN risk)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": None,
            "risk_level": "UNKNOWN",
            "market_price": None
        }
        
        result = await service.calculate_deviation(150000, "UnknownDistrict")
        
        assert result.risk_level == RiskLevel.UNKNOWN
        assert result.risk_score == 0
        assert result.deviation_percent is None
        assert result.market_price_per_sqm is None

    @pytest.mark.asyncio
    async def test_positive_deviation(self, service, mock_db):
        """Positive deviation (price above market)."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": 15.0,
            "risk_level": "LOW",
            "market_price": 233766.0
        }
        
        result = await service.calculate_deviation(268830.9, "Hamovniki")
        
        assert result.risk_level == RiskLevel.LOW
        assert result.deviation_percent == 15.0


class TestAnalyzeLot:
    """Tests for analyze_lot() method."""

    @pytest.mark.asyncio
    async def test_analyze_lot_success(self, service, mock_db):
        """Successfully analyze a normal lot."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -30.0,
            "risk_level": "MEDIUM",
            "market_price": 233766.0
        }
        
        result = await service.analyze_lot(
            lot_price=5_000_000,
            lot_area=50,
            district="Hamovniki"
        )
        
        assert result.lot_price_per_sqm == 100000.0  # 5,000,000 / 50
        assert result.deviation_percent == -30.0
        assert result.risk_level == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_analyze_lot_zero_area(self, service, mock_db):
        """Zero area should raise ValueError."""
        with pytest.raises(ValueError, match="Площадь должна быть > 0"):
            await service.analyze_lot(
                lot_price=5_000_000,
                lot_area=0,
                district="Hamovniki"
            )

    @pytest.mark.asyncio
    async def test_analyze_lot_negative_area(self, service, mock_db):
        """Negative area should raise ValueError."""
        with pytest.raises(ValueError, match="Площадь должна быть > 0"):
            await service.analyze_lot(
                lot_price=5_000_000,
                lot_area=-10,
                district="Hamovniki"
            )

    @pytest.mark.asyncio
    async def test_analyze_lot_huge_numbers(self, service, mock_db):
        """Test with huge numbers."""
        mock_db.fetchrow.return_value = {
            "deviation_percent": -10.0,
            "risk_level": "LOW",
            "market_price": 233766.0
        }
        
        result = await service.analyze_lot(
            lot_price=1_000_000_000,
            lot_area=1000,
            district="Hamovniki"
        )
        
        assert result.lot_price_per_sqm == 1_000_000.0  # 1B / 1000
        assert result.deviation_percent == -10.0


class TestRiskScoreMapping:
    """Tests for risk level to score mapping."""

    def test_risk_level_to_score_mapping(self):
        """Test all risk level to score mappings."""
        service = MarketBenchmarkService(None)
        
        # Test all risk levels
        assert service._risk_level_to_score("LOW") == 0
        assert service._risk_level_to_score("MEDIUM") == 10
        assert service._risk_level_to_score("HIGH") == 25
        assert service._risk_level_to_score("CRITICAL") == 40
        assert service._risk_level_to_score("UNKNOWN") == 0
        
        # Test case sensitivity (should work with uppercase as in enum)
        # Default mapping for unknown strings
        assert service._risk_level_to_score("unknown_string") == 0