"""Tests for WeatherApiClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import aiohttp
import pytest

from custom_components.outdoor_environment.api_client_aq import (
    CannotConnect,
    InvalidResponse,
)
from custom_components.outdoor_environment.api_client_weather import WeatherApiClient


def _make_response(json_data: dict, status: int = 200) -> MagicMock:
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.fixture
def session() -> MagicMock:
    s = MagicMock(spec=aiohttp.ClientSession)
    s.get = MagicMock()
    return s


@pytest.mark.asyncio
async def test_fetch_without_gti(session, wx_response):
    session.get.return_value = _make_response(wx_response)
    client = WeatherApiClient(session, 45.46, 9.19)
    result = await client.fetch()

    assert result["temperature_2m"] == 22.5
    assert "global_tilted_irradiance" not in result

    # Verify GTI params were NOT added to the URL
    call_kwargs = session.get.call_args
    params = call_kwargs[1].get("params", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {})
    assert "tilt" not in str(params)
    assert "global_tilted_irradiance" not in str(params)


@pytest.mark.asyncio
async def test_fetch_with_gti(session, wx_response_gti):
    session.get.return_value = _make_response(wx_response_gti)
    client = WeatherApiClient(session, 45.46, 9.19, panel_tilt=30.0, panel_azimuth=0.0)
    result = await client.fetch()

    assert result["global_tilted_irradiance"] == 570.0

    call_kwargs = session.get.call_args
    params_str = str(call_kwargs)
    assert "global_tilted_irradiance" in params_str
    assert "30" in params_str


@pytest.mark.asyncio
async def test_http_500_raises_invalid_response(session):
    session.get.return_value = _make_response({}, status=500)
    client = WeatherApiClient(session, 45.46, 9.19)
    with pytest.raises(InvalidResponse):
        await client.fetch()


@pytest.mark.asyncio
async def test_missing_current_raises_invalid_response(session):
    session.get.return_value = _make_response({"latitude": 45.46})
    client = WeatherApiClient(session, 45.46, 9.19)
    with pytest.raises(InvalidResponse):
        await client.fetch()


@pytest.mark.asyncio
async def test_connection_error_raises_cannot_connect(session):
    session.get.side_effect = aiohttp.ClientConnectionError("refused")
    client = WeatherApiClient(session, 45.46, 9.19)
    with pytest.raises(CannotConnect):
        await client.fetch()


@pytest.mark.asyncio
async def test_timeout_raises_cannot_connect(session):
    session.get.side_effect = TimeoutError()
    client = WeatherApiClient(session, 45.46, 9.19)
    with pytest.raises(CannotConnect):
        await client.fetch()
