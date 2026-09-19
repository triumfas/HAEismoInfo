"""Sensor platform for the EismoInfo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
        icon="mdi:weather-rainy",
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
    *(
        EismoInfoSensorEntityDescription(
            key=f"construction_temp_{depth}",
            translation_key=f"construction_temp_{depth}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_registry_enabled_default=False,
            value_fn=(lambda depth: lambda s: getattr(s, f"construction_temp_{depth}"))(
                depth
            ),
        )
        for depth in ("007", "020", "050", "080", "110", "140", "170", "200")
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EismoInfo sensors for a config entry."""
    coordinator: EismoInfoCoordinator = hass.data[DOMAIN]["coordinator"]

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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes, if the description defines any."""
        station = self.station
        if station is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(station)
