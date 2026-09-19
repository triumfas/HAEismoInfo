"""The EismoInfo integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EismoInfoApiClient
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import EismoInfoCoordinator
from .entity import resolve_device_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# hass.data[DOMAIN] layout:
#   "coordinator": the single EismoInfoCoordinator shared by every entry
#   "lock": asyncio.Lock guarding creation/teardown of the above across the
#           await points in async_setup_entry/async_unload_entry, so two
#           entries being set up/unloaded concurrently can't race each other
#   <entry_id>: that entry's reference to the shared coordinator, looked up
#               by sensor.py instead of the "coordinator" key above so a
#               platform's setup can never be affected by a *different*
#               entry's concurrent unload popping the shared key


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EismoInfo from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    lock: asyncio.Lock = domain_data.setdefault("lock", asyncio.Lock())

    async with lock:
        coordinator: EismoInfoCoordinator | None = domain_data.get("coordinator")

        if coordinator is None:
            # A single shared coordinator is used for all config entries
            # because the upstream API always returns the full list of
            # stations in one request, regardless of any query parameters.
            session = async_get_clientsession(hass)
            client = EismoInfoApiClient(session)
            coordinator = EismoInfoCoordinator(hass, client)
            domain_data["coordinator"] = coordinator
            coordinator.async_add_listener(
                lambda: _async_check_station_availability(hass)
            )

        needs_first_refresh = coordinator.data is None
        if needs_first_refresh:
            # Only block on a real refresh the first time the coordinator is
            # created. Reusing it for a second/third station, or reloading
            # one entry after an options change, must not re-fetch (and must
            # not risk a transient failure aborting an unrelated entry) when
            # the shared coordinator already has good data.
            await coordinator.async_config_entry_first_refresh()

        domain_data[entry.entry_id] = coordinator
        domain_data.setdefault("entries", set()).add(entry.entry_id)
        _async_apply_fastest_scan_interval(hass, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not needs_first_refresh:
        # If we just did the first refresh above, the coordinator listener
        # (registered on creation) already ran this for every entry. Only
        # entries joining an already-populated coordinator need it here.
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
        lock: asyncio.Lock = domain_data.setdefault("lock", asyncio.Lock())

        async with lock:
            domain_data.pop(entry.entry_id, None)

            entries: set[str] = domain_data.get("entries", set())
            entries.discard(entry.entry_id)

            if not entries:
                # Last entry removed - drop the shared coordinator.
                domain_data.pop("coordinator", None)
                domain_data.pop("entries", None)
            else:
                coordinator = domain_data.get("coordinator")
                if coordinator is not None:
                    _async_apply_fastest_scan_interval(hass, coordinator)

            if domain_data.keys() <= {"lock"}:
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
    interval among all entries is used, clamped to [MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL].
    """
    intervals = [
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]
    fastest = min(intervals, default=DEFAULT_SCAN_INTERVAL)
    interval = max(MIN_SCAN_INTERVAL, min(fastest, MAX_SCAN_INTERVAL))
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
        station_id = entry.data[CONF_STATION_ID]
        issue_id = _issue_id(entry)

        if station_id in coordinator.data:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        name = resolve_device_name(entry)
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="station_unavailable",
            translation_placeholders={"name": name, "station_id": station_id},
        )
