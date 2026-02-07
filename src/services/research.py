"""
Research Service - comprehensive property and company analysis.
Combines data from Checko, Rosreestr, and Fedresurs.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from src.services.checko_client import CheckoAPIClient
from src.services.rosreestr import RosreestrEnricher
from src.database.models import Lot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ResearchService:
    """Service for comprehensive property and owner research."""

    def __init__(self, checko_client: CheckoAPIClient, rosreestr_enricher: RosreestrEnricher):
        self.checko = checko_client
        self.rosreestr = rosreestr_enricher

    async def research_property(
        self,
        cadastral_number: str,
        owner_inn: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive property research combining multiple data sources.

        Args:
            cadastral_number: Property cadastral number
            owner_inn: Optional owner INN for company research
            db: Database session for fetching lot data

        Returns:
            Complete research report with all available data
        """
        report = {
            "cadastral_number": cadastral_number,
            "researched_at": datetime.utcnow().isoformat(),
            "property_data": None,
            "owner_data": None,
            "risk_assessment": None,
            "hidden_assets": [],
            "recommendations": []
        }

        # 1. Get property data from Rosreestr
        logger.info(f"Fetching property data for {cadastral_number}")
        property_data = await self.rosreestr.enrich_cadastral_data(cadastral_number)

        if property_data:
            report["property_data"] = {
                "cadastral_number": cadastral_number,
                "area": property_data.get("area"),
                "address": property_data.get("address"),
                "zone_type": property_data.get("zone_type"),
                "restrictions": property_data.get("restrictions", []),
                "encumbrances": property_data.get("encumbrances", []),
                "source": "Rosreestr PKK API",
                "confidence": "high",
                "fetched_at": property_data.get("fetched_at")
            }

            # Check for restrictions
            if property_data.get("restrictions"):
                report["recommendations"].append({
                    "type": "restriction",
                    "severity": "high",
                    "message": f"Property has {len(property_data['restrictions'])} restrictions",
                    "details": property_data["restrictions"]
                })

            # Check for encumbrances
            if property_data.get("encumbrances"):
                report["recommendations"].append({
                    "type": "encumbrance",
                    "severity": "medium",
                    "message": f"Property has {len(property_data['encumbrances'])} encumbrances",
                    "details": property_data["encumbrances"]
                })

        # 2. Research owner company if INN provided
        if owner_inn:
            logger.info(f"Researching owner company INN {owner_inn}")
            owner_research = await self._research_company(owner_inn)
            report["owner_data"] = owner_research

            # Risk assessment
            if owner_research.get("risk_score"):
                risk_data = owner_research["risk_score"]
                report["risk_assessment"] = {
                    "overall_score": risk_data["risk_score"],
                    "level": risk_data["risk_level"],
                    "factors": risk_data["risk_factors"],
                    "checked_at": risk_data["checked_at"]
                }

                # Add recommendations based on risk
                if risk_data["risk_level"] == "HIGH":
                    report["recommendations"].append({
                        "type": "risk",
                        "severity": "critical",
                        "message": "HIGH RISK: Owner company has significant red flags",
                        "details": risk_data["risk_factors"]
                    })
                elif risk_data["risk_level"] == "MEDIUM":
                    report["recommendations"].append({
                        "type": "risk",
                        "severity": "warning",
                        "message": "MEDIUM RISK: Owner company requires additional due diligence",
                        "details": risk_data["risk_factors"]
                    })

            # Find hidden assets (related companies)
            hidden_assets = await self._find_hidden_assets(owner_inn)
            report["hidden_assets"] = hidden_assets

        # 3. Fetch auction data from database if available
        if db:
            lot_data = await self._get_lot_data(db, cadastral_number)
            if lot_data:
                report["auction_data"] = lot_data

        return report

    async def _research_company(self, inn: str) -> Dict[str, Any]:
        """Research company using Checko API."""
        result = {
            "inn": inn,
            "company_info": None,
            "bankruptcy_status": None,
            "court_cases": [],
            "financial_health": None,
            "founders": [],
            "risk_score": None
        }

        # Get company info
        company_info = await self.checko.get_company_info(inn)
        if company_info:
            result["company_info"] = {
                "name": company_info.get("name"),
                "ogrn": company_info.get("ogrn"),
                "status": company_info.get("status"),
                "registration_date": company_info.get("registration_date"),
                "address": company_info.get("address"),
                "source": "Checko API",
                "confidence": "high"
            }

        # Check bankruptcy
        bankruptcy = await self.checko.get_bankruptcy_info(inn)
        if bankruptcy:
            result["bankruptcy_status"] = {
                "status": bankruptcy.get("status"),
                "case_number": bankruptcy.get("case_number"),
                "start_date": bankruptcy.get("start_date"),
                "source": "Checko API"
            }

        # Get court cases
        court_cases = await self.checko.get_court_cases(inn)
        if court_cases:
            result["court_cases"] = [
                {
                    "case_number": case.get("case_number"),
                    "status": case.get("status"),
                    "amount": case.get("amount"),
                    "date": case.get("date"),
                    "source": "Checko API"
                }
                for case in court_cases[:10]  # Limit to top 10
            ]

        # Financial analysis
        financial = await self.checko.get_financial_analysis(inn)
        if financial:
            result["financial_health"] = {
                "revenue": financial.get("revenue"),
                "profit": financial.get("profit"),
                "assets": financial.get("assets"),
                "liabilities": financial.get("liabilities"),
                "year": financial.get("year"),
                "source": "Checko API"
            }

        # Get founders
        founders = await self.checko.get_founders(inn)
        if founders:
            result["founders"] = [
                {
                    "name": f.get("name"),
                    "inn": f.get("inn"),
                    "share": f.get("share"),
                    "source": "Checko API"
                }
                for f in founders
            ]

        # Calculate risk score
        risk_score = await self.checko.calculate_risk_score(inn)
        if risk_score:
            result["risk_score"] = risk_score

        return result

    async def _find_hidden_assets(self, inn: str) -> List[Dict[str, Any]]:
        """Find related companies that might hold hidden assets."""
        hidden_assets = []

        # Get related companies
        related = await self.checko.get_related_companies(inn)
        if not related:
            return hidden_assets

        for company in related:
            # Check if this could be a shell company or hidden asset
            connection_type = company.get("connection_type", "")
            company_inn = company.get("inn")

            if connection_type in ["same_founder", "same_manager", "same_address"]:
                # Get basic info about related company
                info = await self.checko.get_company_info(company_inn)

                if info:
                    hidden_assets.append({
                        "inn": company_inn,
                        "name": info.get("name"),
                        "connection": connection_type,
                        "status": info.get("status"),
                        "suspicion_level": self._calculate_suspicion(info, connection_type),
                        "source": "Checko API - Related Companies"
                    })

        return hidden_assets

    def _calculate_suspicion(self, company_info: Dict, connection_type: str) -> str:
        """Calculate suspicion level for potential hidden asset."""
        score = 0

        # Same address = suspicious
        if connection_type == "same_address":
            score += 2

        # Recently registered
        reg_date = company_info.get("registration_date")
        if reg_date:
            # Simple heuristic: if registered in last 2 years
            score += 1

        # Low/no revenue
        # (would need financial data, simplified here)

        if score >= 3:
            return "high"
        elif score >= 2:
            return "medium"
        return "low"

    async def _get_lot_data(self, db: AsyncSession, cadastral_number: str) -> Optional[Dict[str, Any]]:
        """Fetch lot data from database."""
        try:
            stmt = select(Lot).where(Lot.cadastral_number == cadastral_number)
            result = await db.execute(stmt)
            lot = result.scalar_one_or_none()

            if not lot:
                return None

            return {
                "lot_id": lot.id,
                "message_guid": str(lot.message_guid),
                "price_start": float(lot.price_start) if lot.price_start else None,
                "price_step": float(lot.price_step) if lot.price_step else None,
                "date_auction": lot.date_auction.isoformat() if lot.date_auction else None,
                "debtor_name": lot.debtor_name,
                "manager_company": lot.manager_company,
                "zone": lot.zone,
                "source": "Fedresurs Database"
            }
        except Exception as e:
            logger.error(f"Failed to fetch lot data for {cadastral_number}: {e}")
            return None

    async def research_by_example(self, example_name: str) -> Dict[str, Any]:
        """
        Research using predefined example cases (ОМДА, ОТЭКО, etc.)

        Args:
            example_name: Name of example case

        Returns:
            Research report for the example
        """
        examples = {
            "omda": {
                "cadastral_number": "77:01:0004022:1026",
                "owner_inn": "7713084767",
                "description": "ОМДА - проблемный объект с аренд земли"
            },
            "oteko": {
                "cadastral_number": "77:06:0003002:1234",
                "owner_inn": "7713321151",
                "description": "ОТЭКО - санкционный риск"
            }
        }

        if example_name not in examples:
            return {"error": f"Unknown example: {example_name}"}

        example = examples[example_name]
        return await self.research_property(
            cadastral_number=example["cadastral_number"],
            owner_inn=example["owner_inn"]
        )
