"""Tests for AirQualityApiClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.outdoor_environment.api_client_aq import (
    AirQualityApiClient,
    CannotConnect,
    InvalidResponse,
)


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
async def test_fetch_returns_full_dict(session, aq_response):
    session.get.return_value = _make_response(aq_response)
    client = AirQualityApiClient(session, 45.46, 9.19)
    result = await client.fetch()

    assert isinstance(result, dict)
    assert result["european_aqi"] == 32.0
    assert result["pm2_5"] == 8.3
    assert result["uv_index"] == 4.5


@pytest.mark.asyncio
async def test_fetch_null_pollen_becomes_none(session, aq_response_nulls):
    session.get.return_value = _make_response(aq_response_nulls)
    client = AirQualityApiClient(session, 40.71, -74.01)
    result = await client.fetch()

    assert result["grass_pollen"] is None
    assert result["birch_pollen"] is None
    assert result["european_aqi"] == 28.0


@pytest.mark.asyncio
async def test_fetch_all_nulls_no_exception(session):
    payload = {"current": {k: None for k in ["european_aqi", "pm2_5", "grass_pollen"]}}
    session.get.return_value = _make_response(payload)
    client = AirQualityApiClient(session, 0.0, 0.0)
    result = await client.fetch()

    assert result.get("european_aqi") is None
    assert result.get("pm2_5") is None


@pytest.mark.asyncio
async def test_http_500_raises_invalid_response(session):
    session.get.return_value = _make_response({}, status=500)
    client = AirQualityApiClient(session, 45.46, 9.19)
    with pytest.raises(InvalidResponse):
        await client.fetch()


@pytest.mark.asyncio
async def test_missing_current_field_raises_invalid_response(session):
    session.get.return_value = _make_response({"latitude": 45.46})
    client = AirQualityApiClient(session, 45.46, 9.19)
    with pytest.raises(InvalidResponse):
        await client.fetch()


@pytest.mark.asyncio
async def test_connection_error_raises_cannot_connect(session):
    session.get.side_effect = aiohttp.ClientConnectionError("refused")
    client = AirQualityApiClient(session, 45.46, 9.19)
    with pytest.raises(CannotConnect):
        await client.fetch()


@pytest.mark.asyncio
async def test_timeout_raises_cannot_connect(session):
    session.get.side_effect = TimeoutError()
    client = AirQualityApiClient(session, 45.46, 9.19)
    with pytest.raises(CannotConnect):
        await client.fetch()
