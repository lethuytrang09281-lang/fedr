"""
Hunter API endpoints for hot deals and lot recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

from src.database.base import get_db_session
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hunter", tags=["hunter"])


@router.get("/hot-deals-demo")
async def get_hot_deals_demo(db: AsyncSession = Depends(get_db_session)):
    """
    Get demo hot deals for testing.

    Returns a list of high-potential auction lots.
    """
    # Demo data for frontend testing
    demo_deals = [
        {
            "id": "demo-001",
            "title": "Коммерческое помещение в ЦАО",
            "price": 15000000,
            "discount": 45,
            "location": "Москва, ЦАО",
            "status": "active",
            "deadline": "2024-03-15",
            "score": 8.5
        },
        {
            "id": "demo-002",
            "title": "Офисное здание на Садовом кольце",
            "price": 120000000,
            "discount": 60,
            "location": "Москва, Садовое кольцо",
            "status": "active",
            "deadline": "2024-03-20",
            "score": 9.2
        }
    ]

    return {"deals": demo_deals, "total": len(demo_deals)}


@router.get("/lots")
async def get_lots(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get filtered and scored lots from database.
    """
    try:
        # TODO: Implement actual database query when orchestrator populates DB
        return {
            "lots": [],
            "total": 0,
            "message": "Orchestrator is running - database will be populated soon"
        }
    except Exception as e:
        logger.error(f"Failed to fetch lots: {e}")
        raise HTTPException(status_code=500, detail=str(e))
