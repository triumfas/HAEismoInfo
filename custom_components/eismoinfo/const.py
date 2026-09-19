"""Constants for the EismoInfo integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "eismoinfo"

API_URL: Final = "https://eismoinfo.lt/weather-conditions-service"

CONF_STATION_ID: Final = "station_id"
CONF_CUSTOM_NAME: Final = "custom_name"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 300  # seconds
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 3600

MANUFACTURER: Final = "Lietuvos automobilių kelių direkcija"
MODEL: Final = "Kelių orų stotelė"
