from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OutdoorEnvironmentData
from .const import (
    ATTRIBUTION,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_GROUP_A_EXTRA,
    CONF_ENABLE_GROUP_A_SUB,
    CONF_ENABLE_GROUP_A_SUB_US,
    CONF_ENABLE_GROUP_D_AGRO,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_SOLAR,
    CONF_ENABLE_UV,
    CONF_ENABLE_WEATHER,
    CONF_PANEL_AZIMUTH,
    CONF_PANEL_TILT,
    DOMAIN,
    WMO_DESCRIPTIONS,
    get_aqi_eu_category,
    get_aqi_us_category,
    get_dominant_eu_pollutant,
    get_pollen_risk,
    get_uv_category,
    is_europe,
)
from .coordinator_aq import AirQualityCoordinator
from .coordinator_weather import WeatherCoordinator
from .sensor_derived import create_derived_sensors

_COORDINATOR_AQ = "aq"
_COORDINATOR_WEATHER = "weather"


@dataclass(frozen=True)
class OutdoorSensorDescription(SensorEntityDescription):
    """Extended sensor description with coordinator type and enable flag."""

    coordinator_type: str = _COORDINATOR_AQ
    enabled_default: bool = True


# ---------------------------------------------------------------------------
# Group A — AQ core (enabled_default=True)
# ---------------------------------------------------------------------------
AQ_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(
        key="european_aqi",
        name="AQI European",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="us_aqi",
        name="AQI US",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="pm2_5",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="pm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="nitrogen_dioxide",
        name="NO₂",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="ozone",
        name="O₃",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="sulphur_dioxide",
        name="SO₂",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="carbon_monoxide",
        name="CO",
        device_class=SensorDeviceClass.CARBON_MONOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="carbon_dioxide",
        name="CO₂",
        device_class=SensorDeviceClass.CARBON_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="dust",
        name="Dust",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="aerosol_optical_depth",
        name="Aerosol Optical Depth",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="ammonia",
        name="NH₃",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="methane",
        name="CH₄",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
)

# ---------------------------------------------------------------------------
# Group A-sub — EU sub-AQI per pollutant (enabled_default=False)
# ---------------------------------------------------------------------------
AQ_SUB_EU_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="european_aqi_pm2_5", name="AQI EU PM2.5", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="european_aqi_pm10", name="AQI EU PM10", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="european_aqi_no2", name="AQI EU NO₂", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="european_aqi_o3", name="AQI EU O₃", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="european_aqi_so2", name="AQI EU SO₂", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
)

# ---------------------------------------------------------------------------
# Group A-sub-us — US sub-AQI per pollutant (enabled_default=False)
# ---------------------------------------------------------------------------
AQ_SUB_US_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="us_aqi_pm2_5", name="AQI US PM2.5", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="us_aqi_pm10", name="AQI US PM10", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="us_aqi_no2", name="AQI US NO₂", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="us_aqi_co", name="AQI US CO", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="us_aqi_o3", name="AQI US O₃", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="us_aqi_so2", name="AQI US SO₂", device_class=SensorDeviceClass.AQI, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
)

# ---------------------------------------------------------------------------
# Group A-extra — advanced pollutants (enabled_default=False)
# ---------------------------------------------------------------------------
AQ_EXTRA_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="formaldehyde", name="Formaldehyde", native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="glyoxal", name="Glyoxal", native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="nitrogen_monoxide", name="NO", native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="peroxyacyl_nitrates", name="PAN", native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
    OutdoorSensorDescription(key="sea_salt_aerosol", name="Sea Salt Aerosol", native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_AQ, enabled_default=False),
)

# ---------------------------------------------------------------------------
# Group B — pollen species (enabled_default=False, created only if enable_pollen)
# (api_key, species_slug, display_name)
# ---------------------------------------------------------------------------
POLLEN_SPECIES: tuple[tuple[str, str, str], ...] = (
    ("grass_pollen", "grass", "Grass Pollen"),
    ("birch_pollen", "birch", "Birch Pollen"),
    ("alder_pollen", "alder", "Alder Pollen"),
    ("olive_pollen", "olive", "Olive Pollen"),
    ("ragweed_pollen", "ragweed", "Ragweed Pollen"),
    ("mugwort_pollen", "mugwort", "Mugwort Pollen"),
)

# ---------------------------------------------------------------------------
# Group C — UV (enabled_default=True)
# ---------------------------------------------------------------------------
UV_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(
        key="uv_index",
        name="UV Index",
        native_unit_of_measurement="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
    OutdoorSensorDescription(
        key="uv_index_clear_sky",
        name="UV Index Clear Sky",
        native_unit_of_measurement="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator_type=_COORDINATOR_AQ,
        enabled_default=True,
    ),
)

