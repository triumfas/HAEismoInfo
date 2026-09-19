"""Diagnostics support for the EismoInfo integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_STATION_ID, DOMAIN
from .coordinator import EismoInfoCoordinator

# The eismoinfo.lt API is public and unauthenticated, and config entry
# data/options here (a station id and a user-chosen name) aren't secrets, so
# nothing needs redacting - unlike most integrations' diagnostics.


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for one EismoInfo config entry (station)."""
    coordinator: EismoInfoCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    station_id = entry.data.get(CONF_STATION_ID)
    station = None
    if coordinator is not None and coordinator.data is not None:
        station = coordinator.data.get(station_id)

    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success
            if coordinator is not None
            else None,
            "update_interval_seconds": coordinator.update_interval.total_seconds()
            if coordinator is not None and coordinator.update_interval is not None
            else None,
            "station_count": len(coordinator.data)
            if coordinator is not None and coordinator.data is not None
            else None,
        },
        "station": asdict(station) if station is not None else None,
    }
