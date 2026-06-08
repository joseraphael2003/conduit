import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Type, Union

import httpx
from openai import OpenAI
from openai._exceptions import APIError, AuthenticationError, RateLimitError
from pydantic import BaseModel


DEFAULT_MAX_TOKENS = 2048
DEFAULT_MODEL = "accounts/fireworks/routers/kimi-k2p6-turbo"
DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"


class FireworksClient:
    """Async wrapper around the Fireworks AI OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("FIREWORKS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "FIREWORKS_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = model or DEFAULT_MODEL
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=60.0,
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_schema: Optional[Type[BaseModel]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Dict[str, Any]]:
        """Call Fireworks chat completions with 3x retry and exponential backoff.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            model: Override the default model. Defaults to self.model.
            max_tokens: Override the default max_tokens. Defaults to 2048.
            temperature: Sampling temperature.
            json_schema: A flat Pydantic model for structured JSON output.
            response_format: Raw response_format dict (ignored if json_schema is set).

        Returns:
            The completion content string, or parsed JSON dict if json_schema is used.

        Raises:
            AuthenticationError: On 401 (no retry).
            APIError: On unrecoverable API errors after retries.
        """
        model = model or self.model
        max_tokens = max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature

        if json_schema is not None:
            schema = json_schema.model_json_schema()
            _flatten_schema(schema)
            kwargs["response_format"] = {
                "type": "json_object",
                "schema": schema,
            }
        elif response_format is not None:
            kwargs["response_format"] = response_format

        last_exception: Optional[Exception] = None
        backoff_delays = [1, 2, 4]

        for attempt in range(len(backoff_delays)):
            try:

                def _call():
                    return self._get_client().chat.completions.create(**kwargs)

                async with asyncio.timeout(120):
                    response = await asyncio.to_thread(_call)
                content = response.choices[0].message.content

                if json_schema is not None:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as exc:
                        raise APIError(
                            "AI returned an invalid or truncated JSON response",
                            request=httpx.Request("POST", f"{self.base_url}/chat/completions"),
                            body=None,
                        ) from exc
                return content

            except AuthenticationError:
                # 401: raise immediately, no retry
                raise
            except (RateLimitError, APIError) as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code == 429:
                    # Rate limit: retry
                    last_exception = exc
                elif status_code in (500, 503):
                    # Server error: retry
                    last_exception = exc
                else:
                    # Other API errors: raise immediately
                    raise
            except Exception as exc:
                # Non-API errors: raise immediately
                raise

            if attempt < len(backoff_delays) - 1:
                await asyncio.sleep(backoff_delays[attempt])

        # All retries exhausted
        if last_exception:
            raise last_exception
        raise APIError(
            "Max retries exceeded for Fireworks API chat completion",
            request=httpx.Request("POST", f"{self.base_url}/chat/completions"),
            body=None,
        )


def _flatten_schema(schema: Dict[str, Any]) -> None:
    """Remove complex JSON Schema constraints from a Pydantic schema.

    Fireworks AI requires flat schemas with no oneOf, pattern, minLength,
    maxLength, minItems, or maxItems.
    """
    # Keys to strip at the current level
    strip_keys = {"oneOf", "pattern", "minLength", "maxLength", "minItems", "maxItems"}
    for key in list(schema.keys()):
        if key in strip_keys:
            del schema[key]

    # Recurse into nested structures
    for key, value in schema.items():
        if isinstance(value, dict):
            _flatten_schema(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _flatten_schema(item)
