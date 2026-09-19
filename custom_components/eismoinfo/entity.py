"""Base entity for the EismoInfo integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Station
from .const import CONF_CUSTOM_NAME, CONF_STATION_ID, DOMAIN, MANUFACTURER, MODEL
from .coordinator import EismoInfoCoordinator


def resolve_device_name(entry: ConfigEntry) -> str:
    """Return the display name for a station's entry (device, Repairs, ...).

    Single source of truth for "custom name, falling back to the entry
    title" so entity.py, __init__.py's Repairs issue text, etc. can't drift
    into subtly different fallback rules.
    """
    return entry.options.get(CONF_CUSTOM_NAME) or entry.title


class EismoInfoEntity(CoordinatorEntity[EismoInfoCoordinator]):
    """Base class for all EismoInfo entities, tied to one station/config entry."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EismoInfoCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the entity for a given config entry (= one station)."""
        super().__init__(coordinator)
        self._entry = entry
        self._station_id: str = entry.data[CONF_STATION_ID]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            name=resolve_device_name(entry),
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url="https://eismoinfo.lt",
        )

    @property
    def station(self) -> Station | None:
        """Return the current data for this entity's station, if available."""
        return self.coordinator.data.get(self._station_id)

    @property
    def available(self) -> bool:
        """Return True if the coordinator succeeded and this station is present."""
        return super().available and self.station is not None
