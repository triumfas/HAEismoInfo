"""The EismoInfo integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EismoInfoApiClient
from .const import (
    CONF_CUSTOM_NAME,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import EismoInfoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EismoInfo from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # A single shared coordinator is used for all config entries because the
    # upstream API always returns the full list of stations in one request.
    domain_data = hass.data[DOMAIN]
    coordinator: EismoInfoCoordinator | None = domain_data.get("coordinator")

    if coordinator is None:
        session = async_get_clientsession(hass)
        client = EismoInfoApiClient(session)
        coordinator = EismoInfoCoordinator(hass, client)
        domain_data["coordinator"] = coordinator
        # Registered once per coordinator lifetime; checks every configured
        # entry after each refresh and raises/clears a Repairs issue for any
        # station that has disappeared from the API response.
        coordinator.async_add_listener(lambda: _async_check_station_availability(hass))

    await coordinator.async_config_entry_first_refresh()

    domain_data.setdefault("entries", set()).add(entry.entry_id)
    _async_apply_fastest_scan_interval(hass, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_check_station_availability(hass)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up when a config entry is permanently removed."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))

        domain_data = hass.data.get(DOMAIN, {})
        entries: set[str] = domain_data.get("entries", set())
        entries.discard(entry.entry_id)

        if not entries:
            # Last entry removed - drop the shared coordinator.
            domain_data.pop("coordinator", None)
            domain_data.pop("entries", None)

        if not domain_data:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_apply_fastest_scan_interval(
    hass: HomeAssistant, coordinator: EismoInfoCoordinator
) -> None:
    """Set the shared coordinator's poll interval to the fastest requested.

    Every config entry may request its own scan interval via its options.
    Since all entries share one coordinator, the fastest (smallest) requested
    interval among all entries is used.
    """
    intervals = [
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]
    interval = max(min(intervals, default=DEFAULT_SCAN_INTERVAL), MIN_SCAN_INTERVAL)
    coordinator.update_interval = timedelta(seconds=interval)


def _issue_id(entry: ConfigEntry) -> str:
    """Return a stable Repairs issue id for a given config entry."""
    return f"station_unavailable_{entry.entry_id}"


def _async_check_station_availability(hass: HomeAssistant) -> None:
    """Raise or clear a Repairs issue for every entry whose station is missing.

    Entities already report as "unavailable" in this case (see
    EismoInfoEntity.available), but that alone is easy to miss. A Repairs
    issue makes it explicit and named, so the user understands *why* a
    station stopped updating instead of silently seeing greyed-out sensors.
    """
    domain_data = hass.data.get(DOMAIN, {})
    coordinator: EismoInfoCoordinator | None = domain_data.get("coordinator")
    if coordinator is None or coordinator.data is None:
        return

    for entry in hass.config_entries.async_entries(DOMAIN):
        station_id = entry.data.get(CONF_STATION_ID)
        issue_id = _issue_id(entry)

        if station_id in coordinator.data:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        name = entry.options.get(CONF_CUSTOM_NAME) or entry.title
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="station_unavailable",
            translation_placeholders={"name": name, "station_id": station_id},
        )
