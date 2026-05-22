from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client_aq import CannotConnect, InvalidResponse
from .api_client_weather import WeatherApiClient
from .const import DEFAULT_WEATHER_UPDATE_MINUTES

_LOGGER = logging.getLogger(__name__)


class WeatherCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
    """Coordinator for Open-Meteo Forecast API (weather + solar)."""

    def __init__(
        self,
        hass: HomeAssistant,
        lat: float,
        lon: float,
        update_interval_minutes: int = DEFAULT_WEATHER_UPDATE_MINUTES,
        panel_tilt: float | None = None,
        panel_azimuth: float | None = None,
    ) -> None:
        self._client = WeatherApiClient(
            async_get_clientsession(hass), lat, lon, panel_tilt, panel_azimuth
        )
        super().__init__(
            hass,
            _LOGGER,
            name="outdoor_environment_weather",
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    async def _async_update_data(self) -> dict[str, float | None]:
        try:
            return await self._client.fetch()
        except CannotConnect as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except InvalidResponse as err:
            raise UpdateFailed(f"Invalid response: {err}") from err
