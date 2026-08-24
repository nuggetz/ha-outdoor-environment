"""Platform-level tests: entities must write valid states inside Home Assistant.

The unit tests in test_sensor_derived.py exercise `native_value` directly, one
layer below where Home Assistant validates state. `SensorEntity.state` is where
a non-numeric value on a sensor carrying `state_class=measurement` raises, so it
is only reachable by setting the platform up against a real `hass`. Without
these tests a sensor can have a perfectly correct `native_value` and still fail
to be added to Home Assistant on every startup.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.outdoor_environment.const import DOMAIN

_AQ_PATH = (
    "custom_components.outdoor_environment.api_client_aq"
    ".AirQualityApiClient.fetch"
)
_WX_PATH = (
    "custom_components.outdoor_environment.api_client_weather"
    ".WeatherApiClient.fetch"
)


def _floats(current: dict) -> dict[str, float | None]:
    """Mirror what the API clients return: every value cast to float or None."""
    return {
        key: (float(val) if isinstance(val, (int, float)) else None)
        for key, val in current.items()
        if key != "time"
    }


@contextmanager
def _patched_apis(aq: dict, wx: dict):
    with patch(_AQ_PATH, return_value=aq), patch(_WX_PATH, return_value=wx):
        yield


@pytest.fixture
def entry_all_groups() -> MockConfigEntry:
    """Config entry with every optional sensor group turned on."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Outdoor Environment",
        data={
            "name": "Outdoor Environment",
            "latitude": 45.46,
            "longitude": 9.19,
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": True,
            "enable_group_a_sub": True,
            "enable_group_a_sub_us": True,
            "enable_group_a_extra": True,
            "enable_group_d_agro": True,
        },
        options={},
    )


# Weather payload chosen to drive every derived sensor onto its "active" branch:
# frost risk true, irrigation needed true, lightning risk "high".
_WX_EXTREMES: dict[str, float] = {
    "temperature_2m": 1.0,
    "relative_humidity_2m": 90.0,
    "apparent_temperature": 1.0,
    "dew_point_2m": 0.0,
    "wind_speed_10m": 2.0,
    "wind_gusts_10m": 5.0,
    "wind_direction_10m": 180.0,
    "precipitation": 0.0,
    "rain": 0.0,
    "snowfall": 0.0,
    "cloud_cover": 80.0,
    "visibility": 10000.0,
    "surface_pressure": 1000.0,
    "weather_code": 95.0,
    "is_day": 1.0,
    "sunshine_duration": 0.0,
    "cape": 2500.0,
    "wet_bulb_temperature_2m": 1.0,
    "vapour_pressure_deficit": 0.1,
    "et0_fao_evapotranspiration": 5.0,
    "shortwave_radiation": 100.0,
    "direct_radiation": 50.0,
    "diffuse_radiation": 50.0,
    "direct_normal_irradiance": 80.0,
    "terrestrial_radiation": 200.0,
}


def _entity_ids(hass, entry) -> list[str]:
    registry = er.async_get(hass)
    return sorted(
        e.entity_id
        for e in registry.entities.values()
        if e.config_entry_id == entry.entry_id
    )


