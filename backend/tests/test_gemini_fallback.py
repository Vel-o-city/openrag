from unittest.mock import patch

import pytest
from google.genai import errors

from app.gemini import client


def _quota_error() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}})


def _bad_request_error() -> errors.ClientError:
    return errors.ClientError(400, {"error": {"status": "INVALID_ARGUMENT", "message": "bad request"}})


def _model_unavailable_error() -> errors.ClientError:
    return errors.ClientError(
        404,
        {"error": {"status": "NOT_FOUND", "message": "This model is no longer available to new users."}},
    )


@pytest.mark.asyncio
async def test_extract_from_text_falls_back_to_next_model_on_quota_error(monkeypatch):
    monkeypatch.setattr(client.settings, "extraction_models", ["model-a", "model-b"])
    calls = []

    async def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == "model-a":
            raise _quota_error()
        return type("R", (), {"parsed": "ok"})()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content = fake_generate_content
        result = await client.extract_from_text("hello")

    assert result == "ok"
    assert calls == ["model-a", "model-b"]


@pytest.mark.asyncio
async def test_extract_from_text_does_not_fall_back_on_non_quota_error(monkeypatch):
    monkeypatch.setattr(client.settings, "extraction_models", ["model-a", "model-b"])
    calls = []

    async def fake_generate_content(*, model, contents, config):
        calls.append(model)
        raise _bad_request_error()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content = fake_generate_content
        with pytest.raises(errors.ClientError) as exc_info:
            await client.extract_from_text("hello")

    assert exc_info.value.status == "INVALID_ARGUMENT"
    assert calls == ["model-a"]


@pytest.mark.asyncio
async def test_extract_from_text_falls_back_on_model_unavailable_404(monkeypatch):
    # Observed in practice: the entire gemini-2.5 generation returns 404 "no
    # longer available to new users" on a freshly-created API key, distinct
    # from quota exhaustion but equally worth falling back on.
    monkeypatch.setattr(client.settings, "extraction_models", ["model-a", "model-b"])
    calls = []

    async def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == "model-a":
            raise _model_unavailable_error()
        return type("R", (), {"parsed": "ok"})()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content = fake_generate_content
        result = await client.extract_from_text("hello")

    assert result == "ok"
    assert calls == ["model-a", "model-b"]


@pytest.mark.asyncio
async def test_extract_from_text_raises_last_error_if_every_model_exhausted(monkeypatch):
    monkeypatch.setattr(client.settings, "extraction_models", ["model-a", "model-b"])

    async def fake_generate_content(*, model, contents, config):
        raise _quota_error()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content = fake_generate_content
        with pytest.raises(errors.ClientError) as exc_info:
            await client.extract_from_text("hello")

    assert exc_info.value.status == "RESOURCE_EXHAUSTED"


@pytest.mark.asyncio
async def test_chat_stream_falls_back_to_next_model_on_quota_error(monkeypatch):
    monkeypatch.setattr(client.settings, "chat_models", ["model-a", "model-b"])
    calls = []

    async def fake_generate_content_stream(*, model, contents, config):
        calls.append(model)
        if model == "model-a":
            raise _quota_error()

        async def gen():
            yield type("Chunk", (), {"text": "hi"})()

        return gen()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content_stream = fake_generate_content_stream
        chunks = [c async for c in client.chat_stream("sys", "user")]

    assert chunks == ["hi"]
    assert calls == ["model-a", "model-b"]


@pytest.mark.asyncio
async def test_chat_stream_does_not_fall_back_once_a_chunk_was_already_yielded(monkeypatch):
    monkeypatch.setattr(client.settings, "chat_models", ["model-a", "model-b"])
    calls = []

    async def fake_generate_content_stream(*, model, contents, config):
        calls.append(model)

        async def gen():
            yield type("Chunk", (), {"text": "partial answer"})()
            raise _quota_error()

        return gen()

    with patch.object(client, "get_client") as get_client_mock:
        get_client_mock.return_value.aio.models.generate_content_stream = fake_generate_content_stream
        with pytest.raises(errors.ClientError):
            _ = [c async for c in client.chat_stream("sys", "user")]

    # only the first model was ever tried — no retry once output has started
    assert calls == ["model-a"]
