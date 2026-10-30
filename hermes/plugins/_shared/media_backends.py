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
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Backend = tuple[str, str]


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


def configured_backends(section: str, default: Backend) -> list[Backend]:
    """``backends_from`` for the active profile's ``config.yaml`` section; the default when unreadable."""
    try:
        from hermes_cli.config import load_config

        return backends_from((load_config() or {}).get(section), default)
    except Exception as exc:  # noqa: BLE001 - a config problem must not break the tool
        logger.debug("media_backends: %s config read failed (%s); using the default", section, exc)
        return [default]


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
    call: Optional[Callable[..., Awaitable[Any]]] = None, max_tokens: int = 4000, timeout: float = 180,
) -> dict[str, Any]:
    """The first backend's answer that has text: ``{"provider", "model", "analysis", "failed"}``.

    ``failed`` lists the backends tried before it, each with its error. Raises ``AllBackendsFailed``
    when none answers. Each backend is called on its own (``direct_call``), never through a path
    that may hand the media to a provider the list does not name.
    """
    call = call or direct_call
    failures: list[dict[str, str]] = []
    for provider, model in backends:
        text, error = "", ""
        for _ in range(2):  # an empty reply gets one more try on the same backend
            try:
                response = await call(provider=provider, model=model, messages=messages, temperature=0.1,
                                      max_tokens=max_tokens, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - any backend failure moves on to the next one
                error = _summary(exc)
                break
            if text := answer_text(response):
                break
            error = "the reply had no text"
        if text:
            return {"provider": provider, "model": model, "analysis": text, "failed": failures}
        logger.warning("media_backends: %s/%s failed (%s); trying the next backend", provider, model, error)
        failures.append({"provider": provider, "model": model, "error": error})
    raise AllBackendsFailed(failures)
