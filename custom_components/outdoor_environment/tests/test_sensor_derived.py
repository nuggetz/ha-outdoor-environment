"""Tests for derived sensor calculations (pure functions and sensor values)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.outdoor_environment.const import (
    calc_ventilation_score,
    heat_index,
    solar_production_factor,
    wind_chill,
)
from custom_components.outdoor_environment.sensor_derived import (
    ComfortIndexSensor,
    DominantPollutantSensor,
    HeatIndexSensor,
    LightningRiskSensor,
    PollenTotalRiskSensor,
    SolarProductionFactorSensor,
    VentilationScoreSensor,
    WindChillSensor,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

def test_heat_index_formula():
    result = heat_index(32.0, 70.0)
    assert 38.0 < result < 46.0


def test_wind_chill_formula():
    result = wind_chill(-5.0, 30.0)
    assert result < -5.0


def test_solar_production_factor_full_cloud():
    assert solar_production_factor(100.0, 500.0) == 0.0


def test_solar_production_factor_clear_sky_max():
    result = solar_production_factor(0.0, 1000.0)
    assert result == 1.0


def test_solar_production_factor_partial_cloud():
    result = solar_production_factor(50.0, 1000.0)
    assert result == pytest.approx(0.5)


def test_ventilation_score_good_conditions():
    score, recommendation, reason = calc_ventilation_score(
        european_aqi=10.0, wind_speed=18.0, precipitation=0.0
    )
    assert score >= 60
    assert recommendation == "ventilate"


def test_ventilation_score_poor_aqi():
    score, recommendation, reason = calc_ventilation_score(
        european_aqi=95.0, wind_speed=5.0, precipitation=1.0
    )
    assert recommendation == "keep_closed"
    assert reason == "aqi_poor"


def test_ventilation_score_rain():
    score, recommendation, reason = calc_ventilation_score(
        european_aqi=15.0, wind_speed=5.0, precipitation=2.0
    )
    assert recommendation in ("keep_closed", "neutral")


# ---------------------------------------------------------------------------
# Sensor value tests via mocked entry.runtime_data
# ---------------------------------------------------------------------------

def _make_entry(aq_data: dict, wx_data: dict, options: dict | None = None):
    """Create a minimal mock config entry with both coordinators populated."""
    from unittest.mock import MagicMock

    from custom_components.outdoor_environment import OutdoorEnvironmentData

    coord_aq = MagicMock()
    coord_aq.data = aq_data
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


def _comfort(apparent, **extra):
    entry = _make_entry({}, {"apparent_temperature": apparent, **extra})
    return ComfortIndexSensor(entry).native_value


def test_comfort_index_plateau_reads_full_marks():
    """Anything inside the comfortable band is comfortable, with no false precision."""
    assert _comfort(18.0) == 100
    assert _comfort(21.0) == 100
    assert _comfort(24.0) == 100


def test_comfort_index_clamps_outside_both_limits():
    assert _comfort(40.0) == 0
    assert _comfort(55.0) == 0
    assert _comfort(-10.0) == 0
    assert _comfort(-30.0) == 0


def test_comfort_index_falls_off_in_both_directions():
    assert _comfort(32.0) == 50.0
    assert _comfort(4.0) == 50.0
    assert _comfort(27.0) > _comfort(32.0)
    assert _comfort(10.0) > _comfort(4.0)


def test_comfort_index_matches_the_value_promised_in_issue_12():
    """The reporter was told their reading becomes 67.5 instead of 1.9."""
    assert _comfort(29.2) == 67.5


def test_comfort_index_is_continuous_over_the_whole_domain():
    """The bug in issue #12 was a 64-point jump across a tenth of a degree.

    Three formulas were switched between on hard thresholds, so the value leapt
    at every boundary. Sweeping the domain in small steps asserts that no such
    boundary exists any more, whatever the implementation.
    """
    previous = None
    apparent = -30.0
    while apparent <= 55.0:
        value = _comfort(round(apparent, 2))
        if previous is not None:
            assert abs(value - previous) < 0.5, f"jump at {apparent}: {previous} -> {value}"
        previous = value
        apparent += 0.05


def test_comfort_index_ignores_the_old_branch_thresholds():
    """Same apparent temperature must give the same score, whatever else moves.

    The old implementation switched formula at 27 C, at 40% humidity and at
    10 C with wind, so these pairs straddle every one of those thresholds.
    """
    for apparent, low, high in (
        (29.0, {"temperature_2m": 27.0, "relative_humidity_2m": 40.0, "wind_speed_10m": 4.8},
                {"temperature_2m": 27.1, "relative_humidity_2m": 40.1, "wind_speed_10m": 4.9}),
        (5.0, {"temperature_2m": 10.1, "relative_humidity_2m": 60.0, "wind_speed_10m": 4.0},
               {"temperature_2m": 9.9, "relative_humidity_2m": 60.0, "wind_speed_10m": 20.0}),
    ):
        assert _comfort(apparent, **low) == _comfort(apparent, **high)


def test_comfort_index_is_unknown_without_apparent_temperature():
    assert _comfort(None) is None


def test_heat_index_valid_conditions():
    entry = _make_entry({}, {"temperature_2m": 32.0, "relative_humidity_2m": 70.0})
    sensor = HeatIndexSensor(entry)
    val = sensor.native_value
    assert val is not None
    assert val > 32.0


def test_heat_index_cold_returns_none():
    entry = _make_entry({}, {"temperature_2m": 15.0, "relative_humidity_2m": 60.0})
    sensor = HeatIndexSensor(entry)
    assert sensor.native_value is None


def test_wind_chill_valid_conditions():
    entry = _make_entry({}, {"temperature_2m": -5.0, "wind_speed_10m": 25.0})
    sensor = WindChillSensor(entry)
    val = sensor.native_value
    assert val is not None
    assert val < -5.0


def test_wind_chill_warm_returns_none():
    entry = _make_entry({}, {"temperature_2m": 15.0, "wind_speed_10m": 15.0})
    sensor = WindChillSensor(entry)
    assert sensor.native_value is None


def test_ventilation_score_good():
    entry = _make_entry(
        {"european_aqi": 15.0},
        {"wind_speed_10m": 18.0, "precipitation": 0.0},
    )
    sensor = VentilationScoreSensor(entry)
    val = sensor.native_value
    assert val is not None
    assert val >= 60
    attrs = sensor.extra_state_attributes
    assert attrs["recommendation"] == "ventilate"


def test_ventilation_score_poor_aqi():
    entry = _make_entry(
        {"european_aqi": 95.0},
        {"wind_speed_10m": 3.0, "precipitation": 2.0},
    )
    sensor = VentilationScoreSensor(entry)
    attrs = sensor.extra_state_attributes
    assert attrs["recommendation"] == "keep_closed"


def test_solar_production_full_cloud():
    entry = _make_entry({}, {"cloud_cover": 100.0, "shortwave_radiation": 0.0})
    sensor = SolarProductionFactorSensor(entry)
    assert sensor.native_value == 0.0


def test_solar_production_clear_sky():
    entry = _make_entry({}, {"cloud_cover": 0.0, "shortwave_radiation": 1000.0})
    sensor = SolarProductionFactorSensor(entry)
    assert sensor.native_value == 1.0


def test_derived_sensors_return_none_when_data_missing():
    entry = _make_entry({}, {})
    for SensorClass in [
        ComfortIndexSensor,
        HeatIndexSensor,
        WindChillSensor,
        VentilationScoreSensor,
        SolarProductionFactorSensor,
    ]:
        sensor = SensorClass(entry)
        assert sensor.native_value is None


def test_derived_sensors_partial_data_aq_only():
    entry = _make_entry({"european_aqi": 30.0}, {})
    heat = HeatIndexSensor(entry)
    assert heat.native_value is None  # depends on weather data


@pytest.mark.parametrize(
    ("aq_data", "expected"),
    [
        ({"grass_pollen": 0.0, "birch_pollen": 0.0}, 0),
        ({"grass_pollen": 0.0, "birch_pollen": None}, 0),
        ({"grass_pollen": None, "birch_pollen": None}, None),
        ({}, None),
    ],
)
def test_pollen_total_risk_zero_and_missing_values(aq_data, expected):
    entry = _make_entry(aq_data, {})
    sensor = PollenTotalRiskSensor(entry)
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("sensor_cls", "expected_aq", "expected_weather"),
    [
        (ComfortIndexSensor, 0, 1),
        (DominantPollutantSensor, 1, 0),
        (VentilationScoreSensor, 1, 1),
    ],
)
@pytest.mark.asyncio
async def test_derived_sensors_only_subscribe_to_used_coordinators(
    sensor_cls,
    expected_aq,
    expected_weather,
):
    from custom_components.outdoor_environment import OutdoorEnvironmentData

    aq = MagicMock()
    weather = MagicMock()
    aq.async_add_listener = MagicMock(return_value=lambda: None)
    weather.async_add_listener = MagicMock(return_value=lambda: None)

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.title = "Outdoor Environment"
    entry.runtime_data = OutdoorEnvironmentData(
        coordinator_aq=aq,
        coordinator_weather=weather,
    )
    entry.data = {}
    entry.options = {}

    sensor = sensor_cls(entry)
    sensor.async_on_remove = MagicMock()
    await sensor.async_added_to_hass()

    assert aq.async_add_listener.call_count == expected_aq
    assert weather.async_add_listener.call_count == expected_weather


def test_lightning_risk_high():
    entry = _make_entry({}, {"cape": 2500.0, "cloud_cover": 80.0})
    sensor = LightningRiskSensor(entry)
    assert sensor.native_value == "high"


def test_lightning_risk_none():
    entry = _make_entry({}, {"cape": 50.0, "cloud_cover": 20.0})
    sensor = LightningRiskSensor(entry)
    assert sensor.native_value == "none"
