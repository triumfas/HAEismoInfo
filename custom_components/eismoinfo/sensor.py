"""Sensor platform for the EismoInfo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Station
from .const import DOMAIN
from .coordinator import EismoInfoCoordinator
from .entity import EismoInfoEntity


@dataclass(frozen=True, kw_only=True)
class EismoInfoSensorEntityDescription(SensorEntityDescription):
    """Describes an EismoInfo sensor entity."""

    value_fn: Callable[[Station], Any]
    attrs_fn: Callable[[Station], dict[str, Any]] | None = None
    icon_fn: Callable[[Station], str | None] | None = None
    # Most sensors here measure something the station either does or doesn't
    # currently report; a None value_fn result then means "this station
    # isn't giving us this reading" and should show as *unavailable*, not
    # the more ambiguous "unknown" (which HA shows for any None state).
    # "warnings" is the one exception: None there just means "no active
    # warnings right now", a real and legitimate value - not missing data.
    unavailable_when_none: bool = True


# Lithuanian precipitation/road-condition text isn't a confirmed closed
# enum (see PLAN.md), so icons are chosen by keyword match against whatever
# text the API sends, with a sensible default - rather than an exact
# icons.json state map that would silently stop updating for any value we
# haven't seen yet.
def _precipitation_icon(station: Station) -> str:
    text = (station.precipitation_type or "").lower()
    if "sning" in text or "sniego" in text:
        return "mdi:weather-snowy"
    if "dulksn" in text:
        return "mdi:weather-fog"
    if "migl" in text:
        return "mdi:weather-fog"
    if "lyja" in text or "lietus" in text:
        return "mdi:weather-pouring"
    if "nėra" in text or "nera" in text:
        return "mdi:weather-sunny"
    return "mdi:weather-cloudy"


def _road_condition_icon(station: Station) -> str:
    text = (station.road_condition or "").lower()
    if "apledėj" in text or "ledas" in text or "slidu" in text:
        return "mdi:road-variant"  # no dedicated "icy road" mdi icon
    if "snieg" in text:
        return "mdi:snowflake"
    if "šlap" in text or "drėgn" in text:
        return "mdi:water"
    if "saus" in text:
        return "mdi:road-variant"
    return "mdi:road-variant"


def _warnings_state(station: Station) -> str | None:
    if not station.warnings:
        return None
    return "; ".join(w.name for w in station.warnings if w.name)


def _warnings_attrs(station: Station) -> dict[str, Any]:
    return {
        "warning_codes": [w.code for w in station.warnings if w.code],
    }


def _station_attrs(station: Station) -> dict[str, Any]:
    return {
        "station_id": station.id,
        "station_name": station.device_name,
        "road_number": station.road_number,
        "road_name": station.road_name,
        "road_km": station.road_km,
        "latitude": station.latitude,
        "longitude": station.longitude,
    }


_CONSTRUCTION_TEMP_DEPTHS_CM = ("007", "020", "050", "080", "110", "140", "170", "200")

# Split out from SENSOR_DESCRIPTIONS below so the "one family of similar
# sensors, generated" shape doesn't get lost among the hand-written entries.
_CONSTRUCTION_TEMP_DESCRIPTIONS: tuple[EismoInfoSensorEntityDescription, ...] = tuple(
    EismoInfoSensorEntityDescription(
        key=f"construction_temp_{depth}",
        translation_key=f"construction_temp_{depth}",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
        # attrgetter binds the attribute name by value, so this needs none
        # of the "lambda depth: lambda s: ..." closure tricks a plain
        # per-iteration lambda would require to avoid late binding.
        value_fn=attrgetter(f"construction_temp_{depth}"),
    )
    for depth in _CONSTRUCTION_TEMP_DEPTHS_CM
)


SENSOR_DESCRIPTIONS: tuple[EismoInfoSensorEntityDescription, ...] = (
    EismoInfoSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.air_temperature,
    ),
    EismoInfoSensorEntityDescription(
        key="road_surface_temperature",
        translation_key="road_surface_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.road_surface_temperature,
    ),
    EismoInfoSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.dew_point,
    ),
    EismoInfoSensorEntityDescription(
        key="wind_speed_avg",
        translation_key="wind_speed_avg",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda s: s.wind_speed_avg,
    ),
    EismoInfoSensorEntityDescription(
        key="wind_speed_max",
        translation_key="wind_speed_max",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        value_fn=lambda s: s.wind_speed_max,
    ),
    EismoInfoSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        icon="mdi:compass-outline",
        value_fn=lambda s: s.wind_direction,
    ),
    EismoInfoSensorEntityDescription(
        key="precipitation_type",
        translation_key="precipitation_type",
        icon="mdi:weather-cloudy",
        icon_fn=_precipitation_icon,
        value_fn=lambda s: s.precipitation_type,
    ),
    EismoInfoSensorEntityDescription(
        key="precipitation_amount",
        translation_key="precipitation_amount",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=lambda s: s.precipitation_amount,
    ),
    EismoInfoSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda s: s.visibility,
    ),
    EismoInfoSensorEntityDescription(
        key="road_condition",
        translation_key="road_condition",
        icon="mdi:road-variant",
        icon_fn=_road_condition_icon,
        value_fn=lambda s: s.road_condition,
    ),
    EismoInfoSensorEntityDescription(
        key="friction_coefficient",
        translation_key="friction_coefficient",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:road-variant",
        value_fn=lambda s: s.friction_coefficient,
    ),
    EismoInfoSensorEntityDescription(
        key="warnings",
        translation_key="warnings",
        icon="mdi:alert-outline",
        value_fn=_warnings_state,
        attrs_fn=_warnings_attrs,
        unavailable_when_none=False,  # None here means "no active warnings"
    ),
    EismoInfoSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.collected_at,
        attrs_fn=_station_attrs,
    ),
    EismoInfoSensorEntityDescription(
        key="freezing_point",
        translation_key="freezing_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.freezing_point,
    ),
    *_CONSTRUCTION_TEMP_DESCRIPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EismoInfo sensors for a config entry."""
    # Looked up per-entry (rather than the shared "coordinator" key) so this
    # can never be affected by a *different* entry's concurrent unload.
    coordinator: EismoInfoCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        EismoInfoSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class EismoInfoSensor(EismoInfoEntity, SensorEntity):
    """Representation of a single EismoInfo measurement."""

    entity_description: EismoInfoSensorEntityDescription

    def __init__(
        self,
        coordinator: EismoInfoCoordinator,
        entry: ConfigEntry,
        description: EismoInfoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self._station_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        station = self.station
        if station is None:
            return None
        return self.entity_description.value_fn(station)

    @property
    def available(self) -> bool:
        """Return False if this station simply doesn't report this value.

        Distinguishes "the API never sent this field" (unavailable - a
        station that has no dew-point sensor, say) from "unknown" (which HA
        would otherwise show for any None state, indistinguishable from a
        station or coordinator outage).
        """
        if not super().available:
            return False
        if not self.entity_description.unavailable_when_none:
            return True
        return self.entity_description.value_fn(self.station) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes, if the description defines any."""
        station = self.station
        if station is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(station)

    @property
    def icon(self) -> str | None:
        """Return a value-dependent icon, if the description defines one."""
        station = self.station
        if station is None or self.entity_description.icon_fn is None:
            return self.entity_description.icon
        return self.entity_description.icon_fn(station)
