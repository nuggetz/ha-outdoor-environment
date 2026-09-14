"""Binary sensors derived from the coordinators.

`Irrigation Needed` and `Frost Risk` answer yes or no. They lived on the sensor
platform until 0.3.0, where they wrote the strings 'True' and 'False' into the
state machine — accepted, because bool subclasses int, but silently dropped from
long-term statistics and awkward to use as an automation trigger.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_IRRIGATION_THRESHOLD,
    DEFAULT_IRRIGATION_THRESHOLD_MM,
    get_api_demand,
)
from .entity import OutdoorComputedEntity

_LOGGER = logging.getLogger(__name__)


class OutdoorBinarySensor(OutdoorComputedEntity, BinarySensorEntity):
    """Base for computed binary sensors."""


class IrrigationNeededBinarySensor(OutdoorBinarySensor):
    _attr_name = "Irrigation Needed"
    # No device_class on purpose. Every candidate says something else: `moisture`
    # renders on as "Wet" and off as "Dry", which is the opposite of what this
    # sensor means — on is "the ground is dry enough to water". `problem` renders
    # on as "Problem", and watering a garden is routine maintenance, not a fault.
    # A device class Home Assistant turns into the wrong word on screen is worse
    # than none, so the entity name carries the meaning and an icon carries the
    # glance value.
    _attr_icon = "mdi:sprinkler-variant"
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_irrigation_needed"
        self._threshold: float = float(
            entry.options.get(
                CONF_IRRIGATION_THRESHOLD,
                entry.data.get(CONF_IRRIGATION_THRESHOLD, DEFAULT_IRRIGATION_THRESHOLD_MM),
            )
        )

    def _daily_balance(self) -> tuple[float, float] | None:
        """Return today's (evapotranspiration, precipitation) totals in mm.

        Both come from the API's daily block. The current block reports each over
        its own 15-minute interval, and comparing that against a threshold in
        millimetres per day is a comparison that can never be true — which is why
        this sensor never once turned on before 0.2.2.
        """
        wx = self._wx()
        et0 = wx.get("daily_et0_fao_evapotranspiration")
        precip = wx.get("daily_precipitation_sum")
        if et0 is None or precip is None:
            return None
        return et0, precip

    @property
    def is_on(self) -> bool | None:
        balance = self._daily_balance()
        if balance is None:
            return None
        et0, precip = balance
        return (et0 - precip) > self._threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        balance = self._daily_balance()
        if balance is None:
            return {}
        et0, precip = balance
        return {
            "et0_today": et0,
            "precipitation_today": precip,
            "deficit_mm": round(et0 - precip, 2),
            "threshold_mm": self._threshold,
            # Both totals are forecasts for the whole calendar day, not what has
            # accumulated so far. That is what an irrigation decision needs — rain
            # due this afternoon should stop the sprinklers this morning — but it
            # means the figures can be revised as the forecast changes.
            "period": "today, full-day forecast",
        }


class FrostRiskBinarySensor(OutdoorBinarySensor):
    _attr_name = "Frost Risk"
    # COLD renders on as "Cold" and off as "Normal", which is exactly what this
    # sensor reports. No inversion, no alarm connotation.
    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_frost_risk"

    @property
    def is_on(self) -> bool | None:
        wx = self._wx()
        apparent = wx.get("apparent_temperature")
        humidity = wx.get("relative_humidity_2m")
        if apparent is None or humidity is None:
            return None
        return apparent < 2.0 and humidity > 80.0


def create_binary_sensors(
    entry: ConfigEntry,
    cfg: dict[str, Any],
    demand_weather: bool | None = None,
) -> list[BinarySensorEntity]:
    """Return binary sensors whose required input API is active."""
    if demand_weather is None:
        _, demand_weather = get_api_demand(cfg)
    if not demand_weather:
        return []
    return [IrrigationNeededBinarySensor(entry), FrostRiskBinarySensor(entry)]


def _async_remove_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entities: list[BinarySensorEntity],
) -> None:
    """Drop registry rows for binary sensors this configuration no longer provides.

    Only the binary_sensor domain is touched. The sensor platform owns its own
    rows and cleans them up itself — which is also what removes the pre-0.3.0
    `sensor.*_irrigation_needed` and `sensor.*_frost_risk` entries once these two
    stop being created there.
    """
    registry = er.async_get(hass)
    expected = {entity.unique_id for entity in entities}

    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.domain != Platform.BINARY_SENSOR:
            continue
        if registry_entry.unique_id in expected:
            continue
        _LOGGER.debug(
            "Removing stale entity %s (unique_id=%s): no longer provided by this configuration",
            registry_entry.entity_id,
            registry_entry.unique_id,
        )
        registry.async_remove(registry_entry.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the binary sensor entities for this config entry."""
    cfg = {**entry.data, **entry.options}
    _, demand_weather = get_api_demand(cfg)

    entities = create_binary_sensors(entry, cfg, demand_weather)
    _async_remove_stale_entities(hass, entry, entities)
    async_add_entities(entities)
