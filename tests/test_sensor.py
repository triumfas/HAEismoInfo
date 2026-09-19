"""Tests for the EismoInfo sensor platform."""

from __future__ import annotations

from homeassistant import config_entries

from custom_components.eismoinfo.const import CONF_STATION_ID, DOMAIN


async def test_sensors_created_and_populated(hass, mock_stations_response):
    """Setting up an entry should create sensors with values from the API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206"}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.baisogala_144_75_51_air_temperature")
    assert state is not None
    assert state.state == "16.5"

    warnings_entity_id = None
    for entity_id in hass.states.async_entity_ids("sensor"):
        if entity_id.endswith("_warnings"):
            warnings_entity_id = entity_id
            break
    assert warnings_entity_id is not None
    warnings_state = hass.states.get(warnings_entity_id)
    assert "Geros oro sąlygos" in warnings_state.state


async def test_disabled_by_default_sensors_are_not_enabled(hass, mock_stations_response):
    """Construction-temperature sensors should be disabled by default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "157"}
    )
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("sensor")
    assert not any("construction_temp" in e for e in entity_ids)


async def test_two_stations_get_independent_devices(hass, mock_stations_response):
    """Two config entries for different stations should not collide."""
    for station_id in ("206", "157"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STATION_ID: station_id}
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
