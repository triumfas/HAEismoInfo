"""Binary sensor platform for the EismoInfo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Station
from .const import DOMAIN
from .coordinator import EismoInfoCoordinator
from .entity import EismoInfoEntity

# Warning codes seen in the API response that describe genuinely good
# conditions (see PLAN.md). Any *other* code present means road conditions
# are worth the user's attention - this is a coarse, keyword-free signal
# meant for automations ("notify me if any station on my route is hazardous")
# without having to parse the free-text warnings sensor.
_GOOD_CONDITION_CODES = {"GS", "NMS"}


def _is_hazardous(station: Station) -> bool:
    codes = {w.code for w in station.warnings if w.code}
    return bool(codes - _GOOD_CONDITION_CODES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EismoInfo road-hazard binary sensor for a config entry."""
    coordinator: EismoInfoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EismoInfoRoadHazardBinarySensor(coordinator, entry)])


class EismoInfoRoadHazardBinarySensor(EismoInfoEntity, BinarySensorEntity):
    """Whether this station currently reports a non-'good' road warning."""

    _attr_translation_key = "road_hazard"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: EismoInfoCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._station_id}_road_hazard"

    @property
    def is_on(self) -> bool | None:
        """Return True if the station reports anything but good conditions."""
        station = self.station
        if station is None:
            return None
        return _is_hazardous(station)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw warning names/codes behind the on/off state."""
        station = self.station
        if station is None:
            return None
        return {
            "warnings": [w.name for w in station.warnings if w.name],
            "warning_codes": [w.code for w in station.warnings if w.code],
        }
