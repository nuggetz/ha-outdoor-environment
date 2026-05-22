from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .api_client_aq import AirQualityApiClient, CannotConnect, InvalidResponse
from .api_client_weather import WeatherApiClient
from .const import (
    CONF_AQ_UPDATE_INTERVAL,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_GROUP_A_EXTRA,
    CONF_ENABLE_GROUP_A_SUB,
    CONF_ENABLE_GROUP_A_SUB_US,
    CONF_ENABLE_GROUP_D_AGRO,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_SOLAR,
    CONF_ENABLE_UV,
    CONF_ENABLE_WEATHER,
    CONF_IRRIGATION_THRESHOLD,
    CONF_PANEL_AZIMUTH,
    CONF_PANEL_TILT,
    CONF_USE_HOME_LOCATION,
    CONF_WEATHER_UPDATE_INTERVAL,
    DEFAULT_AQ_UPDATE_MINUTES,
    DEFAULT_IRRIGATION_THRESHOLD_MM,
    DEFAULT_WEATHER_UPDATE_MINUTES,
    DOMAIN,
    is_europe,
)

_LOGGER = logging.getLogger(__name__)


class OutdoorEnvironmentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for Outdoor Environment."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_USE_HOME_LOCATION, True):
                lat = self.hass.config.latitude
                lon = self.hass.config.longitude
            else:
                lat = user_input[CONF_LATITUDE]
                lon = user_input[CONF_LONGITUDE]

            user_input[CONF_LATITUDE] = lat
            user_input[CONF_LONGITUDE] = lon

            session = async_get_clientsession(self.hass)
            aq_client = AirQualityApiClient(session, lat, lon)
            wx_client = WeatherApiClient(session, lat, lon)

            aq_ok = wx_ok = True
            try:
                await aq_client.fetch()
            except (CannotConnect, InvalidResponse):
                aq_ok = False
            try:
                await wx_client.fetch()
            except (CannotConnect, InvalidResponse):
                wx_ok = False

            if not aq_ok and not wx_ok:
                errors["base"] = "cannot_connect"
            else:
                if not aq_ok:
                    user_input[CONF_ENABLE_AIR_QUALITY] = False
                    user_input[CONF_ENABLE_POLLEN] = False
                    user_input[CONF_ENABLE_UV] = False
                if not wx_ok:
                    user_input[CONF_ENABLE_WEATHER] = False
                    user_input[CONF_ENABLE_SOLAR] = False

                self._data = user_input

                if user_input.get(CONF_ENABLE_SOLAR, True):
                    return await self.async_step_solar_panel()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Outdoor Environment"),
                    data=self._data,
                )

        in_europe = is_europe(
            self.hass.config.latitude, self.hass.config.longitude
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Outdoor Environment"): TextSelector(),
                vol.Required(CONF_USE_HOME_LOCATION, default=True): BooleanSelector(),
                vol.Optional(CONF_LATITUDE, default=self.hass.config.latitude): NumberSelector(
                    NumberSelectorConfig(min=-90, max=90, step=0.0001, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_LONGITUDE, default=self.hass.config.longitude): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step=0.0001, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ENABLE_AIR_QUALITY, default=True): BooleanSelector(),
                vol.Required(CONF_ENABLE_POLLEN, default=in_europe): BooleanSelector(),
                vol.Required(CONF_ENABLE_UV, default=True): BooleanSelector(),
                vol.Required(CONF_ENABLE_WEATHER, default=True): BooleanSelector(),
                vol.Required(CONF_ENABLE_SOLAR, default=True): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_solar_panel(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("skip_solar_panel"):
                return self.async_create_entry(
                    title=self._data.get(CONF_NAME, "Outdoor Environment"),
                    data=self._data,
                )

            tilt = user_input.get(CONF_PANEL_TILT)
            if tilt is not None:
                self._data[CONF_PANEL_TILT] = float(tilt)
                self._data[CONF_PANEL_AZIMUTH] = float(
                    user_input.get(CONF_PANEL_AZIMUTH, 0)
                )

            return self.async_create_entry(
                title=self._data.get(CONF_NAME, "Outdoor Environment"),
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_PANEL_TILT): NumberSelector(
                    NumberSelectorConfig(min=0, max=90, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_PANEL_AZIMUTH, default=0): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required("skip_solar_panel", default=False): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="solar_panel",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OutdoorEnvironmentOptionsFlow(config_entry)


class OutdoorEnvironmentOptionsFlow(OptionsFlow):
    """Handle options (reconfigure) flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        lat = current.get(CONF_LATITUDE, self.hass.config.latitude)
        lon = current.get(CONF_LONGITUDE, self.hass.config.longitude)
        in_europe = is_europe(lat, lon)

        schema = vol.Schema(
            {
                vol.Required(CONF_USE_HOME_LOCATION, default=current.get(CONF_USE_HOME_LOCATION, True)): BooleanSelector(),
                vol.Optional(CONF_LATITUDE, default=lat): NumberSelector(
                    NumberSelectorConfig(min=-90, max=90, step=0.0001, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_LONGITUDE, default=lon): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step=0.0001, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ENABLE_AIR_QUALITY, default=current.get(CONF_ENABLE_AIR_QUALITY, True)): BooleanSelector(),
                vol.Required(CONF_ENABLE_POLLEN, default=current.get(CONF_ENABLE_POLLEN, in_europe)): BooleanSelector(),
                vol.Required(CONF_ENABLE_UV, default=current.get(CONF_ENABLE_UV, True)): BooleanSelector(),
                vol.Required(CONF_ENABLE_WEATHER, default=current.get(CONF_ENABLE_WEATHER, True)): BooleanSelector(),
                vol.Required(CONF_ENABLE_SOLAR, default=current.get(CONF_ENABLE_SOLAR, True)): BooleanSelector(),
                vol.Optional(CONF_PANEL_TILT, default=current.get(CONF_PANEL_TILT)): NumberSelector(
                    NumberSelectorConfig(min=0, max=90, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_PANEL_AZIMUTH, default=current.get(CONF_PANEL_AZIMUTH, 0)): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_AQ_UPDATE_INTERVAL, default=int(current.get(CONF_AQ_UPDATE_INTERVAL, DEFAULT_AQ_UPDATE_MINUTES))): NumberSelector(
                    NumberSelectorConfig(min=30, max=360, step=30, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_WEATHER_UPDATE_INTERVAL, default=int(current.get(CONF_WEATHER_UPDATE_INTERVAL, DEFAULT_WEATHER_UPDATE_MINUTES))): NumberSelector(
                    NumberSelectorConfig(min=10, max=60, step=5, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_IRRIGATION_THRESHOLD, default=float(current.get(CONF_IRRIGATION_THRESHOLD, DEFAULT_IRRIGATION_THRESHOLD_MM))): NumberSelector(
                    NumberSelectorConfig(min=0.5, max=10.0, step=0.5, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_ENABLE_GROUP_A_SUB, default=current.get(CONF_ENABLE_GROUP_A_SUB, False)): BooleanSelector(),
                vol.Required(CONF_ENABLE_GROUP_A_SUB_US, default=current.get(CONF_ENABLE_GROUP_A_SUB_US, False)): BooleanSelector(),
                vol.Required(CONF_ENABLE_GROUP_A_EXTRA, default=current.get(CONF_ENABLE_GROUP_A_EXTRA, False)): BooleanSelector(),
                vol.Required(CONF_ENABLE_GROUP_D_AGRO, default=current.get(CONF_ENABLE_GROUP_D_AGRO, False)): BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
