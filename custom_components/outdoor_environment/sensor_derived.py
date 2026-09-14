from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENABLE_AQ_FORECAST,
    CONF_ENABLE_POLLEN,
    EU_SUB_AQI_KEYS,
    calc_ventilation_score,
    comfort_index,
    daily_max_from_hourly,
    get_api_demand,
    get_dominant_eu_pollutant,
    get_pollen_risk,
    heat_index,
    solar_production_factor,
    wind_chill,
)
from .entity import OutdoorComputedEntity

if TYPE_CHECKING:
    from . import OutdoorEnvironmentData


class OutdoorDerivedSensor(OutdoorComputedEntity, SensorEntity):
    """Base class for computed sensors — no direct coordinator ownership."""

    # NOTE: state_class is deliberately NOT set on the base class. Not every
    # derived sensor is numeric, and declaring MEASUREMENT here made HA expect
    # a number from every subclass — non-numeric ones raised ValueError when
    # their state was written. Numeric subclasses opt in individually.


# ---------------------------------------------------------------------------
# Derived sensor implementations
# ---------------------------------------------------------------------------

class ComfortIndexSensor(OutdoorDerivedSensor):
    _attr_name = "Comfort Index"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_comfort_index"

    @property
    def native_value(self) -> float | None:
        apparent = self._wx().get("apparent_temperature")
        if apparent is None:
            return None
        return round(comfort_index(apparent), 1)


class HeatIndexSensor(OutdoorDerivedSensor):
    _attr_name = "Heat Index"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_heat_index"

    @property
    def native_value(self) -> float | None:
        wx = self._wx()
        temp = wx.get("temperature_2m")
        humidity = wx.get("relative_humidity_2m")
        if temp is None or humidity is None:
            return None
        if temp < 27 or humidity < 40:
            return None
        return round(heat_index(temp, humidity), 1)


class WindChillSensor(OutdoorDerivedSensor):
    _attr_name = "Wind Chill"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_wind_chill"

    @property
    def native_value(self) -> float | None:
        wx = self._wx()
        temp = wx.get("temperature_2m")
        wind = wx.get("wind_speed_10m")
        if temp is None or wind is None:
            return None
        if temp >= 10 or wind < 4.8:
            return None
        return round(wind_chill(temp, wind), 1)


class DominantPollutantSensor(OutdoorDerivedSensor):
    _attr_name = "Dominant Pollutant"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(EU_SUB_AQI_KEYS.values())
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("aq",))
        self._attr_unique_id = f"{entry.entry_id}_dominant_pollutant"

    @property
    def native_value(self) -> str | None:
        dominant, _ = get_dominant_eu_pollutant(self._aq())
        return dominant


class PollenTotalRiskSensor(OutdoorDerivedSensor):
    _attr_name = "Pollen Total Risk"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = True

    _RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "very_high": 4}
    _SPECIES_KEYS = {
        "grass_pollen": "grass",
        "birch_pollen": "birch",
        "alder_pollen": "alder",
        "olive_pollen": "olive",
        "ragweed_pollen": "ragweed",
        "mugwort_pollen": "mugwort",
    }

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("aq",))
        self._attr_unique_id = f"{entry.entry_id}_pollen_total_risk"

    @property
    def native_value(self) -> int | None:
        aq = self._aq()
        max_level = 0
        saw_numeric_reading = False
        for key, species in self._SPECIES_KEYS.items():
            val = aq.get(key)
            if val is None:
                continue
            if not isinstance(val, (int, float)):
                continue
            saw_numeric_reading = True
            if val == 0:
                continue
            level = self._RISK_ORDER.get(get_pollen_risk(species, val), 0)
            max_level = max(max_level, level)
        if not saw_numeric_reading:
            return None
        return max_level


class VentilationScoreSensor(OutdoorDerivedSensor):
    _attr_name = "Ventilation Score"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("aq", "weather"))
        self._attr_unique_id = f"{entry.entry_id}_ventilation_score"

    @property
    def native_value(self) -> float | None:
        aq = self._aq()
        wx = self._wx()
        aqi = aq.get("european_aqi")
        wind = wx.get("wind_speed_10m")
        precip = wx.get("precipitation")
        if aqi is None or wind is None or precip is None:
            return None
        score, _, _ = calc_ventilation_score(aqi, wind, precip)
        return score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        aq = self._aq()
        wx = self._wx()
        aqi = aq.get("european_aqi")
        wind = wx.get("wind_speed_10m")
        precip = wx.get("precipitation")
        if aqi is None or wind is None or precip is None:
            return {}
        _, recommendation, reason = calc_ventilation_score(aqi, wind, precip)
        return {"recommendation": recommendation, "reason": reason}


