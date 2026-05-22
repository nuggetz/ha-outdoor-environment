from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client_aq import AirQualityApiClient, CannotConnect, InvalidResponse
from .const import DEFAULT_AQ_UPDATE_MINUTES

_LOGGER = logging.getLogger(__name__)


class AirQualityCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
    """Coordinator for Open-Meteo Air Quality API (AQ + pollen + UV)."""

    def __init__(
        self,
        hass: HomeAssistant,
        lat: float,
        lon: float,
        update_interval_minutes: int = DEFAULT_AQ_UPDATE_MINUTES,
    ) -> None:
        self._client = AirQualityApiClient(
            async_get_clientsession(hass), lat, lon
        )
        super().__init__(
            hass,
            _LOGGER,
            name="outdoor_environment_aq",
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    async def _async_update_data(self) -> dict[str, float | None]:
        try:
            return await self._client.fetch()
        except CannotConnect as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except InvalidResponse as err:
            raise UpdateFailed(f"Invalid response: {err}") from err
