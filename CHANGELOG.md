# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`Irrigation Needed` never turned on, in any climate.** It compared
  evapotranspiration from the `current` block — a figure covering that block's
  own 15-minute interval — against a threshold measured in millimetres per day,
  a comparison that cannot be true. Measured against Open-Meteo for Milan on
  2026-09-14: 0.11 mm over the current interval against 3.59 mm for the day, on
  a 2 mm threshold. The sensor now uses the API's daily totals
  (`et0_fao_evapotranspiration` and `precipitation_sum`), requested on the same
  call, so there is no extra API request. The `et0_today` and
  `precipitation_today` attributes finally hold what their names claim, and a
  new `period` attribute records that both are forecasts for the whole day
  rather than what has accumulated so far.
  If you have an automation on this sensor, **it can now fire for the first
  time.**

### Changed

- **`Comfort Index` is now a single continuous measure instead of three
  incompatible ones.** It switched formula at 27 °C, at 40% relative humidity and
  at 10 °C with wind, and the three branches shared neither a scale nor a
  direction — in one a higher number meant hotter and worse, in another warmer
  and better. The value could fall from 64.9 to 0.9 across a tenth of a degree
  and never had a defined meaning. It is now derived from apparent temperature
  alone, on a documented scale where 100 is comfortable and 0 is dangerous:
  100 between 18 °C and 24 °C apparent, falling to 0 at 40 °C and at −10 °C.
  **Your recorded history is on the old scale and cannot be compared with the
  new one**, and the direction is inverted relative to the old hot-weather
  branch. The entity keeps its ID, so dashboards and automations still resolve —
  check any threshold you set on it.
  ([#12](https://github.com/nuggetz/ha-outdoor-environment/issues/12))

## [0.2.1] - 2026-09-14

### Fixed

- **Deprecation warnings for `CONCENTRATION_MICROGRAMS_PER_CUBIC_METER` and
  `CONCENTRATION_PARTS_PER_MILLION` in the Home Assistant log.** Both constants
  are deprecated in favour of `UnitOfDensity.MICROGRAMS_PER_CUBIC_METER` and
  `UnitOfRatio.PARTS_PER_MILLION`, which only exist from HA 2026.7.0 onwards —
  adopting them would have raised the minimum supported version from 2024.1.0 to
  pre-empt a removal scheduled for HA 2027.8. The unit strings are byte-identical,
  so the component now declares them itself. The warnings stop, the minimum stays
  at 2024.1.0, and no entity, unit or long-term statistic changes.
  ([#11](https://github.com/nuggetz/ha-outdoor-environment/issues/11))

## [0.2.0] - 2026-09-07

### Fixed

- **Solar panel settings had no effect unless entered during initial setup.**
  `panel_tilt` and `panel_azimuth` were read from the config entry data only, so
  setting a tilt afterwards through **Configure** never created the Global
  Tilted Irradiance sensor. Both values are now read from the options as well.
  ([@bexelbie](https://github.com/bexelbie))
- **`Pollen Total Risk` reported `0` when it had no pollen data at all.**
  Open-Meteo publishes pollen only for European locations, so enabling Group B
  anywhere else produced a confident "no risk" reading built on no readings. The
  sensor now reports `unknown` when every pollen value is missing, and continues
  to report `0` when the values are present and genuinely zero.
  ([@bexelbie](https://github.com/bexelbie))

### Changed

- **Each Open-Meteo API is polled only if an enabled sensor group needs it.**
  Both APIs were refreshed on every cycle regardless of configuration. The
  enabled groups now decide: disable every group that depends on the weather
  API and it is no longer contacted, neither at startup nor on the update
  interval.
  ([@bexelbie](https://github.com/bexelbie))
- **Derived sensors are created only when the API they read is being polled.**
  A calculated sensor is gated on the data it consumes rather than on the group
  it belongs to, so an API that is never polled no longer produces entities that
  could never hold a value. If you have disabled a whole group, some calculated
  sensors will no longer be created.
  ([@bexelbie](https://github.com/bexelbie))
- **Entities the configuration no longer provides are deleted from the entity
  registry.** Disabling a sensor group stopped its entities from being created,
  but the registry kept the rows, so they stayed `unavailable` forever with no
  way out except deleting each one by hand. They are now removed at startup,
  which is what Home Assistant's own integrations do. **Deleting a registry row
  also deletes that entity's history and long-term statistics, and that cannot
  be undone**: re-enabling the group creates the entities again, empty. Only the
  `sensor` domain is touched.

## [0.1.2] - 2026-08-19

### Fixed

- **`Dominant Pollutant` failed to start and errored on every update.** The sensor
  reports which pollutant drives the European AQI, so its value is a name such as
  `o3` — but it inherited `state_class: measurement` from its base class, which
  tells Home Assistant to expect a number. Home Assistant rejected the state with
  `ValueError: ... it has the non-numeric value`, the entity was never added, and
  the error repeated on every air-quality and weather coordinator refresh. This
  affected every installation that receives European sub-AQI data, in the default
  configuration. The sensor now declares `device_class: enum`.
- **`Lightning Risk` had the same defect.** It returns `none`/`low`/`medium`/`high`
  and carried the same inherited `state_class`. It did not surface in logs only
  because the entity is disabled by default; enabling it produced an identical
  failure. It now declares `device_class: enum`.
- **`Frost Risk` and `Irrigation Needed` no longer claim to be measurements.**
  Both return a boolean. Home Assistant accepted these without error — a `bool`
  is a subclass of `int` — but recorded them as the literal states `True`/`False`
  and then silently discarded them from long-term statistics, so these sensors
  never produced usable history. They no longer declare a `state_class`.

### Changed

- `state_class` is no longer set on the shared base class for derived sensors.
  Each numeric sensor now declares it explicitly, so a non-numeric sensor can no
  longer inherit an incorrect one by accident. No numeric sensor changed value,
  unit, `unique_id` or `entity_id`.

### Added

- Platform-level tests that set the integration up inside Home Assistant and
  assert every entity — including those disabled by default — writes a valid
  state. The previous tests exercised `native_value` directly, one layer below
  where Home Assistant validates state, so they could not detect these failures.

### Documentation

- README updated for availability in the HACS default store: installation no
  longer requires adding a custom repository, plus HACS and My Home Assistant
  badges and a social preview image.

## [0.1.1] - 2026-05-24

### Fixed

- Compatibility with current Home Assistant releases: corrected `SensorDeviceClass`
  attribute names and replaced `UnitOfPressure.KILOPASCAL` with `UnitOfPressure.KPA`.
- `manifest.json` key ordering and other issues reported by hassfest and HACS
  validation.

### Added

- Branding: repository header image, integration icon, README heading.

## [0.1.0] - 2026-05-22

### Added

- Initial release. Home Assistant custom integration exposing 80+ outdoor
  environment sensors from the free Open-Meteo APIs, with no API key required:
  air quality and per-pollutant sub-AQI (EU and US), pollen, UV, weather,
  agrometeorology, solar radiation including optional Global Tilted Irradiance,
  and calculated sensors such as comfort index, ventilation score and heat index.
- Dual coordinator design: air quality polled hourly, weather every 15 minutes,
  so a failure in one API does not affect the other.
- Config flow with per-group enable switches and configurable update intervals.

[0.2.0]: https://github.com/nuggetz/ha-outdoor-environment/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/nuggetz/ha-outdoor-environment/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/nuggetz/ha-outdoor-environment/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nuggetz/ha-outdoor-environment/releases/tag/v0.1.0
