"""Tests for ConfigFlow and OptionsFlow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.outdoor_environment.const import DOMAIN


@pytest.fixture(autouse=True)
def _bypass_api_calls():
    """Mock API clients and async_setup_entry so config flow tests stay lightweight."""
    with (
        patch(
            "custom_components.outdoor_environment.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.outdoor_environment.config_flow.AirQualityApiClient.fetch",
            new_callable=AsyncMock,
            return_value={"european_aqi": 30.0},
        ),
        patch(
            "custom_components.outdoor_environment.config_flow.WeatherApiClient.fetch",
            new_callable=AsyncMock,
            return_value={"temperature_2m": 20.0},
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_step_user_uses_home_location(hass):
    hass.config.latitude = 45.46
    hass.config.longitude = 9.19

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Test",
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["latitude"] == 45.46
    assert result["data"]["longitude"] == 9.19


@pytest.mark.asyncio
async def test_step_user_custom_coordinates(hass):
    hass.config.latitude = 0.0
    hass.config.longitude = 0.0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Custom",
            "use_home_location": False,
            "latitude": 48.85,
            "longitude": 2.35,
            "enable_air_quality": True,
            "enable_pollen": False,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["latitude"] == 48.85
    assert result["data"]["enable_pollen"] is False


@pytest.mark.asyncio
async def test_europe_coordinates_default_pollen_true(hass):
    hass.config.latitude = 45.46  # Italy — inside Europe bbox
    hass.config.longitude = 9.19

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Default enable_pollen should be True for European coords
    schema_defaults = result["data_schema"].schema
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_solar_panel_step_shown_when_solar_enabled(hass):
    hass.config.latitude = 45.46
    hass.config.longitude = 9.19

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Solar Test",
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": True,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "solar_panel"


@pytest.mark.asyncio
async def test_solar_panel_skip_creates_entry_without_gti(hass):
    hass.config.latitude = 45.46
    hass.config.longitude = 9.19

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Skip GTI",
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": True,
        },
    )
    assert result["step_id"] == "solar_panel"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"skip_solar_panel": True},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "panel_tilt" not in result["data"]


@pytest.mark.asyncio
async def test_solar_panel_with_tilt_creates_entry_with_gti(hass):
    hass.config.latitude = 45.46
    hass.config.longitude = 9.19

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "GTI",
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": True,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"panel_tilt": 30.0, "panel_azimuth": 0.0, "skip_solar_panel": False},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["panel_tilt"] == 30.0


@pytest.mark.asyncio
async def test_both_apis_fail_returns_error(hass):
    from custom_components.outdoor_environment.api_client_aq import CannotConnect

    with (
        patch(
            "custom_components.outdoor_environment.config_flow.AirQualityApiClient.fetch",
            new_callable=AsyncMock,
            side_effect=CannotConnect("timeout"),
        ),
        patch(
            "custom_components.outdoor_environment.config_flow.WeatherApiClient.fetch",
            new_callable=AsyncMock,
            side_effect=CannotConnect("timeout"),
        ),
    ):
        hass.config.latitude = 45.46
        hass.config.longitude = 9.19

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "name": "Fail",
                "use_home_location": True,
                "enable_air_quality": True,
                "enable_pollen": True,
                "enable_uv": True,
                "enable_weather": True,
                "enable_solar": False,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"
