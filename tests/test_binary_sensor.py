"""Tests for the EismoInfo road-hazard binary sensor."""

from __future__ import annotations

from homeassistant import config_entries

from custom_components.eismoinfo.const import CONF_STATION_ID, DOMAIN


async def test_road_hazard_off_for_good_conditions(hass, mock_stations_response):
    """Station 206 only has GS/NMS ('good') warnings -> hazard should be off."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206"}
    )
    await hass.async_block_till_done()

    hazard_entity_id = None
    for entity_id in hass.states.async_entity_ids("binary_sensor"):
        if entity_id.endswith("road_hazard"):
            hazard_entity_id = entity_id
            break

    assert hazard_entity_id is not None
    assert hass.states.get(hazard_entity_id).state == "off"


async def test_road_hazard_off_for_missing_warnings(hass, mock_stations_response):
    """Station 1021 has no 'perspejimai' key at all -> hazard should be off."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "1021"}
    )
    await hass.async_block_till_done()

    hazard_entity_id = None
    for entity_id in hass.states.async_entity_ids("binary_sensor"):
        if entity_id.endswith("road_hazard"):
            hazard_entity_id = entity_id
            break

    assert hazard_entity_id is not None
    assert hass.states.get(hazard_entity_id).state == "off"
