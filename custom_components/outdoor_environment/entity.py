"""Shared entity plumbing for every platform of this integration.

Both the sensor and binary_sensor platforms expose entities that own no
coordinator of their own and read from one or both of them. Keeping that
subscription logic in one place is not tidiness: a derived entity must
subscribe only to the coordinators it actually reads, because Home Assistant
stops scheduling refreshes for a coordinator with no listeners. A second copy
of that rule is a second chance to get it wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION, DOMAIN

if TYPE_CHECKING:
    from . import OutdoorEnvironmentData


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Every entity of a config entry belongs to one device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Open-Meteo",
        model="Outdoor Environment",
        configuration_url="https://open-meteo.com",
    )


class OutdoorComputedEntity(Entity):
    """Base for entities computed from coordinator data rather than owning one.

    Subclasses declare which coordinators they read through `coordinator_types`
    and are subscribed to those only.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, *, coordinator_types: tuple[str, ...]) -> None:
        self._entry = entry
        self._coordinator_types = coordinator_types
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        data: OutdoorEnvironmentData = self._entry.runtime_data
        for coordinator_type in self._coordinator_types:
            if coordinator_type == "aq":
                self.async_on_remove(data.coordinator_aq.async_add_listener(self._handle_update))
            elif coordinator_type == "weather":
                self.async_on_remove(
                    data.coordinator_weather.async_add_listener(self._handle_update)
                )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    def _aq(self) -> dict[str, float | None]:
        data: OutdoorEnvironmentData = self._entry.runtime_data
        return data.coordinator_aq.data or {}

    def _wx(self) -> dict[str, float | None]:
        data: OutdoorEnvironmentData = self._entry.runtime_data
        return data.coordinator_weather.data or {}
