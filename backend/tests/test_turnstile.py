from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.security import turnstile


@pytest.mark.asyncio
async def test_skips_verification_when_no_secret_configured(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "turnstile_secret_key", "")

    with patch.object(httpx, "AsyncClient") as client_mock:
        result = await turnstile.verify_turnstile_token("any-token")

    assert result is True
    client_mock.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_missing_token_when_secret_configured(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "turnstile_secret_key", "s3cret")

    with patch.object(httpx, "AsyncClient") as client_mock:
        result = await turnstile.verify_turnstile_token(None)

    assert result is False
    client_mock.assert_not_called()


def _fake_client(json_result: dict | None = None, raise_error: bool = False):
    mock_client = AsyncMock()
    if raise_error:
        mock_client.post.side_effect = httpx.HTTPError("boom")
    else:
        response = AsyncMock()
        response.json = lambda: json_result
        response.raise_for_status = lambda: None
        mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_returns_true_on_successful_verification(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "turnstile_secret_key", "s3cret")

    with patch.object(httpx, "AsyncClient", return_value=_fake_client({"success": True})):
        result = await turnstile.verify_turnstile_token("real-token", remote_ip="1.2.3.4")

    assert result is True


@pytest.mark.asyncio
async def test_returns_false_when_cloudflare_rejects_token(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "turnstile_secret_key", "s3cret")

    with patch.object(
        httpx, "AsyncClient", return_value=_fake_client({"success": False, "error-codes": ["invalid-input-response"]})
    ):
        result = await turnstile.verify_turnstile_token("bad-token")

    assert result is False


@pytest.mark.asyncio
async def test_returns_false_on_network_error(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "turnstile_secret_key", "s3cret")

    with patch.object(httpx, "AsyncClient", return_value=_fake_client(raise_error=True)):
        result = await turnstile.verify_turnstile_token("real-token")

    assert result is False