class SolarProductionFactorSensor(OutdoorDerivedSensor):
    _attr_name = "Solar Production Factor"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_solar_production_factor"

    @property
    def native_value(self) -> float | None:
        wx = self._wx()
        cloud = wx.get("cloud_cover")
        ghi = wx.get("shortwave_radiation")
        if cloud is None or ghi is None:
            return None
        return round(solar_production_factor(cloud, ghi), 3)


class LightningRiskSensor(OutdoorDerivedSensor):
    _attr_name = "Lightning Risk"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["none", "low", "medium", "high"]
    _attr_native_unit_of_measurement = None
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, coordinator_types=("weather",))
        self._attr_unique_id = f"{entry.entry_id}_lightning_risk"

    @property
    def native_value(self) -> str | None:
        wx = self._wx()
        cape = wx.get("cape")
        cloud = wx.get("cloud_cover")
        if cape is None or cloud is None:
            return None
        if cape > 2000 and cloud > 70:
            return "high"
        if cape > 1000 and cloud > 70:
            return "medium"
        if cape > 500:
            return "low"
        return "none"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class AqiForecastMaxSensor(OutdoorDerivedSensor):
    """Highest forecast AQI for one calendar day.

    The air quality endpoint publishes no daily block, so the maximum is
    aggregated from the hourly series. It covers the whole calendar day,
    including hours already past: a daily maximum that only looked ahead would
    drift downwards through the day, and an automation keyed to it would fire at
    whatever hour the window happened to catch. "Keep the windows shut today"
    needs a number that holds still.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    # Enabled once the group is on. The config option is off by default and is
    # already the gate: leaving these disabled as well would mean a user turns
    # the forecast on in Configure and still sees nothing. The older optional
    # groups do carry both gates — changing those is a separate decision, and
    # inert for anyone who already has their rows in the registry.
    _attr_entity_registry_enabled_default = True
    # 24 floats rewritten on every coordinator update would be recorded in full
    # each time. The series exists for a card to draw, not for history.
    _unrecorded_attributes = frozenset({"forecast"})

    def __init__(
        self,
        entry: ConfigEntry,
        *,
        api_key: str,
        day_index: int,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(entry, coordinator_types=("aq",))
        self._api_key = api_key
        self._day_index = day_index
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"

    def _day(self) -> tuple[str, float] | None:
        days = daily_max_from_hourly(self._aq().get("hourly") or {}, self._api_key)
        if len(days) <= self._day_index:
            return None
        return days[self._day_index]

    @property
    def native_value(self) -> int | None:
        day = self._day()
        return None if day is None else round(day[1])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        day = self._day()
        if day is None:
            return {}
        date, _ = day
        hourly = self._aq().get("hourly") or {}
        return {
            # Which day this actually is, rather than trusting "today" to mean
            # what the reader assumes: the series is in the location's timezone,
            # which need not be Home Assistant's.
            "date": date,
            "forecast": [
                value
                for timestamp, value in zip(
                    hourly.get("time") or [], hourly.get(self._api_key) or []
                )
                if str(timestamp)[:10] == date
            ],
        }


# (api_key, day_index, name, unique_id suffix)
AQ_FORECAST_SENSORS: tuple[tuple[str, int, str, str], ...] = (
    ("european_aqi", 0, "European AQI Max Today", "european_aqi_max_today"),
    ("european_aqi", 1, "European AQI Max Tomorrow", "european_aqi_max_tomorrow"),
    ("us_aqi", 0, "US AQI Max Today", "us_aqi_max_today"),
    ("us_aqi", 1, "US AQI Max Tomorrow", "us_aqi_max_tomorrow"),
)


def create_derived_sensors(
    entry: ConfigEntry,
    cfg: dict[str, Any],
    demand_aq: bool | None = None,
    demand_weather: bool | None = None,
) -> list[SensorEntity]:
    """Return derived sensors whose required input APIs are active."""
    if demand_aq is None or demand_weather is None:
        demand_aq, demand_weather = get_api_demand(cfg)

    sensors: list[SensorEntity] = []

    if demand_weather:
        sensors.extend(
            [
                ComfortIndexSensor(entry),
                HeatIndexSensor(entry),
                WindChillSensor(entry),
                LightningRiskSensor(entry),
                SolarProductionFactorSensor(entry),
            ]
        )

    if demand_aq and demand_weather:
        sensors.append(VentilationScoreSensor(entry))

    if demand_aq:
        sensors.append(DominantPollutantSensor(entry))

    if demand_aq and cfg.get(CONF_ENABLE_POLLEN, True):
        sensors.append(PollenTotalRiskSensor(entry))

    if demand_aq and cfg.get(CONF_ENABLE_AQ_FORECAST, False):
        sensors.extend(
            AqiForecastMaxSensor(
                entry,
                api_key=api_key,
                day_index=day_index,
                name=name,
                unique_suffix=suffix,
            )
            for api_key, day_index, name, suffix in AQ_FORECAST_SENSORS
        )

    return sensors
