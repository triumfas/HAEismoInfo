"""Config flow for the EismoInfo integration."""

from __future__ import annotations

import logging
from math import asin, cos, radians, sin, sqrt
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import EismoInfoApiClient, EismoInfoApiError, EismoInfoConnectionError, Station
from .const import (
    CONF_CUSTOM_NAME,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


EARTH_RADIUS_KM = 6371.0


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two WGS84 points, in km."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _station_distance_km(hass: HomeAssistant, station: Station) -> float | None:
    """Return the station's distance from HA's configured home location."""
    if station.latitude is None or station.longitude is None:
        return None
    if hass.config.latitude is None or hass.config.longitude is None:
        return None
    return _distance_km(
        hass.config.latitude, hass.config.longitude, station.latitude, station.longitude
    )


def _station_label(station: Station, distance_km: float | None) -> str:
    parts = [station.device_name]
    extra = " ".join(
        p
        for p in (
            station.road_number,
            f"({station.road_name})" if station.road_name else None,
            f"{station.road_km} km" if station.road_km is not None else None,
        )
        if p
    )
    if extra:
        parts.append(f"- {extra}")
    if distance_km is not None:
        parts.append(f"[~{distance_km:.0f} km]")
    return " ".join(parts)


class _EismoInfoFlowMixin:
    """Shared helpers for the config flow and its reconfigure step."""

    hass: HomeAssistant

    async def _async_get_stations_or_abort(
        self,
    ) -> tuple[dict[str, Station], None] | tuple[None, ConfigFlowResult]:
        """Fetch all stations, or return a ready-to-return abort result."""
        session = async_get_clientsession(self.hass)
        client = EismoInfoApiClient(session)

        try:
            stations = await client.async_get_stations()
        except EismoInfoConnectionError:
            _LOGGER.exception("Failed to connect to eismoinfo.lt")
            return None, self.async_abort(reason="cannot_connect")  # type: ignore[attr-defined]
        except EismoInfoApiError:
            _LOGGER.exception("eismoinfo.lt returned an unexpected response")
            return None, self.async_abort(reason="unknown")  # type: ignore[attr-defined]

        return stations, None

    def _build_station_options(
        self, stations: dict[str, Station]
    ) -> list[SelectOptionDict]:
        """Build a station dropdown, nearest-to-home first when possible."""
        distances = {
            station_id: _station_distance_km(self.hass, station)
            for station_id, station in stations.items()
        }
        ordered_ids = sorted(
            stations,
            key=lambda sid: (
                distances[sid] if distances[sid] is not None else float("inf"),
                _station_label(stations[sid], None),
            ),
        )
        return [
            SelectOptionDict(
                value=station_id,
                label=_station_label(stations[station_id], distances[station_id]),
            )
            for station_id in ordered_ids
        ]


class EismoInfoConfigFlow(_EismoInfoFlowMixin, ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EismoInfo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: pick a station and an optional custom name."""
        errors: dict[str, str] = {}

        stations, abort = await self._async_get_stations_or_abort()
        if abort is not None:
            return abort

        already_configured = {
            entry.data[CONF_STATION_ID] for entry in self._async_current_entries()
        }
        available_stations = {
            station_id: station
            for station_id, station in stations.items()
            if station_id not in already_configured
        }

        if not available_stations:
            return self.async_abort(reason="no_stations_available")

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            station = stations.get(station_id)

            if station is None:
                errors["base"] = "invalid_station"
            else:
                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()

                custom_name = (user_input.get(CONF_CUSTOM_NAME) or "").strip()
                title = custom_name or station.device_name

                return self.async_create_entry(
                    title=title,
                    data={CONF_STATION_ID: station_id},
                    options={
                        CONF_CUSTOM_NAME: custom_name or station.device_name,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=self._build_station_options(available_stations),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_CUSTOM_NAME): TextSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user point this entry at a different station.

        The name and scan-interval options are left untouched - only which
        station this entry/device tracks can change here.
        """
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        stations, abort = await self._async_get_stations_or_abort()
        if abort is not None:
            return abort

        already_configured = {
            entry.data[CONF_STATION_ID]
            for entry in self._async_current_entries()
            if entry.entry_id != reconfigure_entry.entry_id
        }
        available_stations = {
            station_id: station
            for station_id, station in stations.items()
            if station_id not in already_configured
        }

        if not available_stations:
            return self.async_abort(reason="no_stations_available")

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            station = stations.get(station_id)

            if station is None:
                errors["base"] = "invalid_station"
            else:
                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_STATION_ID: station_id},
                )

        current_station_id = reconfigure_entry.data[CONF_STATION_ID]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID, default=current_station_id
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=self._build_station_options(available_stations),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return EismoInfoOptionsFlow()


class EismoInfoOptionsFlow(OptionsFlow):
    """Handle options for an EismoInfo config entry (rename, scan interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        current_name = self.config_entry.options.get(
            CONF_CUSTOM_NAME, self.config_entry.title
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        if user_input is not None:
            custom_name = user_input[CONF_CUSTOM_NAME].strip()

            if not custom_name:
                # Unlike the initial "add station" step, there is no API
                # device_name lying around here to silently fall back to -
                # ask the user for a name instead of saving an empty one
                # (which would leave the device/Repairs text blank).
                errors["base"] = "name_required"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=custom_name
                )

                return self.async_create_entry(
                    data={
                        CONF_CUSTOM_NAME: custom_name,
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    }
                )

            current_name = user_input[CONF_CUSTOM_NAME]
            current_interval = user_input[CONF_SCAN_INTERVAL]

        schema = vol.Schema(
            {
                vol.Required(CONF_CUSTOM_NAME, default=current_name): TextSelector(),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=30,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
