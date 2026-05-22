"""Tests for derived sensor calculations (pure functions and sensor values)."""
from __future__ import annotations

import pytest

from custom_components.outdoor_environment.const import (
    calc_ventilation_score,
    heat_index,
    solar_production_factor,
    wind_chill,
)
from custom_components.outdoor_environment.sensor_derived import (
    ComfortIndexSensor,
    FrostRiskSensor,
    HeatIndexSensor,
    IrrigationNeededSensor,
    LightningRiskSensor,
    SolarProductionFactorSensor,
    VentilationScoreSensor,
    WindChillSensor,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

def test_heat_index_formula():
    result = heat_index(32.0, 70.0)
    assert 35.0 < result < 45.0


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


def test_comfort_index_high_temp_uses_heat_index():
    entry = _make_entry(
        {},
        {"temperature_2m": 35.0, "relative_humidity_2m": 75.0, "wind_speed_10m": 5.0},
    )
    sensor = ComfortIndexSensor(entry)
    val = sensor.native_value
    assert val is not None
    assert 0 <= val <= 100


def test_comfort_index_low_temp_wind_uses_wind_chill():
    entry = _make_entry(
        {},
        {"temperature_2m": -2.0, "relative_humidity_2m": 60.0, "wind_speed_10m": 20.0},
    )
    sensor = ComfortIndexSensor(entry)
    val = sensor.native_value
    assert val is not None
    assert 0 <= val <= 100


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


def test_irrigation_needed_true():
    entry = _make_entry(
        {},
        {"et0_fao_evapotranspiration": 5.0, "precipitation": 1.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    sensor = IrrigationNeededSensor(entry)
    assert sensor.native_value is True
    attrs = sensor.extra_state_attributes
    assert attrs["deficit_mm"] == pytest.approx(4.0)


def test_irrigation_needed_false():
    entry = _make_entry(
        {},
        {"et0_fao_evapotranspiration": 1.0, "precipitation": 3.0},
        options={"irrigation_threshold_mm": 2.0},
    )
    sensor = IrrigationNeededSensor(entry)
    assert sensor.native_value is False


def test_frost_risk_true():
    entry = _make_entry({}, {"apparent_temperature": 1.0, "relative_humidity_2m": 90.0})
    sensor = FrostRiskSensor(entry)
    assert sensor.native_value is True


def test_frost_risk_false_warm():
    entry = _make_entry({}, {"apparent_temperature": 10.0, "relative_humidity_2m": 85.0})
    sensor = FrostRiskSensor(entry)
    assert sensor.native_value is False


def test_lightning_risk_high():
    entry = _make_entry({}, {"cape": 2500.0, "cloud_cover": 80.0})
    sensor = LightningRiskSensor(entry)
    assert sensor.native_value == "high"


def test_lightning_risk_none():
    entry = _make_entry({}, {"cape": 50.0, "cloud_cover": 20.0})
    sensor = LightningRiskSensor(entry)
    assert sensor.native_value == "none"
