"""API client for the eismoinfo.lt weather conditions service."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import API_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


class EismoInfoApiError(Exception):
    """Generic error raised while talking to the eismoinfo.lt API."""


class EismoInfoConnectionError(EismoInfoApiError):
    """Raised when the API cannot be reached."""


@dataclass(slots=True)
class Warning_:
    """A single warning reported for a station."""

    code: str | None
    name: str | None


@dataclass(slots=True)
class Station:
    """Typed representation of a single weather station reading."""

    id: str
    device_name: str
    road_number: str | None
    road_name: str | None
    road_km: float | None
    latitude: float | None
    longitude: float | None
    collected_at: datetime | None
    air_temperature: float | None
    road_surface_temperature: float | None
    dew_point: float | None
    freezing_point: float | None
    wind_speed_avg: float | None
    wind_speed_max: float | None
    wind_direction: str | None
    precipitation_type: str | None
    precipitation_amount: float | None
    visibility: float | None
    road_condition: str | None
    friction_coefficient: float | None
    construction_temp_007: float | None
    construction_temp_020: float | None
    construction_temp_050: float | None
    construction_temp_080: float | None
    construction_temp_110: float | None
    construction_temp_140: float | None
    construction_temp_170: float | None
    construction_temp_200: float | None
    warnings: list[Warning_] = field(default_factory=list)


def _to_float(value: Any) -> float | None:
    """Convert an API value to float, treating null/empty as unknown."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str | None:
    """Convert an API value to a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_datetime(value: Any) -> datetime | None:
    """Convert a unix timestamp string to an aware UTC datetime."""
    if value is None or value == "":
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _parse_warnings(raw: Any) -> list[Warning_]:
    if not isinstance(raw, list):
        return []
    warnings: list[Warning_] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        warnings.append(
            Warning_(
                code=_to_str(item.get("kodas")),
                name=_to_str(item.get("pavadinimas")),
            )
        )
    return warnings


def _parse_station(raw: dict[str, Any]) -> Station | None:
    station_id = _to_str(raw.get("id"))
    if station_id is None:
        return None

    device_name = _to_str(raw.get("irenginys")) or station_id

    return Station(
        id=station_id,
        device_name=device_name,
        road_number=_to_str(raw.get("numeris")),
        road_name=_to_str(raw.get("pavadinimas")),
        road_km=_to_float(raw.get("kilometras")),
        latitude=_to_float(raw.get("lat")),
        longitude=_to_float(raw.get("lng")),
        collected_at=_to_datetime(raw.get("surinkimo_data_unix")),
        air_temperature=_to_float(raw.get("oro_temperatura")),
        road_surface_temperature=_to_float(raw.get("dangos_temperatura")),
        dew_point=_to_float(raw.get("rasos_taskas")),
        freezing_point=_to_float(raw.get("uzsalimo_taskas")),
        wind_speed_avg=_to_float(raw.get("vejo_greitis_vidut")),
        wind_speed_max=_to_float(raw.get("vejo_greitis_maks")),
        wind_direction=_to_str(raw.get("vejo_kryptis")),
        precipitation_type=_to_str(raw.get("krituliu_tipas")),
        precipitation_amount=_to_float(raw.get("krituliu_kiekis")),
        visibility=_to_float(raw.get("matomumas")),
        road_condition=_to_str(raw.get("kelio_danga")),
        friction_coefficient=_to_float(raw.get("sukibimo_koeficientas")),
        construction_temp_007=_to_float(raw.get("konstrukcijos_temp_007")),
        construction_temp_020=_to_float(raw.get("konstrukcijos_temp_020")),
        construction_temp_050=_to_float(raw.get("konstrukcijos_temp_050")),
        construction_temp_080=_to_float(raw.get("konstrukcijos_temp_080")),
        construction_temp_110=_to_float(raw.get("konstrukcijos_temp_110")),
        construction_temp_140=_to_float(raw.get("konstrukcijos_temp_140")),
        construction_temp_170=_to_float(raw.get("konstrukcijos_temp_170")),
        construction_temp_200=_to_float(raw.get("konstrukcijos_temp_200")),
        warnings=_parse_warnings(raw.get("perspejimai")),
    )


class EismoInfoApiClient:
    """Thin async client for the eismoinfo.lt weather conditions API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with a shared aiohttp session."""
        self._session = session

    async def async_get_stations(self) -> dict[str, Station]:
        """Fetch and parse all weather stations, keyed by station id."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.get(API_URL)
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise EismoInfoConnectionError("Timeout connecting to eismoinfo.lt") from err
        except aiohttp.ClientError as err:
            raise EismoInfoConnectionError(f"Error connecting to eismoinfo.lt: {err}") from err

        if not isinstance(payload, list):
            raise EismoInfoApiError("Unexpected response format from eismoinfo.lt")

        stations: dict[str, Station] = {}
        for raw_station in payload:
            if not isinstance(raw_station, dict):
                continue
            station = _parse_station(raw_station)
            if station is not None:
                stations[station.id] = station

        if not stations:
            raise EismoInfoApiError("No stations returned by eismoinfo.lt")

        return stations
