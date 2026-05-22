from __future__ import annotations

DOMAIN = "outdoor_environment"

# API endpoints
AQ_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"

# HTTP timeout seconds
HTTP_TIMEOUT = 10

# Default update intervals (minutes)
DEFAULT_AQ_UPDATE_MINUTES = 60
DEFAULT_WEATHER_UPDATE_MINUTES = 15
DEFAULT_IRRIGATION_THRESHOLD_MM = 2.0

# Config / options entry keys
CONF_USE_HOME_LOCATION = "use_home_location"
CONF_ENABLE_AIR_QUALITY = "enable_air_quality"
CONF_ENABLE_POLLEN = "enable_pollen"
CONF_ENABLE_UV = "enable_uv"
CONF_ENABLE_WEATHER = "enable_weather"
CONF_ENABLE_SOLAR = "enable_solar"
CONF_PANEL_TILT = "panel_tilt"
CONF_PANEL_AZIMUTH = "panel_azimuth"
CONF_AQ_UPDATE_INTERVAL = "aq_update_interval_minutes"
CONF_WEATHER_UPDATE_INTERVAL = "weather_update_interval_minutes"
CONF_IRRIGATION_THRESHOLD = "irrigation_threshold_mm"
CONF_ENABLE_GROUP_A_SUB = "enable_group_a_sub"
CONF_ENABLE_GROUP_A_SUB_US = "enable_group_a_sub_us"
CONF_ENABLE_GROUP_A_EXTRA = "enable_group_a_extra"
CONF_ENABLE_GROUP_D_AGRO = "enable_group_d_agro"

# Attribution
ATTRIBUTION = "Data provided by Open-Meteo (CC BY 4.0)"

# Europa bounding box
EUROPE_LAT_MIN = 34.0
EUROPE_LAT_MAX = 72.0
EUROPE_LON_MIN = -25.0
EUROPE_LON_MAX = 45.0

# AQI EU categories (EEA)
AQI_EU_CATEGORIES: list[tuple[float, str]] = [
    (20, "good"),
    (40, "fair"),
    (60, "moderate"),
    (80, "poor"),
    (100, "very_poor"),
    (float("inf"), "extremely_poor"),
]

# AQI US categories (EPA)
AQI_US_CATEGORIES: list[tuple[float, str]] = [
    (50, "good"),
    (100, "moderate"),
    (150, "unhealthy_sensitive"),
    (200, "unhealthy"),
    (300, "very_unhealthy"),
    (float("inf"), "hazardous"),
]

# UV categories (WHO)
UV_CATEGORIES: list[tuple[float, str]] = [
    (3, "low"),
    (6, "moderate"),
    (8, "high"),
    (11, "very_high"),
    (float("inf"), "extreme"),
]

# Pollen thresholds EAN (grains/m³)
POLLEN_THRESHOLDS: dict[str, list[tuple[float, str]]] = {
    "grass": [(10, "low"), (30, "medium"), (80, "high"), (float("inf"), "very_high")],
    "birch": [(10, "low"), (50, "medium"), (200, "high"), (float("inf"), "very_high")],
    "alder": [(10, "low"), (50, "medium"), (200, "high"), (float("inf"), "very_high")],
    "olive": [(10, "low"), (50, "medium"), (200, "high"), (float("inf"), "very_high")],
    "ragweed": [(10, "low"), (30, "medium"), (100, "high"), (float("inf"), "very_high")],
    "mugwort": [(10, "low"), (30, "medium"), (100, "high"), (float("inf"), "very_high")],
}

# WMO weather code descriptions
WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers",
    81: "Moderate showers",
    82: "Violent showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Sub-AQI EU keys → human label (used by dominant pollutant derived sensor)
EU_SUB_AQI_KEYS: dict[str, str] = {
    "european_aqi_pm2_5": "pm2_5",
    "european_aqi_pm10": "pm10",
    "european_aqi_no2": "no2",
    "european_aqi_o3": "o3",
    "european_aqi_so2": "so2",
}


def _classify(value: float, thresholds: list[tuple[float, str]]) -> str:
    for limit, label in thresholds:
        if value <= limit:
            return label
    return thresholds[-1][1]


def get_aqi_eu_category(value: float) -> str:
    return _classify(value, AQI_EU_CATEGORIES)


def get_aqi_us_category(value: float) -> str:
    return _classify(value, AQI_US_CATEGORIES)


def get_uv_category(value: float) -> str:
    return _classify(value, UV_CATEGORIES)


def get_pollen_risk(species: str, value: float) -> str:
    thresholds = POLLEN_THRESHOLDS.get(species)
    if not thresholds:
        return "unknown"
    return _classify(value, thresholds)


def is_europe(lat: float, lon: float) -> bool:
    return (
        EUROPE_LAT_MIN <= lat <= EUROPE_LAT_MAX
        and EUROPE_LON_MIN <= lon <= EUROPE_LON_MAX
    )


def get_dominant_eu_pollutant(
    data: dict[str, float | None],
) -> tuple[str | None, float | None]:
    """Return (pollutant_slug, sub_aqi_value) for the highest EU sub-AQI."""
    candidates = {
        label: data.get(key)
        for key, label in EU_SUB_AQI_KEYS.items()
        if data.get(key) is not None
    }
    if not candidates:
        return None, None
    dominant = max(candidates, key=lambda k: candidates[k])  # type: ignore[arg-type]
    return dominant, candidates[dominant]


def heat_index(temp: float, humidity: float) -> float:
    """NOAA Rothfusz regression (valid for T > 27°C and humidity > 40%).

    Computed in Fahrenheit then converted to Celsius so the standard
    NOAA coefficients are used exactly. The Celsius-direct coefficients
    in SPEC_v2.md produce inflated values due to incomplete conversion.
    """
    T = temp * 9 / 5 + 32  # °C → °F
    H = humidity
    hi_f = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * H
        - 0.22475541 * T * H
        - 0.00683783 * T**2
        - 0.05481717 * H**2
        + 0.00122874 * T**2 * H
        + 0.00085282 * T * H**2
        - 0.00000199 * T**2 * H**2
    )
    return (hi_f - 32) * 5 / 9  # °F → °C


def wind_chill(temp: float, wind_speed_kmh: float) -> float:
    """NWS formula — valid for T < 10°C and wind > 4.8 km/h."""
    V = wind_speed_kmh
    return 13.12 + 0.6215 * temp - 11.37 * (V**0.16) + 0.3965 * temp * (V**0.16)


def solar_production_factor(cloud_cover: float, shortwave_radiation: float) -> float:
    return (1.0 - cloud_cover / 100.0) * min(shortwave_radiation / 1000.0, 1.0)


def calc_ventilation_score(
    european_aqi: float,
    wind_speed: float,
    precipitation: float,
) -> tuple[float, str, str]:
    """Return (score 0-100, recommendation, reason)."""
    aqi_norm = max(0.0, 1.0 - european_aqi / 100.0)
    wind_norm = min(wind_speed / 20.0, 1.0)
    no_rain = 0.0 if precipitation > 0.1 else 1.0
    score = round(aqi_norm * 50 + wind_norm * 30 + no_rain * 20, 1)

    if score >= 60:
        recommendation = "ventilate"
        reason = "aqi_good" if aqi_norm > 0.6 else "wind_adequate"
    elif score >= 40:
        recommendation = "neutral"
        reason = "conditions_mixed"
    else:
        recommendation = "keep_closed"
        reason = "aqi_poor" if aqi_norm < 0.4 else "rain"

    return score, recommendation, reason
