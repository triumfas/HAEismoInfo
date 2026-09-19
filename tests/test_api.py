"""Tests for the EismoInfo API client."""

from __future__ import annotations

import pytest

from custom_components.eismoinfo.api import (
    EismoInfoApiClient,
    EismoInfoApiError,
    EismoInfoConnectionError,
)
from custom_components.eismoinfo.const import API_URL


async def test_get_stations_parses_fixture(hass, mock_stations_response):
    """The client should parse the fixture into typed Station objects."""
    client = EismoInfoApiClient(async_get_test_session(hass))

    stations = await client.async_get_stations()

    assert set(stations) == {"206", "1021", "157", "1024"}

    normal = stations["206"]
    assert normal.device_name == "Baisogala 144 75,51"
    assert normal.road_number == "144"
    assert normal.air_temperature == pytest.approx(16.5)
    assert normal.friction_coefficient == pytest.approx(0.82)
    assert normal.dew_point is None
    assert normal.collected_at is not None
    assert [w.code for w in normal.warnings] == ["GS", "NMS"]


async def test_get_stations_handles_nulls_and_empty_strings(hass, mock_stations_response):
    """Null and empty-string fields should become None, not crash parsing."""
    client = EismoInfoApiClient(async_get_test_session(hass))

    stations = await client.async_get_stations()

    station = stations["1021"]
    assert station.air_temperature is None
    assert station.road_condition is None  # was ""
    assert station.friction_coefficient is None  # was null


async def test_get_stations_parses_construction_temperatures(hass, mock_stations_response):
    """Construction temperature fields should be parsed when present."""
    client = EismoInfoApiClient(async_get_test_session(hass))

    stations = await client.async_get_stations()

    station = stations["157"]
    assert station.construction_temp_007 == pytest.approx(20.4)
    assert station.construction_temp_050 == pytest.approx(17.31)


async def test_get_stations_connection_error(hass, aioclient_mock):
    """A network failure should raise EismoInfoConnectionError."""
    aioclient_mock.get(API_URL, exc=Exception("boom"))
    client = EismoInfoApiClient(async_get_test_session(hass))

    with pytest.raises((EismoInfoConnectionError, EismoInfoApiError)):
        await client.async_get_stations()


async def test_get_stations_empty_payload(hass, aioclient_mock):
    """An empty station list should raise EismoInfoApiError."""
    aioclient_mock.get(API_URL, json=[])
    client = EismoInfoApiClient(async_get_test_session(hass))

    with pytest.raises(EismoInfoApiError):
        await client.async_get_stations()


def async_get_test_session(hass):
    """Return the shared aiohttp session used by aioclient_mock."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    return async_get_clientsession(hass)
