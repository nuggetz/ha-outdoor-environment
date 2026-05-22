"""Shared pytest fixtures for Outdoor Environment tests."""
from __future__ import annotations

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.outdoor_environment.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this package."""

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text())


@pytest.fixture
def aq_response() -> dict:
    return load_fixture("air_quality_response.json")


@pytest.fixture
def aq_response_nulls() -> dict:
    return load_fixture("air_quality_response_nulls.json")


@pytest.fixture
def wx_response() -> dict:
    return load_fixture("weather_response.json")


@pytest.fixture
def wx_response_gti() -> dict:
    return load_fixture("weather_response_gti.json")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
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
        },
        options={},
    )


@pytest.fixture
def mock_config_entry_gti() -> MockConfigEntry:
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
            "panel_tilt": 30.0,
            "panel_azimuth": 0.0,
        },
        options={},
    )