# ---------------------------------------------------------------------------
# Group D — weather (enabled_default=True)
# ---------------------------------------------------------------------------
WEATHER_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="temperature_2m", name="Temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="relative_humidity_2m", name="Humidity", device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="apparent_temperature", name="Apparent Temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="dew_point_2m", name="Dew Point", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="precipitation", name="Precipitation", native_unit_of_measurement="mm", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="rain", name="Rain", native_unit_of_measurement="mm", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="snowfall", name="Snowfall", native_unit_of_measurement="cm", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="wind_speed_10m", name="Wind Speed", device_class=SensorDeviceClass.WIND_SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="wind_direction_10m", name="Wind Direction", native_unit_of_measurement="°", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="wind_gusts_10m", name="Wind Gusts", device_class=SensorDeviceClass.WIND_SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="cloud_cover", name="Cloud Cover", device_class=SensorDeviceClass.CLOUD_COVERAGE, native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="visibility", name="Visibility", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=UnitOfLength.METERS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="surface_pressure", name="Pressure", device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE, native_unit_of_measurement=UnitOfPressure.HPA, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="weather_code", name="Weather Code", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="is_day", name="Is Day", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="sunshine_duration", name="Sunshine Duration", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.SECONDS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
)

# ---------------------------------------------------------------------------
# Group D-agro — agrometeorological (enabled_default=False)
# ---------------------------------------------------------------------------
AGRO_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="et0_fao_evapotranspiration", name="Evapotranspiration", native_unit_of_measurement="mm", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=False),
    OutdoorSensorDescription(key="vapour_pressure_deficit", name="Vapour Pressure Deficit", native_unit_of_measurement=UnitOfPressure.KILOPASCAL, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=False),
    OutdoorSensorDescription(key="cape", name="CAPE", native_unit_of_measurement="J/kg", state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=False),
    OutdoorSensorDescription(key="wet_bulb_temperature_2m", name="Wet Bulb Temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=False),
)

# ---------------------------------------------------------------------------
# Group E — solar radiation (enabled_default=True)
# ---------------------------------------------------------------------------
SOLAR_SENSORS: tuple[OutdoorSensorDescription, ...] = (
    OutdoorSensorDescription(key="shortwave_radiation", name="Solar GHI", device_class=SensorDeviceClass.IRRADIANCE, native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="direct_radiation", name="Solar Direct", device_class=SensorDeviceClass.IRRADIANCE, native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="diffuse_radiation", name="Solar Diffuse", device_class=SensorDeviceClass.IRRADIANCE, native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="direct_normal_irradiance", name="Solar DNI", device_class=SensorDeviceClass.IRRADIANCE, native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
    OutdoorSensorDescription(key="terrestrial_radiation", name="Solar Terrestrial", device_class=SensorDeviceClass.IRRADIANCE, native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER, state_class=SensorStateClass.MEASUREMENT, coordinator_type=_COORDINATOR_WEATHER, enabled_default=True),
)


# ---------------------------------------------------------------------------
# Entity classes
# ---------------------------------------------------------------------------

def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Open-Meteo",
        model="Outdoor Environment",
        configuration_url="https://open-meteo.com",
    )


class OutdoorEnvironmentSensor(
    CoordinatorEntity[AirQualityCoordinator | WeatherCoordinator],
    SensorEntity,
):
    """Generic raw sensor reading from one coordinator."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AirQualityCoordinator | WeatherCoordinator,
        entry: ConfigEntry,
        description: OutdoorSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_entity_registry_enabled_default = description.enabled_default
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class AqiSensor(OutdoorEnvironmentSensor):
    """AQI sensor with category + dominant pollutant extra attributes."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        if val is None:
            return {}
        attrs: dict[str, Any] = {}
        if self.entity_description.key == "european_aqi":
            attrs["aqi_category"] = get_aqi_eu_category(val)
            dominant, dominant_val = get_dominant_eu_pollutant(
                self.coordinator.data or {}
            )
            attrs["dominant_pollutant"] = dominant
            attrs["dominant_pollutant_value"] = dominant_val
        elif self.entity_description.key == "us_aqi":
            attrs["aqi_category"] = get_aqi_us_category(val)
        return attrs


