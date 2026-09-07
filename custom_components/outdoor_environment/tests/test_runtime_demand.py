from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.outdoor_environment import async_setup_entry
from custom_components.outdoor_environment.const import (
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_GROUP_A_EXTRA,
    CONF_ENABLE_GROUP_A_SUB,
    CONF_ENABLE_GROUP_A_SUB_US,
    CONF_ENABLE_GROUP_D_AGRO,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_SOLAR,
    CONF_ENABLE_UV,
    CONF_ENABLE_WEATHER,
    DOMAIN,
)
from custom_components.outdoor_environment.coordinator_aq import AirQualityCoordinator
from custom_components.outdoor_environment.coordinator_weather import WeatherCoordinator
from custom_components.outdoor_environment.sensor_derived import (
    ComfortIndexSensor,
    DominantPollutantSensor,
    FrostRiskSensor,
    HeatIndexSensor,
    IrrigationNeededSensor,
    LightningRiskSensor,
    PollenTotalRiskSensor,
    SolarProductionFactorSensor,
    VentilationScoreSensor,
    WindChillSensor,
    create_derived_sensors,
)

_ALL_GROUPS_DISABLED = {
    CONF_ENABLE_AIR_QUALITY: False,
    CONF_ENABLE_GROUP_A_SUB: False,
    CONF_ENABLE_GROUP_A_SUB_US: False,
    CONF_ENABLE_GROUP_A_EXTRA: False,
    CONF_ENABLE_POLLEN: False,
    CONF_ENABLE_UV: False,
    CONF_ENABLE_WEATHER: False,
    CONF_ENABLE_SOLAR: False,
    CONF_ENABLE_GROUP_D_AGRO: False,
}


def _entry(data: dict | None = None, options: dict | None = None) -> MockConfigEntry:
    config = {
        "latitude": 45.46,
        "longitude": 9.19,
        "enable_air_quality": True,
        "enable_pollen": True,
        "enable_uv": True,
        "enable_weather": True,
        "enable_solar": True,
        "enable_group_a_sub": False,
        "enable_group_a_sub_us": False,
        "enable_group_a_extra": False,
        "enable_group_d_agro": False,
    }
    config.update(data or {})
    return MockConfigEntry(
        domain=DOMAIN,
        title="Outdoor Environment",
        data=config,
        options=options or {},
    )


@pytest.mark.asyncio
async def test_coordinators_accept_none_and_expose_none_interval(hass):
    assert WeatherCoordinator(hass, 45.46, 9.19, update_interval_minutes=None).update_interval is None
    assert AirQualityCoordinator(hass, 45.46, 9.19, update_interval_minutes=None).update_interval is None


