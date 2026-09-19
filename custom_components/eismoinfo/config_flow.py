"""Config flow for the EismoInfo integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
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

from .api import EismoInfoApiClient, EismoInfoApiError, Station
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


def _station_label(station: Station) -> str:
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
    return " ".join(parts)


class EismoInfoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EismoInfo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Handle the initial step: pick a station and an optional custom name."""
        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass)
        client = EismoInfoApiClient(session)

        try:
            stations = await client.async_get_stations()
        except EismoInfoApiError:
            _LOGGER.exception("Failed to fetch station list from eismoinfo.lt")
            return self.async_abort(reason="cannot_connect")

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

        options = sorted(
            (
                SelectOptionDict(value=station_id, label=_station_label(station))
                for station_id, station in available_stations.items()
            ),
            key=lambda opt: opt["label"],
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(CONF_CUSTOM_NAME): TextSelector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return EismoInfoOptionsFlow()


class EismoInfoOptionsFlow(OptionsFlow):
    """Handle options for an EismoInfo config entry (rename, scan interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Manage the options."""
        if user_input is not None:
            custom_name = user_input[CONF_CUSTOM_NAME].strip()

            self.hass.config_entries.async_update_entry(
                self.config_entry, title=custom_name
            )

            return self.async_create_entry(
                data={
                    CONF_CUSTOM_NAME: custom_name,
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                }
            )

        current_name = self.config_entry.options.get(
            CONF_CUSTOM_NAME, self.config_entry.title
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

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

        return self.async_show_form(step_id="init", data_schema=schema)
