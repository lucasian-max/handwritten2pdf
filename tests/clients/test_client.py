"""Tests for the LiteLLM client wrapper."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from clients.llm.client import acompletion


def _response(content: str | None, finish_reason: str = "stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
    )


@pytest.mark.asyncio
async def test_returns_content():
    with patch("clients.llm.client.litellm.acompletion", new_callable=AsyncMock) as mock:
        mock.return_value = _response("Hello")
        out = await acompletion("m", [], 0.1, 100)
    assert out == "Hello"


@pytest.mark.asyncio
async def test_none_content_raises_so_retry_can_run():
    # A reasoning model on a long page can return content=None instead of raising;
    # the graph's tenacity retry only fires on exceptions.
    with patch("clients.llm.client.litellm.acompletion", new_callable=AsyncMock) as mock:
        mock.return_value = _response(None, finish_reason="length")
        with pytest.raises(ValueError, match="empty content"):
            await acompletion("m", [], 0.1, 100)


@pytest.mark.asyncio
async def test_whitespace_content_raises():
    with patch("clients.llm.client.litellm.acompletion", new_callable=AsyncMock) as mock:
        mock.return_value = _response("   \n  ")
        with pytest.raises(ValueError, match="empty content"):
            await acompletion("m", [], 0.1, 100)


@pytest.mark.asyncio
async def test_api_base_forwarded():
    with patch("clients.llm.client.litellm.acompletion", new_callable=AsyncMock) as mock:
        mock.return_value = _response("ok")
        await acompletion(
            "openai/x",
            [],
            0.1,
            100,
            api_key="k",
            api_base="https://proxy.example/v1",
        )
    kwargs = mock.call_args.kwargs
    assert kwargs["api_base"] == "https://proxy.example/v1"
    assert kwargs["api_key"] == "k"