@pytest.mark.asyncio
async def test_numeric_intervals_preserve_timedelta(hass):
    assert WeatherCoordinator(hass, 45.46, 9.19, update_interval_minutes=10).update_interval == timedelta(minutes=10)
    assert AirQualityCoordinator(hass, 45.46, 9.19, update_interval_minutes=30).update_interval == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_forecast_startup_fetch_skipped_when_weather_related_groups_are_disabled(hass):
    entry = _entry({
        CONF_ENABLE_WEATHER: False,
        CONF_ENABLE_SOLAR: False,
        CONF_ENABLE_GROUP_D_AGRO: False,
        CONF_ENABLE_AIR_QUALITY: True,
    })
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        side_effect=AssertionError("weather refresh should be skipped"),
    ) as weather_refresh, patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as aq_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    weather_refresh.assert_not_awaited()
    aq_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_aq_startup_fetch_skipped_when_all_aq_backed_groups_are_disabled(hass):
    entry = _entry({**_ALL_GROUPS_DISABLED, CONF_ENABLE_WEATHER: True})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        side_effect=AssertionError("aq refresh should be skipped"),
    ) as aq_refresh, patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as weather_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    aq_refresh.assert_not_awaited()
    weather_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    "enabled_group",
    [
        CONF_ENABLE_AIR_QUALITY,
        CONF_ENABLE_GROUP_A_SUB,
        CONF_ENABLE_GROUP_A_SUB_US,
        CONF_ENABLE_GROUP_A_EXTRA,
        CONF_ENABLE_POLLEN,
        CONF_ENABLE_UV,
    ],
)
@pytest.mark.asyncio
async def test_each_aq_group_independently_demands_aq_refresh(hass, enabled_group):
    entry = _entry({**_ALL_GROUPS_DISABLED, enabled_group: True})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as aq_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    aq_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    "enabled_group",
    [
        CONF_ENABLE_SOLAR,
        CONF_ENABLE_GROUP_D_AGRO,
    ],
)
@pytest.mark.asyncio
async def test_each_weather_group_independently_demands_weather_refresh(hass, enabled_group):
    entry = _entry({**_ALL_GROUPS_DISABLED, enabled_group: True})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as weather_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    weather_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_pollen_flag_defaults_true_and_demands_aq(hass):
    data = {
        "latitude": 45.46,
        "longitude": 9.19,
        **{
            key: value
            for key, value in _ALL_GROUPS_DISABLED.items()
            if key != CONF_ENABLE_POLLEN
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Outdoor Environment",
        data=data,
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as aq_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    aq_refresh.assert_awaited_once()
    assert {type(sensor) for sensor in create_derived_sensors(entry, {**entry.data, **entry.options})} == {
        PollenTotalRiskSensor,
        DominantPollutantSensor,
    }


@pytest.mark.asyncio
async def test_demand_is_independent_across_apis(hass):
    entry = _entry({
        CONF_ENABLE_AIR_QUALITY: True,
        CONF_ENABLE_WEATHER: False,
        CONF_ENABLE_SOLAR: False,
        CONF_ENABLE_GROUP_D_AGRO: False,
    })
    entry.add_to_hass(hass)

    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ) as aq_refresh, patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        side_effect=AssertionError("weather refresh should be skipped"),
    ) as weather_refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)

    aq_refresh.assert_awaited_once()
    weather_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_demanded_api_failure_blocks_setup_but_undemanded_failure_does_not(hass):
    requested_entry = _entry({CONF_ENABLE_AIR_QUALITY: True, CONF_ENABLE_WEATHER: False, CONF_ENABLE_SOLAR: False, CONF_ENABLE_GROUP_D_AGRO: False})
    requested_entry.add_to_hass(hass)
    with patch(
        "custom_components.outdoor_environment.coordinator_aq.AirQualityCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        side_effect=RuntimeError("aq boom"),
    ):
        assert not await hass.config_entries.async_setup(requested_entry.entry_id)

    undemanded_entry = _entry({CONF_ENABLE_AIR_QUALITY: False, CONF_ENABLE_GROUP_A_SUB: False, CONF_ENABLE_GROUP_A_SUB_US: False, CONF_ENABLE_GROUP_A_EXTRA: False, CONF_ENABLE_POLLEN: False, CONF_ENABLE_UV: False, CONF_ENABLE_WEATHER: False, CONF_ENABLE_SOLAR: False, CONF_ENABLE_GROUP_D_AGRO: False})
    undemanded_entry.add_to_hass(hass)
    with patch(
        "custom_components.outdoor_environment.coordinator_weather.WeatherCoordinator.async_config_entry_first_refresh",
        new_callable=AsyncMock,
        side_effect=RuntimeError("weather boom"),
    ):
        assert await hass.config_entries.async_setup(undemanded_entry.entry_id)


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        (
            {CONF_ENABLE_WEATHER: True},
            {
                ComfortIndexSensor,
                HeatIndexSensor,
                WindChillSensor,
                FrostRiskSensor,
                LightningRiskSensor,
                IrrigationNeededSensor,
                SolarProductionFactorSensor,
            },
        ),
        (
            {CONF_ENABLE_AIR_QUALITY: True, CONF_ENABLE_POLLEN: False},
            {DominantPollutantSensor},
        ),
        (
            {CONF_ENABLE_POLLEN: True},
            {DominantPollutantSensor, PollenTotalRiskSensor},
        ),
        (
            {CONF_ENABLE_WEATHER: True, CONF_ENABLE_POLLEN: True},
            {
                ComfortIndexSensor,
                HeatIndexSensor,
                WindChillSensor,
                FrostRiskSensor,
                LightningRiskSensor,
                IrrigationNeededSensor,
                SolarProductionFactorSensor,
                DominantPollutantSensor,
                PollenTotalRiskSensor,
                VentilationScoreSensor,
            },
        ),
        ({**_ALL_GROUPS_DISABLED}, set()),
    ],
)
def test_derived_sensor_creation_respects_group_dependencies(cfg, expected):
    entry = _entry({**_ALL_GROUPS_DISABLED, **cfg})
    sensors = create_derived_sensors(entry, {**entry.data, **entry.options})
    sensor_types = {type(sensor) for sensor in sensors}
    assert sensor_types == expected
