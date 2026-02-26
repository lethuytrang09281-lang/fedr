"""
Research API endpoints for property and company analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from src.database.base import get_db_session
from src.services.checko_client import CheckoAPIClient
from src.services.research import ResearchService
from src.services.enricher import RosreestrEnricher
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


# Dependency injection
async def get_checko_client():
    """Get Checko API client."""
    if not settings.CHECKO_API_KEY:
        raise HTTPException(status_code=500, detail="CHECKO_API_KEY not configured")
    client = CheckoAPIClient(settings.CHECKO_API_KEY)
    try:
        yield client
    finally:
        await client.close()


async def get_research_service(checko: CheckoAPIClient = Depends(get_checko_client)):
    """Get Research Service."""
    rosreestr = RosreestrEnricher(api_key=settings.PARSER_API_KEY)
    return ResearchService(checko_client=checko, rosreestr_enricher=rosreestr)


@router.get("/property/{cadastral_number}")
async def research_property(
    cadastral_number: str,
    owner_inn: Optional[str] = Query(None, description="Optional owner INN for deep research"),
    service: ResearchService = Depends(get_research_service),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Comprehensive property research.

    Combines data from:
    - Rosreestr (property details, restrictions, encumbrances)
    - Checko (owner company analysis, bankruptcy risk)
    - Fedresurs (auction data)

    Returns full research report with recommendations.
    """
    try:
        report = await service.research_property(
            cadastral_number=cadastral_number,
            owner_inn=owner_inn,
            db=db
        )
        return report
    except Exception as e:
        logger.error(f"Research failed for {cadastral_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/{inn}")
async def research_company(
    inn: str,
    service: ResearchService = Depends(get_research_service)
):
    """
    Company research by INN.

    Returns:
    - Company info (name, OGRN, status, address)
    - Bankruptcy status
    - Court cases
    - Financial health
    - Founders
    - Risk score (0-100)
    """
    try:
        report = await service._research_company(inn)
        return report
    except Exception as e:
        logger.error(f"Company research failed for INN {inn}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples/{example_name}")
async def research_example(
    example_name: str,
    service: ResearchService = Depends(get_research_service)
):
    """
    Research using predefined examples.

    Available examples:
    - omda: ОМДА case (leased land, fragmentation scheme)
    - oteko: ОТЭКО case (sanctions risk, beneficiary issues)
    """
    try:
        report = await service.research_by_example(example_name)
        return report
    except Exception as e:
        logger.error(f"Example research failed for {example_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/{inn}")
async def calculate_risk_score(
    inn: str,
    checko: CheckoAPIClient = Depends(get_checko_client)
):
    """
    Calculate bankruptcy risk score for company.

    Returns:
    - risk_score: 0-100 (0 = lowest risk, 100 = highest)
    - risk_level: LOW | MEDIUM | HIGH
    - risk_factors: List of identified issues
    """
    try:
        risk_data = await checko.calculate_risk_score(inn)
        if not risk_data:
            raise HTTPException(status_code=404, detail=f"Company not found: {inn}")
        return risk_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk calculation failed for INN {inn}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hidden-assets/{inn}")
async def find_hidden_assets(
    inn: str,
    service: ResearchService = Depends(get_research_service)
):
    """
    Find potential hidden assets via related companies.

    Identifies:
    - Companies with same founders
    - Companies with same managers
    - Companies at same address
    - Shell companies
    """
    try:
        assets = await service._find_hidden_assets(inn)
        return {
            "inn": inn,
            "potential_hidden_assets": assets,
            "count": len(assets)
        }
    except Exception as e:
        logger.error(f"Hidden assets search failed for INN {inn}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
