"""Fixtures for EismoInfo tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for every test."""
    return


@pytest.fixture(name="stations_payload")
def stations_payload_fixture() -> list[dict]:
    """Return the raw JSON payload for a small set of stations."""
    return json.loads((FIXTURES_DIR / "weather-conditions.json").read_text(encoding="utf-8"))


@pytest.fixture(name="mock_stations_response")
def mock_stations_response_fixture(aioclient_mock, stations_payload):
    """Mock the eismoinfo.lt weather conditions endpoint."""
    from custom_components.eismoinfo.const import API_URL

    aioclient_mock.get(API_URL, json=stations_payload)
    return aioclient_mock
