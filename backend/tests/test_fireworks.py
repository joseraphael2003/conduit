import json
import os
import pytest
import httpx
import respx
from pydantic import BaseModel

from services.fireworks import FireworksClient


@pytest.fixture
def fireworks_client():
    return FireworksClient(api_key="test-fireworks-key")


@pytest.mark.asyncio
async def test_fireworks_client_base_url():
    """FireworksClient base_url defaults to Fireworks AI endpoint."""
    client = FireworksClient(api_key="test-key")
    assert client.base_url == "https://api.fireworks.ai/inference/v1"


@pytest.mark.asyncio
async def test_fireworks_client_base_url_override():
    """FireworksClient base_url can be overridden."""
    client = FireworksClient(api_key="test-key", base_url="https://custom.example.com")
    assert client.base_url == "https://custom.example.com"


@pytest.mark.asyncio
async def test_fireworks_chat_completion_mock_respx(fireworks_client):
    """Mock Fireworks chat completion with respx and assert request params."""
    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello!",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Say hello"}],
        )

        assert result == "Hello!"
        assert route.called, "Fireworks chat completion endpoint should have been called"

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["model"] == "accounts/fireworks/routers/kimi-k2p6-turbo"
        assert body["max_tokens"] == 2048
        assert body["messages"] == [{"role": "user", "content": "Say hello"}]


@pytest.mark.asyncio
async def test_fireworks_chat_completion_max_tokens_override(fireworks_client):
    """max_tokens can be overridden per call."""
    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Short",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=100,
        )

        assert result == "Short"
        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["max_tokens"] == 100


@pytest.mark.asyncio
async def test_fireworks_chat_completion_json_schema_mock(fireworks_client):
    """Mock Fireworks chat completion with json_schema and assert flat schema."""

    class FlatResponse(BaseModel):
        summary: str
        score: int

    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": '{"summary": "test", "score": 42}',
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Summarize"}],
            json_schema=FlatResponse,
        )

        assert isinstance(result, dict)
        assert result["summary"] == "test"
        assert result["score"] == 42

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["model"] == "accounts/fireworks/routers/kimi-k2p6-turbo"
        assert body["max_tokens"] == 2048
        assert body["response_format"]["type"] == "json_object"
        schema = body["response_format"]["schema"]
        # Ensure flat schema: no complex constraints
        assert "oneOf" not in schema
        assert "pattern" not in schema
        assert "minLength" not in schema
        assert "maxLength" not in schema
        assert "minItems" not in schema
        assert "maxItems" not in schema


@pytest.mark.asyncio
async def test_fireworks_chat_completion_retry_500(fireworks_client):
    """Retry on 500 error with exponential backoff."""
    call_count = 0

    def _side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, json={"error": "Internal Server Error"})
        return httpx.Response(
            200,
            json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Recovered",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock:
        route = respx.post(
            "https://api.fireworks.ai/inference/v1/chat/completions"
        ).mock(side_effect=_side_effect)

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Retry me"}],
        )

        assert result == "Recovered"
        assert call_count == 3


@pytest.mark.asyncio
async def test_fireworks_chat_completion_401_no_retry(fireworks_client):
    """401 should raise immediately without retry."""
    call_count = 0

    def _side_effect(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            401,
            json={"error": "Invalid Authentication"},
        )

    with respx.mock:
        route = respx.post(
            "https://api.fireworks.ai/inference/v1/chat/completions"
        ).mock(side_effect=_side_effect)

        from openai._exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            await fireworks_client.chat_completion(
                messages=[{"role": "user", "content": "Auth fail"}],
            )

        assert call_count == 1


@pytest.mark.asyncio
async def test_fireworks_chat_completion_retry_429(fireworks_client):
    """Retry on 429 rate limit error."""
    call_count = 0

    def _side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(429, json={"error": "Rate limit exceeded"})
        return httpx.Response(
            200,
            json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Rate limit ok",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock:
        route = respx.post(
            "https://api.fireworks.ai/inference/v1/chat/completions"
        ).mock(side_effect=_side_effect)

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Rate limit"}],
        )

        assert result == "Rate limit ok"
        assert call_count == 2


@pytest.mark.asyncio
async def test_fireworks_chat_completion_retry_503(fireworks_client):
    """Retry on 503 service unavailable error."""
    call_count = 0

    def _side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(503, json={"error": "Service Unavailable"})
        return httpx.Response(
            200,
            json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Service ok",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock:
        route = respx.post(
            "https://api.fireworks.ai/inference/v1/chat/completions"
        ).mock(side_effect=_side_effect)

        result = await fireworks_client.chat_completion(
            messages=[{"role": "user", "content": "Service unavailable"}],
        )

        assert result == "Service ok"
        assert call_count == 2
