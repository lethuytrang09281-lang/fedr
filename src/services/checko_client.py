"""
Checko.ru API Client for company research and risk assessment.
Docs: https://checko.ru/integration/api
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CheckoAPIClient:
    """Client for Checko.ru API integration."""

    BASE_URL = "https://api.checko.ru/v2"

    def __init__(self, api_key: str):
        """
        Initialize Checko API client.

        Args:
            api_key: Checko API key (starts with 'uxa')
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def get_company_info(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive company information by INN.

        Args:
            inn: Company INN (10 or 12 digits)

        Returns:
            Company data including registration, financial info, etc.
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get company info for INN {inn}: {e}")
            return None

    async def get_bankruptcy_info(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get bankruptcy proceedings information.

        Args:
            inn: Company INN

        Returns:
            Bankruptcy status, cases, dates
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/bankruptcy"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get bankruptcy info for INN {inn}: {e}")
            return None

    async def get_court_cases(self, inn: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get court cases involving the company.

        Args:
            inn: Company INN

        Returns:
            List of court cases with status, dates, amounts
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/court-cases"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("cases", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get court cases for INN {inn}: {e}")
            return None

    async def get_financial_analysis(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get financial analysis and ratios.

        Args:
            inn: Company INN

        Returns:
            Financial metrics, profitability, liquidity ratios
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/financial"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get financial analysis for INN {inn}: {e}")
            return None

    async def get_founders(self, inn: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get company founders and beneficiaries.

        Args:
            inn: Company INN

        Returns:
            List of founders with shares, INNs, relations
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/founders"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("founders", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get founders for INN {inn}: {e}")
            return None

    async def get_related_companies(self, inn: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get related companies (same founders, managers, addresses).

        Args:
            inn: Company INN

        Returns:
            List of related companies with connection type
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/related"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("companies", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get related companies for INN {inn}: {e}")
            return None

    async def get_licenses(self, inn: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get company licenses and permits.

        Args:
            inn: Company INN

        Returns:
            List of active licenses
        """
        try:
            url = f"{self.BASE_URL}/company/{inn}/licenses"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("licenses", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get licenses for INN {inn}: {e}")
            return None

    async def search_by_name(self, company_name: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Search companies by name.

        Args:
            company_name: Company name (partial match)
            limit: Max results to return

        Returns:
            List of matching companies with INNs
        """
        try:
            url = f"{self.BASE_URL}/search"
            params = {"query": company_name, "limit": limit}
            response = await self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to search companies by name '{company_name}': {e}")
            return None

    async def calculate_risk_score(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Calculate comprehensive risk score (0-100).

        Args:
            inn: Company INN

        Returns:
            Risk score with breakdown by categories
        """
        try:
            # Get all available data
            company_info = await self.get_company_info(inn)
            bankruptcy = await self.get_bankruptcy_info(inn)
            court_cases = await self.get_court_cases(inn)
            financial = await self.get_financial_analysis(inn)

            if not company_info:
                return None

            risk_score = 0
            risk_factors = []

            # Bankruptcy risk (0-40 points)
            if bankruptcy:
                if bankruptcy.get("status") == "active":
                    risk_score += 40
                    risk_factors.append("Active bankruptcy proceedings")
                elif bankruptcy.get("status") == "finished":
                    risk_score += 20
                    risk_factors.append("Previous bankruptcy")

            # Court cases risk (0-20 points)
            if court_cases and len(court_cases) > 0:
                active_cases = [c for c in court_cases if c.get("status") == "active"]
                if len(active_cases) > 10:
                    risk_score += 20
                    risk_factors.append(f"High litigation activity ({len(active_cases)} cases)")
                elif len(active_cases) > 5:
                    risk_score += 10
                    risk_factors.append(f"Moderate litigation ({len(active_cases)} cases)")

            # Financial health risk (0-30 points)
            if financial:
                revenue = financial.get("revenue", 0)
                profit = financial.get("profit", 0)

                if revenue == 0:
                    risk_score += 15
                    risk_factors.append("No reported revenue")

                if profit < 0:
                    risk_score += 15
                    risk_factors.append("Negative profit")

            # Company status risk (0-10 points)
            status = company_info.get("status", "").lower()
            if status in ["liquidation", "reorganization"]:
                risk_score += 10
                risk_factors.append(f"Company status: {status}")

            # Determine risk level
            if risk_score >= 70:
                risk_level = "HIGH"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            return {
                "inn": inn,
                "risk_score": min(risk_score, 100),
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "checked_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to calculate risk score for INN {inn}: {e}")
            return None
