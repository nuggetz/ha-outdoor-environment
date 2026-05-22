# Outdoor Environment

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![HA version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration that exposes **80+ outdoor environment sensors** using two free, no-key [Open-Meteo](https://open-meteo.com) APIs.

> Zero API key · Zero registration · Zero cost · Global coverage

---

## Features

| Group | Sensors | Default |
|-------|---------|---------|
| **A — Air Quality** | AQI (EU + US), PM2.5, PM10, NO₂, O₃, SO₂, CO, CO₂, dust, AOD, NH₃, CH₄ | ✅ Enabled |
| **A-sub — EU sub-AQI** | EU sub-AQI per pollutant (PM2.5, PM10, NO₂, O₃, SO₂) | ⬜ Disabled |
| **A-sub-us — US sub-AQI** | US sub-AQI per pollutant (PM2.5, PM10, NO₂, CO, O₃, SO₂) | ⬜ Disabled |
| **A-extra — Advanced pollutants** | Formaldehyde, glyoxal, NO, PAN, sea salt aerosol | ⬜ Disabled |
| **B — Pollen** | Grass, birch, alder, olive, ragweed, mugwort | ⬜ Disabled |
| **C — UV** | UV Index, UV Index Clear Sky | ✅ Enabled |
| **D — Weather** | Temperature, humidity, apparent temp, dew point, precipitation, wind, cloud cover, visibility, pressure, weather code | ✅ Enabled |
| **D-agro — Agro** | ET0, VPD, CAPE, wet bulb temperature | ⬜ Disabled |
| **E — Solar** | GHI, direct, diffuse, DNI, terrestrial radiation, GTI (optional) | ✅ Enabled |
| **F — Derived** | Comfort index, heat index, wind chill, dominant pollutant, pollen risk, ventilation score, solar production factor, irrigation needed, frost risk, lightning risk | ✅/⬜ |

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/nuggetz/ha-outdoor-environment` as **Integration**
3. Install **Outdoor Environment**
4. Restart Home Assistant

### Manual

Copy `custom_components/outdoor_environment/` to your HA `custom_components/` directory and restart.

---

## Configuration

Go to **Settings → Devices & Services → Add Integration → Outdoor Environment**.

**Step 1 (required):** Choose location and enable/disable sensor groups.

**Step 2 (optional):** Configure solar panel tilt and azimuth to get the GTI sensor (ideal for PV owners).

All settings can be changed later via **Configure** (options flow).

---

## Automation Examples

### Close blinds when pollen is high

```yaml
automation:
  trigger:
    - platform: numeric_state
      entity_id: sensor.outdoor_pollen_grass
      above: 30
  action:
    - service: cover.close_cover
      target:
        entity_id: cover.living_room_blinds
```

### Ventilate when air quality is good and wind is adequate

```yaml
automation:
  trigger:
    - platform: numeric_state
      entity_id: sensor.outdoor_ventilation_score
      above: 60
  condition:
    - condition: state
      entity_id: sensor.outdoor_ventilation_score
      attribute: recommendation
      state: ventilate
  action:
    - service: fan.turn_on
      target:
        entity_id: fan.hrv_unit
```

### Irrigate when ET0 exceeds precipitation threshold

```yaml
automation:
  trigger:
    - platform: state
      entity_id: sensor.outdoor_irrigation_needed
      to: "True"
  action:
    - service: switch.turn_on
      target:
        entity_id: switch.garden_irrigation
```

### Alert for UV protection

```yaml
automation:
  trigger:
    - platform: template
      value_template: >
        {{ state_attr('sensor.outdoor_uv_index', 'protection_required') == true }}
  action:
    - service: notify.mobile_app
      data:
        message: "UV index {{ states('sensor.outdoor_uv_index') }} — apply sunscreen!"
```

---

## Data Sources

| API | Endpoint | Refresh |
|-----|----------|---------|
| Open-Meteo Air Quality | `air-quality-api.open-meteo.com` | Every 60 min (configurable 30–360) |
| Open-Meteo Forecast | `api.open-meteo.com` | Every 15 min (configurable 10–60) |

Both APIs are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

## Development

```bash
pip install -r requirements_test.txt
pytest
```
