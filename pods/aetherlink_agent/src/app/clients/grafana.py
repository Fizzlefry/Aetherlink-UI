import logging

from app.config import settings

logger = logging.getLogger(__name__)


class GrafanaClient:
    """Grafana API client for dashboard management and annotations."""

    def __init__(self):
        self.base_url = settings.GRAFANA_URL

    # TODO: Implement Grafana API methods
    # - create_annotation(dashboard_id, time, tags, text)
    # - get_dashboard(uid)
    # - update_dashboard(uid, dashboard_json)

    async def create_annotation(self, dashboard_id: str, time: int, tags: list, text: str):
        """Create a dashboard annotation (to be implemented)."""
        logger.info(f"TODO: Create annotation on dashboard {dashboard_id}: {text}")
        pass


grafana_client = GrafanaClient()
