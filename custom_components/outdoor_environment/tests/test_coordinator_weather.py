"""Tests for WeatherCoordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.outdoor_environment.api_client_aq import CannotConnect, InvalidResponse
from custom_components.outdoor_environment.coordinator_weather import WeatherCoordinator


@pytest.mark.asyncio
async def test_coordinator_data_populated(hass, wx_response):
    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherApiClient.fetch",
        new_callable=AsyncMock,
        return_value={k: v for k, v in wx_response["current"].items()},
    ):
        coordinator = WeatherCoordinator(hass, 45.46, 9.19)
        await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data["temperature_2m"] == 22.5


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_cannot_connect(hass):
    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherApiClient.fetch",
        new_callable=AsyncMock,
        side_effect=CannotConnect("timeout"),
    ):
        coordinator = WeatherCoordinator(hass, 45.46, 9.19)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_invalid_response(hass):
    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherApiClient.fetch",
        new_callable=AsyncMock,
        side_effect=InvalidResponse("HTTP 500"),
    ):
        coordinator = WeatherCoordinator(hass, 45.46, 9.19)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_respects_custom_interval(hass):
    coordinator = WeatherCoordinator(hass, 45.46, 9.19, update_interval_minutes=10)
    assert coordinator.update_interval.total_seconds() == 10 * 60
