"""
Checko.ru API Client for company research and risk assessment.
Docs: https://checko.ru/integration/api

Correct endpoints (from CLAUDE.md):
- /company?inn=...             → юрлицо (ЕГРЮЛ)
- /entrepreneur?inn=...        → ИП (ЕГРИП)
- /person?inn=...              → физлицо
- /search?by=...&obj=...       → поиск (name/founder-name/leader-name/okved)
- /finances?inn=...            → финотчётность (Росстат + ФНС)
- /legal-cases?inn=...         → арбитражные дела (КАД, задержка 1-2 нед.)
- /enforcements?inn=...        → исполнительные производства (ФССП)
- /inspections?inn=...         → проверки (Генпрокуратура)
- /bankruptcy-messages?inn=... → записи ЕФРСБ
- /fedresurs?inn=...           → сообщения Федресурса
- /contracts?inn=&law=44       → госконтракты (44-ФЗ/94-ФЗ/223-ФЗ)
- /timeline?inn=...            → история изменений
- /bank?bic=...                → банк по БИК
"""
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from src.config import settings

logger = logging.getLogger(__name__)


# Anti-fraud flags mapping (from /company response)
ANTIFRAUD_FLAGS = {
    "МассРуковод": "Массовый руководитель",
    "МассУчред": "Массовый учредитель",
    "ДисквЛицо": "Дисквалифицированное лицо",
    "ДисквЛица": "Дисквалифицированные лица",
    "Санкции": "Санкции",
    "СанкцУчр": "Санкции учредителя",
    "НелегалФин": "Нелегальная финансовая деятельность",
    "НедобПост": "Недобросовестный поставщик",
    "ЮрАдрес.Недост": "Недостоверный юридический адрес",
    "ЮрАдрес.МассАдрес": "Массовый юридический адрес",
}


