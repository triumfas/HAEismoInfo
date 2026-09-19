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
    """A second, concurrently-started flow must not create a duplicate entry.

    Both flows are started (and shown their dropdown) before either commits,
    so both include station 206 as a valid choice - only the *second* one to
    actually submit should be rejected, by the unique_id safety net rather
    than by the dropdown filtering (which only excludes stations that were
    already configured *before* a given flow was opened).
    """
    flow1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result1 = await hass.config_entries.flow.async_configure(
        flow1["flow_id"], {CONF_STATION_ID: "206"}
    )
    assert result1["type"] == FlowResultType.CREATE_ENTRY

    result2 = await hass.config_entries.flow.async_configure(
        flow2["flow_id"], {CONF_STATION_ID: "206"}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass, aioclient_mock):
    """A connection error while listing stations should abort the flow."""
    import aiohttp

    from custom_components.eismoinfo.const import API_URL

    aioclient_mock.get(API_URL, exc=aiohttp.ClientConnectionError("boom"))

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


async def test_options_flow_rejects_empty_name(hass, mock_stations_response):
    """Clearing the name field in options must not save an empty name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206", CONF_CUSTOM_NAME: "Mano stotelė"}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"],
        {CONF_CUSTOM_NAME: "   ", CONF_SCAN_INTERVAL: 120},
    )

    assert options_result["type"] == FlowResultType.FORM
    assert options_result["errors"] == {"base": "name_required"}
    # Nothing was saved - the original name/title must be untouched.
    assert entry.title == "Mano stotelė"
    assert entry.options[CONF_CUSTOM_NAME] == "Mano stotelė"


async def test_reconfigure_changes_station(hass, mock_stations_response):
    """The reconfigure step should retarget an entry at a different station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "206", CONF_CUSTOM_NAME: "Mano stotelė"}
    )
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_STATION_ID] == "206"

    reconfigure_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert reconfigure_result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"], {CONF_STATION_ID: "157"}
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_STATION_ID] == "157"
    # Custom name is untouched by a station change.
    assert entry.title == "Mano stotelė"
