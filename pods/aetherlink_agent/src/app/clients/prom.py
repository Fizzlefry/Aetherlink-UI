import logging
from datetime import datetime
from typing import Any

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Async Prometheus query client."""

    def __init__(self):
        self.base_url = settings.PROM_URL
        self.client = httpx.AsyncClient(timeout=10.0)

    async def instant(self, ql: str) -> float | None:
        """
        Execute instant query and return scalar value if present.

        Args:
            ql: PromQL query string

        Returns:
            Scalar float value or None if query fails or returns no data
        """
        try:
            url = f"{self.base_url}/api/v1/query"
            params = {"query": ql}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "success":
                logger.warning(f"Prometheus query failed: {data.get('error')}")
                return None

            result = data.get("data", {}).get("result", [])

            if not result:
                logger.debug(f"No data returned for query: {ql}")
                return None

            # Extract scalar value from first result
            value = result[0].get("value", [None, None])[1]

            if value is None:
                return None

            return float(value)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying Prometheus: {e}")
            return None
        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Error parsing Prometheus response: {e}")
            return None

    async def series(
        self, ql: str, start: datetime, end: datetime, step: str = "15s"
    ) -> list[dict[str, Any]]:
        """
        Execute range query and return time series data.

        Args:
            ql: PromQL query string
            start: Start time
            end: End time
            step: Query resolution step

        Returns:
            List of time series with metric labels and values
        """
        try:
            url = f"{self.base_url}/api/v1/query_range"
            params = {"query": ql, "start": start.timestamp(), "end": end.timestamp(), "step": step}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "success":
                logger.warning(f"Prometheus range query failed: {data.get('error')}")
                return []

            return data.get("data", {}).get("result", [])

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying Prometheus range: {e}")
            return []
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing Prometheus range response: {e}")
            return []

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global client instance
prom_client = PrometheusClient()
