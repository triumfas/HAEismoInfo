"""Tests for the EismoInfo config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eismoinfo.const import (
    CONF_CUSTOM_NAME,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DOMAIN,
)


async def test_user_flow_creates_entry_with_custom_name(hass, mock_stations_response):
    """Selecting a station with a custom name should create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION_ID: "206", CONF_CUSTOM_NAME: "Mano stotelė"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mano stotelė"
    assert result["data"] == {CONF_STATION_ID: "206"}
    assert result["options"][CONF_CUSTOM_NAME] == "Mano stotelė"
    assert result["options"][CONF_SCAN_INTERVAL] == 300


async def test_user_flow_defaults_to_api_name(hass, mock_stations_response):
    """Leaving the custom name blank should fall back to the API device name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "157"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kartena A11 120,7"


async def test_user_flow_duplicate_station_aborts(hass, mock_stations_response):
    """Adding the same station twice should abort with already_configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {CONF_STATION_ID: "206"}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass, aioclient_mock):
    """A connection error while listing stations should abort the flow."""
    from custom_components.eismoinfo.const import API_URL

    aioclient_mock.get(API_URL, exc=Exception("boom"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_renames_entry(hass, mock_stations_response):
    """The options flow should update the entry title and scan interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206"}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert options_result["type"] == FlowResultType.FORM

    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"],
        {CONF_CUSTOM_NAME: "Naujas pavadinimas", CONF_SCAN_INTERVAL: 120},
    )

    assert options_result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.title == "Naujas pavadinimas"
    assert entry.options[CONF_SCAN_INTERVAL] == 120
