"""LiteLLM client — thin async wrapper for model completions."""

import logging

import litellm

litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class TruncatedResponse(ValueError):
    """The provider stopped the model at its token cap; the content is partial."""


async def acompletion(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    api_key: str | None = None,
    api_base: str | None = None,
) -> str:
    """Run an async litellm completion and return the text content."""
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key is not None:
        kwargs["api_key"] = api_key
    if api_base is not None:
        kwargs["api_base"] = api_base

    try:
        response = await litellm.acompletion(**kwargs)
    except Exception as exc:
        message = str(exc)
        if "Spending limit" in message or "spending limit" in message:
            raise RuntimeError(
                "The AI proxy is out of credits right now (HTTP 402). "
                "Wait for the limit to reset, ask in #hackclub-ai, or switch "
                "provider in Settings."
            ) from exc
        if "429" in message or "rate limit" in message.lower():
            raise RuntimeError(
                "The AI provider is rate-limiting requests (HTTP 429). "
                "Try again in a minute or switch provider in Settings."
            ) from exc
        raise
    choice = response.choices[0]
    content = choice.message.content
    finish = getattr(choice, "finish_reason", None)
    if not content or not content.strip():
        # Some providers (notably reasoning models on long pages) return an empty
        # content field instead of raising. Treat it as a retriable failure so the
        # tenacity retry in the graph gets another attempt instead of crashing
        # downstream on None.strip().
        raise ValueError(f"Model returned empty content (finish_reason={finish!r}, model={model})")
    if finish == "length":
        # Partial content: a LaTeX body cut mid-command compiles to nothing.
        raise TruncatedResponse(
            f"Model output hit the token cap (finish_reason='length', model={model})"
        )
    return content