class UvSensor(OutdoorEnvironmentSensor):
    """UV index sensor with category and protection_required attributes."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        if val is None or self.entity_description.key != "uv_index":
            return {}
        return {
            "uv_category": get_uv_category(val),
            "protection_required": val >= 3,
        }


class PollenSensor(
    CoordinatorEntity[AirQualityCoordinator],
    SensorEntity,
):
    """Pollen sensor with risk level, in_season and is_europe attributes."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "grains/m³"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: AirQualityCoordinator,
        entry: ConfigEntry,
        api_key: str,
        species: str,
        display_name: str,
        in_europe: bool,
    ) -> None:
        super().__init__(coordinator)
        self._api_key = api_key
        self._species = species
        self._in_europe = in_europe
        self._attr_name = display_name
        self._attr_unique_id = f"{entry.entry_id}_{api_key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._api_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        return {
            "pollen_risk_level": get_pollen_risk(self._species, val) if val is not None else "none",
            "is_in_season": val is not None,
            "is_europe": self._in_europe,
        }


class WeatherCodeSensor(OutdoorEnvironmentSensor):
    """Weather code sensor with WMO description attribute."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        if val is None:
            return {}
        return {"weather_description": WMO_DESCRIPTIONS.get(int(val), "Unknown")}


class GtiSensor(
    CoordinatorEntity[WeatherCoordinator],
    SensorEntity,
):
    """Global Tilted Irradiance sensor — only created when panel_tilt is configured."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.IRRADIANCE
    _attr_native_unit_of_measurement = UnitOfIrradiance.WATTS_PER_SQUARE_METER
    _attr_name = "Solar GTI"

    def __init__(
        self,
        coordinator: WeatherCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._panel_tilt: float = entry.data[CONF_PANEL_TILT]
        self._panel_azimuth: float = entry.data.get(CONF_PANEL_AZIMUTH, 0.0)
        self._attr_unique_id = f"{entry.entry_id}_global_tilted_irradiance"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("global_tilted_irradiance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "panel_tilt": self._panel_tilt,
            "panel_azimuth": self._panel_azimuth,
        }


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all sensor entities for this config entry."""
    runtime: OutdoorEnvironmentData = entry.runtime_data
    aq = runtime.coordinator_aq
    weather = runtime.coordinator_weather

    cfg = {**entry.data, **entry.options}
    lat: float = entry.data.get("latitude", 0.0)
    lon: float = entry.data.get("longitude", 0.0)
    in_europe = is_europe(lat, lon)

    entities: list[SensorEntity] = []

    # Group A — AQ core
    if cfg.get(CONF_ENABLE_AIR_QUALITY, True):
        for desc in AQ_SENSORS:
            if desc.key in ("european_aqi", "us_aqi"):
                entities.append(AqiSensor(aq, entry, desc))
            else:
                entities.append(OutdoorEnvironmentSensor(aq, entry, desc))

    # Group A-sub — EU sub-AQI
    if cfg.get(CONF_ENABLE_GROUP_A_SUB, False):
        entities += [OutdoorEnvironmentSensor(aq, entry, d) for d in AQ_SUB_EU_SENSORS]

    # Group A-sub-us — US sub-AQI
    if cfg.get(CONF_ENABLE_GROUP_A_SUB_US, False):
        entities += [OutdoorEnvironmentSensor(aq, entry, d) for d in AQ_SUB_US_SENSORS]

    # Group A-extra — advanced pollutants
    if cfg.get(CONF_ENABLE_GROUP_A_EXTRA, False):
        entities += [OutdoorEnvironmentSensor(aq, entry, d) for d in AQ_EXTRA_SENSORS]

    # Group B — pollen
    if cfg.get(CONF_ENABLE_POLLEN, True):
        for api_key, species, display_name in POLLEN_SPECIES:
            entities.append(PollenSensor(aq, entry, api_key, species, display_name, in_europe))

    # Group C — UV
    if cfg.get(CONF_ENABLE_UV, True):
        for desc in UV_SENSORS:
            entities.append(
                UvSensor(aq, entry, desc) if desc.key == "uv_index"
                else OutdoorEnvironmentSensor(aq, entry, desc)
            )

    # Group D — weather
    if cfg.get(CONF_ENABLE_WEATHER, True):
        for desc in WEATHER_SENSORS:
            entities.append(
                WeatherCodeSensor(weather, entry, desc) if desc.key == "weather_code"
                else OutdoorEnvironmentSensor(weather, entry, desc)
            )

    # Group D-agro
    if cfg.get(CONF_ENABLE_GROUP_D_AGRO, False):
        entities += [OutdoorEnvironmentSensor(weather, entry, d) for d in AGRO_SENSORS]

    # Group E — solar
    if cfg.get(CONF_ENABLE_SOLAR, True):
        entities += [OutdoorEnvironmentSensor(weather, entry, d) for d in SOLAR_SENSORS]
        if entry.data.get(CONF_PANEL_TILT) is not None:
            entities.append(GtiSensor(weather, entry))

    # Group F — derived sensors
    entities += create_derived_sensors(entry)

    async_add_entities(entities)
