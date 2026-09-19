"""DataUpdateCoordinator for the EismoInfo integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EismoInfoApiClient, EismoInfoApiError, Station
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EismoInfoCoordinator(DataUpdateCoordinator[dict[str, Station]]):
    """Coordinator that fetches all weather stations in a single request.

    A single instance is shared by every config entry because the upstream
    API always returns the full list of stations regardless of any query
    parameters.
    """

    def __init__(self, hass: HomeAssistant, client: EismoInfoApiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Station]:
        """Fetch the latest data for all stations."""
        try:
            return await self._client.async_get_stations()
        except EismoInfoApiError as err:
            raise UpdateFailed(f"Error communicating with eismoinfo.lt: {err}") from err
