from __future__ import annotations

import logging

import aiohttp

from .api_client_aq import CannotConnect, InvalidResponse
from .const import HTTP_TIMEOUT, WEATHER_API_URL

_LOGGER = logging.getLogger(__name__)

WEATHER_VARIABLES: list[str] = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "dew_point_2m",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "visibility",
    "surface_pressure",
    "weather_code",
    "is_day",
    "sunshine_duration",
    "cape",
    "wet_bulb_temperature_2m",
    "vapour_pressure_deficit",
    "et0_fao_evapotranspiration",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "terrestrial_radiation",
]

# Daily totals, fetched on the same call as the current block.
#
# The current block reports evapotranspiration over its own 15-minute interval,
# which is roughly a hundredth of a day's worth. Comparing that against a
# threshold expressed in millimetres per day can never be met, which is why
# Irrigation Needed never once turned on. A day's water balance needs the daily
# figures, so they are requested here and exposed under a "daily_" prefix to
# keep them distinct from the current-interval keys of the same name.
DAILY_VARIABLES: list[str] = [
    "et0_fao_evapotranspiration",
    "precipitation_sum",
]
DAILY_PREFIX = "daily_"


class WeatherApiClient:
    """Async wrapper for the Open-Meteo Forecast API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        panel_tilt: float | None = None,
        panel_azimuth: float | None = None,
    ) -> None:
        self._session = session
        self._lat = lat
        self._lon = lon
        self._panel_tilt = panel_tilt
        self._panel_azimuth = panel_azimuth

    async def fetch(self) -> dict[str, float | None]:
        """Return a flat dict of all weather variables. Null values become None."""
        variables = list(WEATHER_VARIABLES)
        if self._panel_tilt is not None:
            variables.append("global_tilted_irradiance")

        params: dict[str, str | float] = {
            "latitude": self._lat,
            "longitude": self._lon,
            "current": ",".join(variables),
            "daily": ",".join(DAILY_VARIABLES),
            "forecast_days": 1,
            "timezone": "auto",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }
        if self._panel_tilt is not None:
            params["tilt"] = self._panel_tilt
            params["azimuth"] = self._panel_azimuth if self._panel_azimuth is not None else 0

        _LOGGER.debug("Fetching weather data for lat=%s lon=%s", self._lat, self._lon)
        try:
            async with self._session.get(
                WEATHER_API_URL,
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
        result: dict[str, float | None] = {
            key: (float(val) if val is not None else None)
            for key in variables
            if (val := current.get(key)) is not None or key in current
        }

        # The daily block is a list per variable, one entry per forecast day.
        # Only today is requested, so take the first. A missing block is not an
        # error: every current-interval sensor still works without it.
        daily: dict[str, object] = data.get("daily") or {}
        for key in DAILY_VARIABLES:
            values = daily.get(key)
            value = values[0] if isinstance(values, list) and values else None
            result[f"{DAILY_PREFIX}{key}"] = float(value) if value is not None else None
        return result
