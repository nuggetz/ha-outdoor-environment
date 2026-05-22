from __future__ import annotations

import logging

import aiohttp

from .const import AQ_API_URL, HTTP_TIMEOUT

_LOGGER = logging.getLogger(__name__)

AQ_VARIABLES: list[str] = [
    # AQI composite
    "european_aqi",
    "us_aqi",
    # Sub-AQI EU
    "european_aqi_pm2_5",
    "european_aqi_pm10",
    "european_aqi_no2",
    "european_aqi_o3",
    "european_aqi_so2",
    # Sub-AQI US
    "us_aqi_pm2_5",
    "us_aqi_pm10",
    "us_aqi_no2",
    "us_aqi_co",
    "us_aqi_o3",
    "us_aqi_so2",
    # Pollutants core
    "pm10",
    "pm2_5",
    "nitrogen_dioxide",
    "ozone",
    "sulphur_dioxide",
    "carbon_monoxide",
    "carbon_dioxide",
    "dust",
    "aerosol_optical_depth",
    "ammonia",
    "methane",
    # Pollutants extra
    "formaldehyde",
    "glyoxal",
    "nitrogen_monoxide",
    "peroxyacyl_nitrates",
    "sea_salt_aerosol",
    # UV
    "uv_index",
    "uv_index_clear_sky",
    # Pollen
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "mugwort_pollen",
    "olive_pollen",
    "ragweed_pollen",
]


class CannotConnect(Exception):
    """Raised when the connection to the API fails."""


class InvalidResponse(Exception):
    """Raised when the API returns an unexpected response."""


class AirQualityApiClient:
    """Async wrapper for the Open-Meteo Air Quality API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
    ) -> None:
        self._session = session
        self._lat = lat
        self._lon = lon

    async def fetch(self) -> dict[str, float | None]:
        """Return a flat dict of all AQ variables. Null values become None."""
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "current": ",".join(AQ_VARIABLES),
            "timezone": "auto",
        }
        _LOGGER.debug("Fetching AQ data for lat=%s lon=%s", self._lat, self._lon)
        try:
            async with self._session.get(
                AQ_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
            ) as response:
                if response.status != 200:
                    raise InvalidResponse(f"HTTP {response.status}")
                data = await response.json()
        except aiohttp.ClientError as err:
            raise CannotConnect(str(err)) from err
        except TimeoutError as err:
            raise CannotConnect("timeout") from err

        if "current" not in data:
            raise InvalidResponse("missing 'current' field in response")

        current: dict[str, object] = data["current"]
        return {
            key: (float(val) if val is not None else None)
            for key in AQ_VARIABLES
            if (val := current.get(key)) is not None or key in current
        }
