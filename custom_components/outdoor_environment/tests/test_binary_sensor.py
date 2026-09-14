"""Tests for the binary_sensor platform, added in 0.3.0.

`Irrigation Needed` and `Frost Risk` moved here from the sensor platform. The
move is a breaking change on entity_id, so the migration itself — the old
`sensor.*` rows going away — is tested here alongside the entities.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.outdoor_environment.binary_sensor import (
    FrostRiskBinarySensor,
    IrrigationNeededBinarySensor,
    create_binary_sensors,
)
from custom_components.outdoor_environment.const import DOMAIN

_AQ_PATH = "custom_components.outdoor_environment.api_client_aq.AirQualityApiClient.fetch"
_WX_PATH = "custom_components.outdoor_environment.api_client_weather.WeatherApiClient.fetch"


def _make_entry(wx_data: dict, options: dict | None = None) -> MagicMock:
    from custom_components.outdoor_environment import OutdoorEnvironmentData

    coord_aq = MagicMock()
    coord_aq.data = {}
    coord_wx = MagicMock()
    coord_wx.data = wx_data

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Outdoor Environment"
    entry.runtime_data = OutdoorEnvironmentData(
        coordinator_aq=coord_aq,
        coordinator_weather=coord_wx,
    )
    entry.data = {}
    entry.options = options or {}
    return entry


@contextmanager
def _patched_apis(aq: dict, wx: dict):
    with patch(_AQ_PATH, return_value=aq), patch(_WX_PATH, return_value=wx):
        yield


def _floats(current: dict) -> dict[str, float | None]:
    return {
        key: (float(val) if isinstance(val, (int, float)) else None)
        for key, val in current.items()
        if key != "time"
    }


# ---------------------------------------------------------------------------
# Irrigation Needed
# ---------------------------------------------------------------------------

def test_irrigation_needed_on():
    entry = _make_entry(
        {"daily_et0_fao_evapotranspiration": 5.0, "daily_precipitation_sum": 1.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    sensor = IrrigationNeededBinarySensor(entry)
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["deficit_mm"] == pytest.approx(4.0)
    assert attrs["et0_today"] == 5.0
    assert attrs["precipitation_today"] == 1.0


def test_irrigation_needed_off():
    entry = _make_entry(
        {"daily_et0_fao_evapotranspiration": 1.0, "daily_precipitation_sum": 3.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    assert IrrigationNeededBinarySensor(entry).is_on is False


def test_irrigation_needed_ignores_the_current_interval_values():
    """The pre-0.2.2 bug: a 15-minute ET0 against a per-day threshold.

    Real figures from Open-Meteo for Milan, 2026-09-14 — 0.11 mm over the current
    interval against 3.59 mm for the day. The current-interval keys alone must
    leave the sensor unknown rather than quietly answering "no" forever.
    """
    entry = _make_entry(
        {"et0_fao_evapotranspiration": 0.11, "precipitation": 0.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    assert IrrigationNeededBinarySensor(entry).is_on is None

    entry = _make_entry(
        {"daily_et0_fao_evapotranspiration": 3.59, "daily_precipitation_sum": 0.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    assert IrrigationNeededBinarySensor(entry).is_on is True


def test_irrigation_needed_states_that_its_figures_are_forecasts():
    entry = _make_entry(
        {"daily_et0_fao_evapotranspiration": 5.0, "daily_precipitation_sum": 1.0}
    )
    assert "forecast" in IrrigationNeededBinarySensor(entry).extra_state_attributes["period"]


def test_irrigation_needed_declares_no_device_class():
    """`moisture` renders on as "Wet", the opposite of what this sensor means.

    Every other candidate is wrong in its own way, so the entity carries no
    device class at all and leans on its name. An icon replaces the glance value
    a device class would have given.
    """
    sensor = IrrigationNeededBinarySensor(_make_entry({}))
    assert sensor.device_class is None
    assert sensor.icon


# ---------------------------------------------------------------------------
# Frost Risk
# ---------------------------------------------------------------------------

def test_frost_risk_on():
    entry = _make_entry({"apparent_temperature": 1.0, "relative_humidity_2m": 90.0})
    assert FrostRiskBinarySensor(entry).is_on is True


def test_frost_risk_off_when_warm():
    entry = _make_entry({"apparent_temperature": 10.0, "relative_humidity_2m": 85.0})
    assert FrostRiskBinarySensor(entry).is_on is False


def test_frost_risk_unknown_without_data():
    assert FrostRiskBinarySensor(_make_entry({})).is_on is None


def test_frost_risk_uses_the_cold_device_class():
    """COLD renders on as "Cold" and off as "Normal" — exactly what it reports."""
    sensor = FrostRiskBinarySensor(_make_entry({}))
    assert sensor.device_class is BinarySensorDeviceClass.COLD


# ---------------------------------------------------------------------------
# Creation gating
# ---------------------------------------------------------------------------

def test_binary_sensors_are_not_created_without_the_weather_api():
    """Both read the weather API, so neither exists when it is never polled."""
    assert create_binary_sensors(_make_entry({}), {}, demand_weather=False) == []

    created = create_binary_sensors(_make_entry({}), {}, demand_weather=True)
    assert {type(entity) for entity in created} == {
        IrrigationNeededBinarySensor,
        FrostRiskBinarySensor,
    }


# ---------------------------------------------------------------------------
# Platform level — the migration itself
# ---------------------------------------------------------------------------

async def test_platform_creates_both_entities(
    hass, mock_config_entry, aq_response, wx_response
):
    mock_config_entry.add_to_hass(hass)

    with _patched_apis(_floats(aq_response["current"]), _floats(wx_response["current"])):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id: entity
        for entity in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
        if entity.domain == "binary_sensor"
    }
    assert f"{mock_config_entry.entry_id}_irrigation_needed" in unique_ids
    assert f"{mock_config_entry.entry_id}_frost_risk" in unique_ids


async def test_pre_migration_sensor_rows_are_removed(
    hass, mock_config_entry, aq_response, wx_response
):
    """The breaking half of the migration.

    An installation upgrading from 0.2.x carries `sensor.*_irrigation_needed`
    and `sensor.*_frost_risk` rows. Nothing creates them any more, so the sensor
    platform's own cleanup must take them out — otherwise they sit `unavailable`
    forever next to the new binary_sensor entities.
    """
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = [
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{mock_config_entry.entry_id}_{suffix}",
            config_entry=mock_config_entry,
        )
        for suffix in ("irrigation_needed", "frost_risk")
    ]

    with _patched_apis(_floats(aq_response["current"]), _floats(wx_response["current"])):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    for entry in legacy:
        assert registry.async_get(entry.entity_id) is None, f"{entry.entity_id} survived"


async def test_stale_binary_sensor_rows_are_removed(
    hass, mock_config_entry, aq_response, wx_response
):
    """The binary_sensor platform owns its domain and prunes it itself."""
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    stale = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_retired_binary_sensor",
        config_entry=mock_config_entry,
    )

    with _patched_apis(_floats(aq_response["current"]), _floats(wx_response["current"])):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get(stale.entity_id) is None
