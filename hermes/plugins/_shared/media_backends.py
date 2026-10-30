"""Ordered backends for the media-analysis tools (``video_analyze``, ``audio_analyze``).

A tool's top-level config section lists where its media may go, in order::

    video_analyze:
      backends:
        - {provider: openrouter, model: xiaomi/mimo-v2.5}

The single form (``provider`` and ``model`` with no ``backends``) reads as a one-entry list, and a
section with neither falls back to the tool's default: the media goes to the listed backends and
nowhere else. ``analyze`` tries the backends in order:
an error moves on to the next one, and so does an answer with no text after one retry. A reply
that is only reasoning (the model never saw the media, or gave up) is not an analysis.

An answer cut off at the output limit (``finish_reason == "length"``) also moves on: a thinking
model spends its output budget on hidden thoughts first, so a small cap returns the opening of an
answer with ``success`` and the questions unanswered. It is returned, marked ``truncated``, only
when no backend answers in full. The cap is ``MAX_OUTPUT_TOKENS`` unless the section sets its own
``max_tokens`` (a positive integer), for a recording long enough to need more::

    audio_analyze:
      max_tokens: 32768
      backends: [...]
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Backend = tuple[str, str]

# Room for a thinking model's hidden thoughts and the answer: thoughts count against the cap, and
# a medium-effort Gemini spent nearly 4,000 tokens thinking about a 2.5-minute recording.
MAX_OUTPUT_TOKENS = 16384

TRUNCATED_NOTE = ("The answer stops at the output limit on every backend: whatever comes after the cut, "
                  "including any question not yet answered, is unknown, not 'none found'.")


def _pair(entry: Any) -> Optional[Backend]:
    if not isinstance(entry, dict):
        return None
    provider, model = str(entry.get("provider") or "").strip(), str(entry.get("model") or "").strip()
    return (provider, model) if provider and model else None


def backends_from(section: Any, default: Backend) -> list[Backend]:
    """The ordered backends a config section names (duplicates dropped), else ``[default]``."""
    section = section if isinstance(section, dict) else {}
    listed = section.get("backends")
    pairs = [p for p in map(_pair, listed) if p] if isinstance(listed, list) else []
    if not pairs and (single := _pair(section)):
        pairs = [single]
    return list(dict.fromkeys(pairs)) or [default]


def max_tokens_from(section: Any) -> int:
    """The section's ``max_tokens`` when it is a positive integer, else ``MAX_OUTPUT_TOKENS``."""
    value = section.get("max_tokens") if isinstance(section, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return MAX_OUTPUT_TOKENS
    return value


def _section(section: str) -> Any:
    from hermes_cli.config import load_config

    return (load_config() or {}).get(section)


def configured_backends(section: str, default: Backend) -> list[Backend]:
    """``backends_from`` for the active profile's ``config.yaml`` section; the default when unreadable."""
    try:
        return backends_from(_section(section), default)
    except Exception as exc:  # noqa: BLE001 - a config problem must not break the tool
        logger.debug("media_backends: %s config read failed (%s); using the default", section, exc)
        return [default]


def configured_max_tokens(section: str) -> int:
    """``max_tokens_from`` for the active profile's ``config.yaml`` section; the default when unreadable."""
    try:
        return max_tokens_from(_section(section))
    except Exception as exc:  # noqa: BLE001 - a config problem must not break the tool
        logger.debug("media_backends: %s config read failed (%s); using the default cap", section, exc)
        return MAX_OUTPUT_TOKENS


def answer_text(response: Any) -> str:
    """The reply's own text (never its reasoning), or ``""``."""
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return ""
    content = getattr(message, "content", None)
    if isinstance(content, list):
        content = "".join(str(p.get("text") or "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "").strip()


def was_cut_off(response: Any) -> bool:
    """True when the reply stopped at the output limit rather than ending on its own."""
    try:
        reason = response.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return False
    return str(reason or "").lower() in ("length", "max_tokens")


class AllBackendsFailed(RuntimeError):
    def __init__(self, failures: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{f['provider']}/{f['model']}: {f['error']}" for f in failures))
        self.failures = failures


async def direct_call(*, provider: str, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """One request to exactly *provider* / *model*.

    Not ``async_call_llm``: on a quota, rate-limit, timeout or connection error it moves an
    explicit-provider call on to other providers and finally the main agent's model, which would
    send the media somewhere the section does not list and credit the answer to the backend named.
    """
    from agent.auxiliary_client import resolve_provider_client

    client, resolved = resolve_provider_client(provider, model, async_mode=True)
    if client is None:
        raise RuntimeError(f"no client for {provider} (no login or key)")
    return await client.chat.completions.create(model=resolved or model, messages=messages, **kwargs)


def _summary(exc: Exception) -> str:
    """The error's type, HTTP status and first line, short: provider text can carry URLs and ids."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return " ".join(p for p in (type(exc).__name__, f"HTTP {status}" if status else "", first[:120]) if p)


async def analyze(
    backends: list[Backend], messages: list[dict[str, Any]], *,
    call: Optional[Callable[..., Awaitable[Any]]] = None, max_tokens: int = MAX_OUTPUT_TOKENS,
    timeout: float = 180,
) -> dict[str, Any]:
    """The first backend's complete answer: ``{"provider", "model", "analysis", "failed", "truncated"}``.

    ``failed`` lists the backends tried before it, each with its error. When every backend fails
    but one answered in part, that first partial answer is returned with ``truncated`` set (and is
    left out of ``failed``); with no text at all, raises ``AllBackendsFailed``. Each backend is
    called on its own (``direct_call``), never through a path that may hand the media to a provider
    the list does not name.
    """
    call = call or direct_call
    failures: list[dict[str, str]] = []
    partial: Optional[dict[str, Any]] = None
    for provider, model in backends:
        text, error, cut_off = "", "", False
        for _ in range(2):  # an empty reply gets one more try on the same backend
            try:
                response = await call(provider=provider, model=model, messages=messages, temperature=0.1,
                                      max_tokens=max_tokens, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - any backend failure moves on to the next one
                error = _summary(exc)
                break
            if text := answer_text(response):
                cut_off = was_cut_off(response)
                break
            error = "the reply had no text"
        if text and not cut_off:
            return {"provider": provider, "model": model, "analysis": text, "failed": failures,
                    "truncated": False}
        if text:
            error = "the answer was cut off at the output limit"
        logger.warning("media_backends: %s/%s failed (%s); trying the next backend", provider, model, error)
        failure = {"provider": provider, "model": model, "error": error}
        failures.append(failure)
        if text and partial is None:
            partial = {"provider": provider, "model": model, "analysis": text, "failure": failure}
    if partial is not None:
        return {"provider": partial["provider"], "model": partial["model"], "analysis": partial["analysis"],
                "failed": [f for f in failures if f is not partial["failure"]], "truncated": True}
    raise AllBackendsFailed(failures)
