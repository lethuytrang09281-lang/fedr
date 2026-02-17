"""
Rosreestr API Client for cadastral data and property information.
Uses async aiohttp for all requests.
"""
import aiohttp
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import asyncio

from src.config import settings

logger = logging.getLogger(__name__)


class RosreestrClient:
    """Client for Rosreestr API (cadastral data)."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Rosreestr client.

        Args:
            api_key: Optional API key (not always required)
        """
        self.api_key = api_key
        self.base_url = "https://rosreestr.gov.ru/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "FedresursPro/1.0",
                    "Accept": "application/json"
                }
            )
        return self.session

    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get cadastral information by address.

        Args:
            address: Full address string

        Returns:
            Cadastral data including number, area, value, coordinates
        """
        try:
            session = await self._get_session()

            # Search by address
            search_url = f"{self.base_url}/cadastral/search"
            params = {
                "address": address,
                "limit": 1
            }

            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Rosreestr search failed: {response.status}")
                    return None

                data = await response.json()

                if not data or not data.get("results"):
                    logger.info(f"No cadastral data found for address: {address}")
                    return None

                # Get first result
                result = data["results"][0]
                cadastral_number = result.get("cadastral_number")

                if not cadastral_number:
                    logger.warning(f"No cadastral number found for address: {address}")
                    return None

                # Get detailed info by cadastral number
                return await self.get_by_cadastral(cadastral_number)

        except Exception as e:
            logger.error(f"Error getting cadastral data by address '{address}': {e}")
            return None

    async def get_by_cadastral(self, cadastral_num: str) -> Optional[Dict[str, Any]]:
        """
        Get full property information by cadastral number.

        Args:
            cadastral_num: Cadastral number

        Returns:
            Complete property information
        """
        try:
            session = await self._get_session()

            # Get property details
            details_url = f"{self.base_url}/cadastral/{cadastral_num}"
            async with session.get(details_url) as response:
                if response.status != 200:
                    logger.error(f"Rosreestr details failed: {response.status}")
                    return None

                details = await response.json()

                # Get coordinates
                coords = await self._get_coordinates(cadastral_num)

                # Get cadastral value
                value = await self._get_cadastral_value(cadastral_num)

                # Get area
                area = await self._get_area(cadastral_num)

                return {
                    "cadastral_number": cadastral_num,
                    "address": details.get("address"),
                    "type": details.get("type"),
                    "status": details.get("status"),
                    "area": area,
                    "area_unit": details.get("area_unit"),
                    "cadastral_value": value,
                    "coordinates": coords,
                    "year_built": details.get("year_built"),
                    "floor_count": details.get("floor_count"),
                    "purpose": details.get("purpose"),
                    "floor": details.get("floor"),
                    "rooms": details.get("rooms"),
                    "total_area": details.get("total_area"),
                    "living_area": details.get("living_area"),
                    "kitchen_area": details.get("kitchen_area"),
                    "source": "Rosreestr",
                    "retrieved_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting cadastral data for {cadastral_num}: {e}")
            return None

    async def _get_coordinates(self, cadastral_num: str) -> Optional[Dict[str, float]]:
        """Get coordinates for cadastral object."""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/cadastral/{cadastral_num}/coordinates"

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                return {
                    "lat": data.get("latitude"),
                    "lng": data.get("longitude")
                }
        except Exception as e:
            logger.error(f"Error getting coordinates for {cadastral_num}: {e}")
            return None

    async def _get_cadastral_value(self, cadastral_num: str) -> Optional[float]:
        """Get cadastral value."""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/cadastral/{cadastral_num}/value"

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                return data.get("value")
        except Exception as e:
            logger.error(f"Error getting cadastral value for {cadastral_num}: {e}")
            return None

    async def _get_area(self, cadastral_num: str) -> Optional[float]:
        """Get area."""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/cadastral/{cadastral_num}/area"

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                return data.get("area")
        except Exception as e:
            logger.error(f"Error getting area for {cadastral_num}: {e}")
            return None

    async def get_egrn_extract(self, cadastral_num: str) -> Optional[Dict[str, Any]]:
        """
        Get EGRN extract (basic information).

        Args:
            cadastral_num: Cadastral number

        Returns:
            EGRN extract data
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/egrn/extract/{cadastral_num}"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Rosreestr EGRN extract failed: {response.status}")
                    return None

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting EGRN extract for {cadastral_num}: {e}")
            return None

    async def search_by_coordinates(
        self,
        lat: float,
        lng: float,
        radius: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search cadastral objects by coordinates.

        Args:
            lat: Latitude
            lng: Longitude
            radius: Search radius in meters

        Returns:
            List of cadastral objects
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/cadastral/search/coordinates"

            params = {
                "lat": lat,
                "lng": lng,
                "radius": radius
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Rosreestr coordinate search failed: {response.status}")
                    return None

                data = await response.json()
                return data.get("results", [])

        except Exception as e:
            logger.error(f"Error searching by coordinates ({lat}, {lng}): {e}")
            return None

    async def get_object_history(self, cadastral_num: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get history of changes for cadastral object.

        Args:
            cadastral_num: Cadastral number

        Returns:
            List of historical records
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/cadastral/{cadastral_num}/history"

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                return data.get("history", [])

        except Exception as e:
            logger.error(f"Error getting history for {cadastral_num}: {e}")
            return None

    async def validate_cadastral_number(self, cadastral_num: str) -> bool:
        """
        Validate cadastral number format.

        Args:
            cadastral_num: Cadastral number to validate

        Returns:
            True if valid format
        """
        import re
        pattern = r'^\d{2}:\d{2}:\d{6,7}:\d+$'
        return bool(re.match(pattern, cadastral_num))