class CheckoAPIClient:
    """Client for Checko.ru API integration."""

    BASE_URL = "https://api.checko.ru/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Checko API client.

        Args:
            api_key: Checko API key (starts with 'uxa')
        """
        self.api_key = api_key or settings.CHECKO_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=self.headers
            )
        return self.session

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to Checko API.
        Returns None on error, logs all errors.
        """
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/{endpoint}"
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Checko API request failed: {endpoint}, status: {response.status}")
                    return None

                data = await response.json()
                
                # Check meta.status == "ok" before returning data
                if data.get("meta", {}).get("status") != "ok":
                    logger.warning(f"Checko API returned non-ok status for {endpoint}: {data.get('meta', {})}")
                    return None

                return data

        except Exception as e:
            logger.error(f"Error making request to Checko API {endpoint}: {e}")
            return None

    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_company(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get company information by INN.

        Args:
            inn: Company INN (10 or 12 digits)

        Returns:
            Company data including name, director FIO, status, OKVED
        """
        try:
            data = await self._make_request("company", {"inn": inn})
            if not data:
                return None

            company_data = data.get("company", {})
            return {
                "inn": inn,
                "company_name": company_data.get("name"),
                "director_fio": company_data.get("director"),
                "status": company_data.get("status"),
                "okved": company_data.get("okved"),
                "ogrn": company_data.get("ogrn"),
                "registration_date": company_data.get("registration_date"),
                "address": company_data.get("address"),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": company_data
            }

        except Exception as e:
            logger.error(f"Error getting company info for INN {inn}: {e}")
            return None

    async def get_entrepreneur(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get entrepreneur (ИП) information by INN.

        Args:
            inn: Entrepreneur INN (12 digits)

        Returns:
            Entrepreneur data
        """
        try:
            data = await self._make_request("entrepreneur", {"inn": inn})
            if not data:
                return None

            entrepreneur_data = data.get("entrepreneur", {})
            return {
                "inn": inn,
                "full_name": entrepreneur_data.get("full_name"),
                "status": entrepreneur_data.get("status"),
                "okved": entrepreneur_data.get("okved"),
                "ogrn": entrepreneur_data.get("ogrn"),
                "registration_date": entrepreneur_data.get("registration_date"),
                "address": entrepreneur_data.get("address"),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": entrepreneur_data
            }

        except Exception as e:
            logger.error(f"Error getting entrepreneur info for INN {inn}: {e}")
            return None

    async def get_person(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get person information by INN.

        Args:
            inn: Person INN

        Returns:
            Person data
        """
        try:
            data = await self._make_request("person", {"inn": inn})
            if not data:
                return None

            person_data = data.get("person", {})
            return {
                "inn": inn,
                "full_name": person_data.get("full_name"),
                "birth_date": person_data.get("birth_date"),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": person_data
            }

        except Exception as e:
            logger.error(f"Error getting person info for INN {inn}: {e}")
            return None

    async def get_finances(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get financial data for company.

        Args:
            inn: Company INN

        Returns:
            Financial data
        """
        try:
            data = await self._make_request("finances", {"inn": inn})
            if not data:
                return None

            return {
                "inn": inn,
                "finances": data.get("finances", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error getting finances for INN {inn}: {e}")
            return None

    async def get_legal_cases(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get legal cases for company.

        Args:
            inn: Company INN

        Returns:
            Legal cases data
        """
        try:
            data = await self._make_request("legal-cases", {"inn": inn})
            if not data:
                return None

            return {
                "inn": inn,
                "legal_cases": data.get("legal_cases", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error getting legal cases for INN {inn}: {e}")
            return None

    async def get_enforcements(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get enforcement proceedings for company.

        Args:
            inn: Company INN

        Returns:
            Enforcement proceedings data
        """
        try:
            data = await self._make_request("enforcements", {"inn": inn})
            if not data:
                return None

            return {
                "inn": inn,
                "enforcements": data.get("enforcements", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error getting enforcements for INN {inn}: {e}")
            return None

    async def get_bankruptcy(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get bankruptcy messages for company.

        Args:
            inn: Company INN

        Returns:
            Bankruptcy messages data
        """
        try:
            data = await self._make_request("bankruptcy-messages", {"inn": inn})
            if not data:
                return None

            return {
                "inn": inn,
                "bankruptcy_messages": data.get("bankruptcy_messages", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error getting bankruptcy messages for INN {inn}: {e}")
            return None

    async def get_fedresurs(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get Fedresurs messages for company.

        Args:
            inn: Company INN

        Returns:
            Fedresurs messages data
        """
        try:
            data = await self._make_request("fedresurs", {"inn": inn})
            if not data:
                return None

            return {
                "inn": inn,
                "fedresurs_messages": data.get("fedresurs_messages", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error getting Fedresurs messages for INN {inn}: {e}")
            return None

    async def search(self, by: str, obj: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Search in Checko database.

        Args:
            by: Search field (name, founder-name, leader-name, okved)
            obj: Object type (company, entrepreneur, person)
            query: Search query

        Returns:
            Search results
        """
        try:
            params = {
                "by": by,
                "obj": obj,
                "query": query
            }
            
            data = await self._make_request("search", params)
            if not data:
                return None

            return {
                "search_params": params,
                "results": data.get("results", []),
                "source": "Checko",
                "retrieved_at": datetime.utcnow().isoformat(),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error searching Checko with params {params}: {e}")
            return None

    async def get_company_info(self, inn: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive company information by INN.

        Args:
            inn: Company INN (10 or 12 digits)

        Returns:
            Company data including registration, financial info, etc.
        """
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get company info for INN {inn}: {response.status}")
                    return None

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting company info for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/bankruptcy"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get bankruptcy info for INN {inn}: {response.status}")
                    return None

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting bankruptcy info for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/court-cases"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get court cases for INN {inn}: {response.status}")
                    return None

                data = await response.json()
                return data.get("cases", [])

        except Exception as e:
            logger.error(f"Error getting court cases for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/financial"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get financial analysis for INN {inn}: {response.status}")
                    return None

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting financial analysis for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/founders"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get founders for INN {inn}: {response.status}")
                    return None

                data = await response.json()
                return data.get("founders", [])

        except Exception as e:
            logger.error(f"Error getting founders for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/related"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get related companies for INN {inn}: {response.status}")
                    return None

                data = await response.json()
                return data.get("companies", [])

        except Exception as e:
            logger.error(f"Error getting related companies for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/company/{inn}/licenses"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get licenses for INN {inn}: {response.status}")
                    return None

                data = await response.json()
                return data.get("licenses", [])

        except Exception as e:
            logger.error(f"Error getting licenses for INN {inn}: {e}")
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
            session = await self._get_session()
            url = f"{self.BASE_URL}/search"
            params = {"query": company_name, "limit": limit}

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to search companies by name '{company_name}': {response.status}")
                    return None

                data = await response.json()
                return data.get("results", [])

        except Exception as e:
            logger.error(f"Error searching companies by name '{company_name}': {e}")
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