def _state_errors(caplog) -> list[str]:
    """Entity-platform errors raised while adding or updating entities."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ]


async def _enable_all_entities(hass, entry) -> None:
    """Clear `disabled_by` on every entity, then reload so they get added."""
    registry = er.async_get(hass)
    for entity_id in _entity_ids(hass, entry):
        if registry.entities[entity_id].disabled_by is not None:
            registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_default_config_adds_every_entity_without_error(
    hass, entry_all_groups, aq_response, wx_response, caplog
):
    """Regression: dominant_pollutant used to raise on every startup.

    It returns a pollutant slug ('pm2_5'), but inherited state_class=measurement
    from its base class, so HA rejected the state as non-numeric.
    """
    caplog.set_level(logging.ERROR)
    entry_all_groups.add_to_hass(hass)

    with _patched_apis(_floats(aq_response["current"]), _floats(wx_response["current"])):
        assert await hass.config_entries.async_setup(entry_all_groups.entry_id)
        await hass.async_block_till_done()

    assert _state_errors(caplog) == []

    registry = er.async_get(hass)
    for entity_id in _entity_ids(hass, entry_all_groups):
        if registry.entities[entity_id].disabled_by is not None:
            continue
        assert hass.states.get(entity_id) is not None, f"{entity_id} has no state"


async def test_panel_tilt_options_are_merged_and_reloaded(
    hass, mock_config_entry, aq_response, wx_response_gti
):
    """Non-default panel settings must be merged into setup and reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Outdoor Environment",
        data={
            "name": "Outdoor Environment",
            "latitude": 45.46,
            "longitude": 9.19,
            "use_home_location": True,
            "enable_air_quality": True,
            "enable_pollen": True,
            "enable_uv": True,
            "enable_weather": True,
            "enable_solar": True,
        },
        options={},
    )
    entry.add_to_hass(hass)

    seen_panel_values: list[tuple[float | None, float | None]] = []

    async def _mock_weather_fetch(self):
        seen_panel_values.append((self._panel_tilt, self._panel_azimuth))
        return _floats(wx_response_gti["current"])

    with patch(_AQ_PATH, return_value=_floats(aq_response["current"])), patch(
        "custom_components.outdoor_environment.api_client_weather.WeatherApiClient.fetch",
        new=_mock_weather_fetch,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert seen_panel_values[0] == (None, None)
        registry = er.async_get(hass)
        assert not any(
            entity.config_entry_id == entry.entry_id
            and entity.unique_id == f"{entry.entry_id}_global_tilted_irradiance"
            for entity in registry.entities.values()
        )

        hass.config_entries.async_update_entry(
            entry,
            options={"panel_tilt": 30.0, "panel_azimuth": 0.0},
        )
        await hass.async_block_till_done()

        assert seen_panel_values[-1] == (30.0, 0.0)
        assert any(
            entity.config_entry_id == entry.entry_id
            and entity.unique_id == f"{entry.entry_id}_global_tilted_irradiance"
            for entity in er.async_get(hass).entities.values()
        )

        hass.config_entries.async_update_entry(
            entry,
            options={"panel_tilt": 45.0, "panel_azimuth": 135.0},
        )
        await hass.async_block_till_done()

        assert seen_panel_values[-1] == (45.0, 135.0)


async def test_every_entity_including_disabled_writes_a_state(
    hass, entry_all_groups, aq_response, caplog
):
    """Regression: lightning_risk had the same defect, hidden behind
    entity_registry_enabled_default=False. Enabling it crashed the platform.
    """
    caplog.set_level(logging.ERROR)
    entry_all_groups.add_to_hass(hass)

    aq = _floats(aq_response["current"])
    with _patched_apis(aq, _WX_EXTREMES):
        assert await hass.config_entries.async_setup(entry_all_groups.entry_id)
        await hass.async_block_till_done()
        await _enable_all_entities(hass, entry_all_groups)

    assert _state_errors(caplog) == []

    entity_ids = _entity_ids(hass, entry_all_groups)
    assert len(entity_ids) > 50, "expected the full entity set to be registered"
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) is not None, f"{entity_id} has no state"


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        # o3 has the highest EU sub-AQI (32) in the fixture, so it dominates.
        ("sensor.outdoor_environment_dominant_pollutant", "o3"),
        ("sensor.outdoor_environment_lightning_risk", "high"),
        ("sensor.outdoor_environment_frost_risk", "True"),
        ("sensor.outdoor_environment_irrigation_needed", "True"),
    ],
)
async def test_non_numeric_sensors_expose_their_value(
    hass, entry_all_groups, aq_response, entity_id, expected
):
    """The non-numeric derived sensors must reach HA with their real value."""
    entry_all_groups.add_to_hass(hass)

    with _patched_apis(_floats(aq_response["current"]), _WX_EXTREMES):
        assert await hass.config_entries.async_setup(entry_all_groups.entry_id)
        await hass.async_block_till_done()
        await _enable_all_entities(hass, entry_all_groups)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} was never added"
    assert state.state == expected


@pytest.mark.parametrize(
    ("entity_id", "options"),
    [
        (
            "sensor.outdoor_environment_dominant_pollutant",
            ["pm2_5", "pm10", "no2", "o3", "so2"],
        ),
        (
            "sensor.outdoor_environment_lightning_risk",
            ["none", "low", "medium", "high"],
        ),
    ],
)
async def test_enum_sensors_declare_options_and_no_state_class(
    hass, entry_all_groups, aq_response, entity_id, options
):
    """Categorical sensors are enums, not measurements.

    `options` must cover every value native_value can return, otherwise HA
    raises for the values that are missing from the list.
    """
    entry_all_groups.add_to_hass(hass)

    with _patched_apis(_floats(aq_response["current"]), _WX_EXTREMES):
        assert await hass.config_entries.async_setup(entry_all_groups.entry_id)
        await hass.async_block_till_done()
        await _enable_all_entities(hass, entry_all_groups)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("device_class") == "enum"
    assert state.attributes.get("options") == options
    assert state.attributes.get("state_class") is None


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.outdoor_environment_frost_risk",
        "sensor.outdoor_environment_irrigation_needed",
    ],
)
async def test_boolean_sensors_carry_no_state_class(
    hass, entry_all_groups, aq_response, entity_id
):
    """Booleans must not claim to be measurements.

    HA accepts a bool as numeric (bool subclasses int), so this never raised —
    it silently produced 'True'/'False' states that the recorder then dropped
    from long-term statistics. These move to binary_sensor in 0.2.0.
    """
    entry_all_groups.add_to_hass(hass)

    with _patched_apis(_floats(aq_response["current"]), _WX_EXTREMES):
        assert await hass.config_entries.async_setup(entry_all_groups.entry_id)
        await hass.async_block_till_done()
        await _enable_all_entities(hass, entry_all_groups)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("state_class") is None


def test_every_derived_sensor_is_covered_by_this_module():
    """Guard: a new derived sensor must not silently escape platform testing."""
    from custom_components.outdoor_environment import sensor_derived

    known = {
        "ComfortIndexSensor",
        "HeatIndexSensor",
        "WindChillSensor",
        "DominantPollutantSensor",
        "PollenTotalRiskSensor",
        "VentilationScoreSensor",
        "SolarProductionFactorSensor",
        "IrrigationNeededSensor",
        "FrostRiskSensor",
        "LightningRiskSensor",
    }
    actual = {
        name
        for name, obj in vars(sensor_derived).items()
        if isinstance(obj, type)
        and issubclass(obj, sensor_derived.OutdoorDerivedSensor)
        and obj is not sensor_derived.OutdoorDerivedSensor
    }
    assert actual == known, (
        "Derived sensors changed. Add the new sensor to the platform tests above "
        "and confirm its native_value type matches its state_class."
    )
