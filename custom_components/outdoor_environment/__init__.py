from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_AQ_UPDATE_INTERVAL,
    CONF_PANEL_AZIMUTH,
    CONF_PANEL_TILT,
    CONF_WEATHER_UPDATE_INTERVAL,
    DEFAULT_AQ_UPDATE_MINUTES,
    DEFAULT_WEATHER_UPDATE_MINUTES,
    DOMAIN,
)
from .coordinator_aq import AirQualityCoordinator
from .coordinator_weather import WeatherCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class OutdoorEnvironmentData:
    """Runtime data stored on the config entry."""

    coordinator_aq: AirQualityCoordinator
    coordinator_weather: WeatherCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Outdoor Environment from a config entry."""
    lat: float = entry.data[CONF_LATITUDE]
    lon: float = entry.data[CONF_LONGITUDE]

    # Options take precedence over data for interval settings
    aq_interval = int(
        entry.options.get(
            CONF_AQ_UPDATE_INTERVAL,
            entry.data.get(CONF_AQ_UPDATE_INTERVAL, DEFAULT_AQ_UPDATE_MINUTES),
        )
    )
    weather_interval = int(
        entry.options.get(
            CONF_WEATHER_UPDATE_INTERVAL,
            entry.data.get(CONF_WEATHER_UPDATE_INTERVAL, DEFAULT_WEATHER_UPDATE_MINUTES),
        )
    )
    panel_tilt: float | None = entry.data.get(CONF_PANEL_TILT)
    panel_azimuth: float | None = entry.data.get(CONF_PANEL_AZIMUTH)

    coordinator_aq = AirQualityCoordinator(hass, lat, lon, aq_interval)
    coordinator_weather = WeatherCoordinator(
        hass, lat, lon, weather_interval, panel_tilt, panel_azimuth
    )

    try:
        await coordinator_aq.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"AQ API unavailable: {err}") from err

    try:
        await coordinator_weather.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Weather API unavailable: {err}") from err

    entry.runtime_data = OutdoorEnvironmentData(
        coordinator_aq=coordinator_aq,
        coordinator_weather=coordinator_weather,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
