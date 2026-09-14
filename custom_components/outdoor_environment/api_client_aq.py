from __future__ import annotations

import logging
from typing import Any

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


# Hourly forecast, fetched on the same call as the current block.
#
# The air quality endpoint has no daily block — `daily=european_aqi_max` answers
# `Cannot initialize ForecastVariableDaily` — so a daily maximum has to be
# aggregated here from the hourly series. With `forecast_days` the series starts
# at local midnight rather than at the current hour (that is `forecast_hours`),
# which is what makes "today's maximum" hold still for the whole day instead of
# drifting down as hours elapse.
AQ_HOURLY_VARIABLES: list[str] = [
    "european_aqi",
    "us_aqi",
]
AQ_FORECAST_DAYS = 2  # today and tomorrow, which is all the sensors expose


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

    async def fetch(self) -> dict[str, Any]:
        """Return the current AQ variables flat, plus the raw hourly forecast.

        Current values stay at the top level as floats, the way every sensor
        reads them. The hourly series is nested under "hourly" untouched: it is
        a list per variable, and turning it into daily maxima is the job of the
        derived sensors, not of the transport.
        """
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "current": ",".join(AQ_VARIABLES),
            "hourly": ",".join(AQ_HOURLY_VARIABLES),
            "forecast_days": AQ_FORECAST_DAYS,
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
        result: dict[str, Any] = {
            key: (float(val) if val is not None else None)
            for key in AQ_VARIABLES
            if (val := current.get(key)) is not None or key in current
        }
        # A missing hourly block is not an error: every current-value sensor
        # still works without it, and the forecast sensors report unknown.
        result["hourly"] = data.get("hourly") or {}
        return result
