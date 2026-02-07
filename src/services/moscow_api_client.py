"""
Moscow Open Data API Client
Documentation: https://apidata.mos.ru/
API Key: a32c7b59-183e-4643-ba40-6259eeb9c8b7
"""
import httpx
from typing import Optional, Dict, Any, List
import logging

from src.config import settings

logger = logging.getLogger(__name__)


class MoscowAPIClient:
    """Client for Moscow Open Data Portal API."""

    BASE_URL = "https://apidata.mos.ru/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Moscow API client.

        Args:
            api_key: API key for Moscow Open Data Portal
        """
        self.api_key = api_key or settings.MOSCOW_API_KEY
        self.headers = {
            "Accept": "application/json",
            "api_key": self.api_key
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def get_dataset_count(self, dataset_id: int) -> Optional[int]:
        """
        Get total number of records in dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            Number of records in dataset
        """
        try:
            url = f"{self.BASE_URL}/datasets/{dataset_id}/count"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get dataset count for {dataset_id}: {e}")
            return None

    async def get_dataset_rows(
        self,
        dataset_id: int,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        orderby: Optional[str] = None,
        filter_expr: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get dataset rows with optional filtering and pagination.

        Args:
            dataset_id: Dataset ID
            top: Limit number of returned records (default: 1000)
            skip: Number of records to skip
            orderby: Field for sorting (e.g., "Caption", "Number desc")
            filter_expr: Filter expression (e.g., "Cells/FieldName eq 'Value'")
            search_query: Search string across all fields

        Returns:
            List of dataset rows
        """
        try:
            url = f"{self.BASE_URL}/datasets/{dataset_id}/rows"
            params = {}

            if top is not None:
                params["$top"] = top
            if skip is not None:
                params["$skip"] = skip
            if orderby:
                params["$orderby"] = orderby
            if filter_expr:
                params["$filter"] = filter_expr
            if search_query:
                params["q"] = search_query

            response = await self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get dataset rows for {dataset_id}: {e}")
            return None

    async def search_cadastral_data(
        self,
        cadastral_number: str,
        dataset_id: int = 658  # Example dataset ID
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for cadastral number in Moscow Open Data.

        Args:
            cadastral_number: Cadastral number to search
            dataset_id: Dataset ID to search in

        Returns:
            List of matching records
        """
        return await self.get_dataset_rows(
            dataset_id=dataset_id,
            search_query=cadastral_number
        )

    async def get_property_data(
        self,
        cadastral_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get property data from Moscow Open Data.

        Args:
            cadastral_number: Cadastral number

        Returns:
            Property data if found
        """
        # Try different datasets that might contain property data
        datasets = [
            658,  # Example: Property registry
            # Add more dataset IDs as needed
        ]

        for dataset_id in datasets:
            try:
                results = await self.search_cadastral_data(
                    cadastral_number=cadastral_number,
                    dataset_id=dataset_id
                )

                if results and len(results) > 0:
                    return {
                        "source": "Moscow Open Data",
                        "dataset_id": dataset_id,
                        "cadastral_number": cadastral_number,
                        "data": results[0],  # First match
                        "total_matches": len(results)
                    }
            except Exception as e:
                logger.warning(f"Error searching dataset {dataset_id}: {e}")
                continue

        return None

    async def get_paginated_dataset(
        self,
        dataset_id: int,
        page_size: int = 1000,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all records from dataset with pagination.

        Args:
            dataset_id: Dataset ID
            page_size: Number of records per page (max 1000)
            max_pages: Maximum number of pages to fetch (None = all)

        Returns:
            List of all records
        """
        all_records = []
        skip = 0
        page = 0

        # Get total count first
        total_count = await self.get_dataset_count(dataset_id)
        if not total_count:
            logger.warning(f"Could not get count for dataset {dataset_id}")
            return []

        logger.info(f"Dataset {dataset_id} has {total_count} records")

        while True:
            if max_pages and page >= max_pages:
                break

            records = await self.get_dataset_rows(
                dataset_id=dataset_id,
                top=page_size,
                skip=skip
            )

            if not records or len(records) == 0:
                break

            all_records.extend(records)
            skip += page_size
            page += 1

            logger.info(f"Fetched page {page}, total records: {len(all_records)}/{total_count}")

            # Stop if we've fetched all records
            if len(all_records) >= total_count:
                break

        return all_records

    async def filter_by_address(
        self,
        dataset_id: int,
        address: str,
        address_field: str = "Address"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Filter dataset by address.

        Args:
            dataset_id: Dataset ID
            address: Address to search for
            address_field: Name of address field in dataset

        Returns:
            List of matching records
        """
        filter_expr = f"Cells/{address_field} eq '{address}'"
        return await self.get_dataset_rows(
            dataset_id=dataset_id,
            filter_expr=filter_expr
        )

    async def get_dataset_info(self, dataset_id: int) -> Optional[Dict[str, Any]]:
        """
        Get metadata about dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dataset metadata
        """
        try:
            url = f"{self.BASE_URL}/datasets/{dataset_id}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get dataset info for {dataset_id}: {e}")
            return None

    def extract_cell_value(self, row: Dict[str, Any], field_name: str) -> Any:
        """
        Extract value from Cells object in row.

        Args:
            row: Row data from API response
            field_name: Name of field to extract

        Returns:
            Field value or None
        """
        cells = row.get("Cells", {})
        return cells.get(field_name)

    def format_row_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format row data to flat structure.

        Args:
            row: Row data from API response

        Returns:
            Formatted data with flattened Cells
        """
        return {
            "id": row.get("Id"),
            "number": row.get("Number"),
            **row.get("Cells", {})
        }
