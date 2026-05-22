"""Tests for AirQualityCoordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.outdoor_environment.api_client_aq import CannotConnect, InvalidResponse
from custom_components.outdoor_environment.coordinator_aq import AirQualityCoordinator


@pytest.mark.asyncio
async def test_coordinator_data_populated(hass, aq_response):
    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityApiClient.fetch",
        new_callable=AsyncMock,
        return_value={k: v for k, v in aq_response["current"].items() if isinstance(v, (int, float)) or v is None},
    ):
        coordinator = AirQualityCoordinator(hass, 45.46, 9.19)
        await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data["european_aqi"] == 32


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_cannot_connect(hass):
    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityApiClient.fetch",
        new_callable=AsyncMock,
        side_effect=CannotConnect("timeout"),
    ):
        coordinator = AirQualityCoordinator(hass, 45.46, 9.19)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_raises_update_failed_on_invalid_response(hass):
    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityApiClient.fetch",
        new_callable=AsyncMock,
        side_effect=InvalidResponse("HTTP 500"),
    ):
        coordinator = AirQualityCoordinator(hass, 45.46, 9.19)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_respects_custom_interval(hass):
    coordinator = AirQualityCoordinator(hass, 45.46, 9.19, update_interval_minutes=30)
    assert coordinator.update_interval.total_seconds() == 30 * 60
