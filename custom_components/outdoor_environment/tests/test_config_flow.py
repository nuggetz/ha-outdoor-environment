"""Tests for ConfigFlow and OptionsFlow."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.outdoor_environment.const import CONF_PANEL_TILT, DOMAIN


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


def _frontend_payload(schema: vol.Schema) -> dict[str, Any]:
    """Build the payload the frontend sends when the user touches nothing.

    Every field is submitted with the value the form was prefilled with, and a
    field with nothing to prefill is left out of the payload entirely — which is
    what an empty number box does.
    """
    payload: dict[str, Any] = {}
    for key in schema.schema:
        value = (key.description or {}).get("suggested_value", vol.UNDEFINED)
        if value is vol.UNDEFINED:
            default = getattr(key, "default", vol.UNDEFINED)
            value = default() if callable(default) else vol.UNDEFINED
        if value is vol.UNDEFINED or value is None:
            continue
        payload[str(key.schema)] = value
    return payload


@pytest.mark.asyncio
async def test_options_schema_has_no_none_defaults(hass, mock_config_entry):
    """A default that resolves to None is fed back into its selector and fails.

    Guards the whole form, not just panel_tilt: any future optional field that
    prefills from an absent config key has to use suggested_value instead.
    """
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    offenders = [
        str(key.schema)
        for key in result["data_schema"].schema
        if callable(getattr(key, "default", None)) and key.default() is None
    ]
    assert offenders == []


@pytest.mark.asyncio
async def test_options_flow_saves_when_panel_tilt_is_unset(hass, mock_config_entry):
    """Issue #16: no panel tilt configured must not block the whole form."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    user_input = _frontend_payload(result["data_schema"])
    assert "panel_tilt" not in user_input  # nothing to prefill, box left empty
    user_input["enable_aq_forecast"] = True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options["enable_aq_forecast"] is True

    # Reopening the form has to show the toggle the user left on.
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    reopened = _frontend_payload(result["data_schema"])
    assert reopened["enable_aq_forecast"] is True


@pytest.mark.asyncio
async def test_options_flow_keeps_configured_panel_tilt(hass, mock_config_entry_gti):
    """Submitting the prefilled form must not drop an existing tilt."""
    mock_config_entry_gti.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry_gti.entry_id
    )
    user_input = _frontend_payload(result["data_schema"])
    assert user_input["panel_tilt"] == 30.0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry_gti.options["panel_tilt"] == 30.0


@pytest.mark.asyncio
async def test_options_flow_clears_panel_tilt(hass, mock_config_entry_gti):
    """Emptying the tilt box removes the panel, including the one in entry.data."""
    mock_config_entry_gti.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry_gti.entry_id
    )
    user_input = _frontend_payload(result["data_schema"])
    del user_input["panel_tilt"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    cfg = {**mock_config_entry_gti.data, **mock_config_entry_gti.options}
    assert cfg[CONF_PANEL_TILT] is None
