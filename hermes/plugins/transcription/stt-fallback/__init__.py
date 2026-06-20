"""STT fallback-chain transcription provider.

Tries a chain of speech-to-text backends in order and returns the first
successful, non-empty transcript — so a single provider outage (or a missing
key) doesn't break voice input. Select with ``stt.provider: stt-fallback``.

Order comes from ``stt.fallback.chain`` in config (so the user's primary/order is
respected); when that key is unset it defaults to:

    groq -> xai -> openai -> elevenlabs -> local

  - groq        GROQ_API_KEY (whisper-large-v3-turbo)
  - xai         SuperGrok OAuth (``hermes auth add xai-oauth``) or XAI_API_KEY
  - openai      VOICE_TOOLS_OPENAI_KEY / OPENAI_API_KEY (Whisper API; paid)
  - elevenlabs  ELEVENLABS_API_KEY (Scribe)
  - local       faster-whisper — no key, offline floor (uses stt.local.model)

``mistral`` is intentionally NOT in the chain: upstream auto-detect skips it
because the ``mistralai`` SDK was quarantined on PyPI (malicious 2.4.6 release,
2026-05-12). Add ``mistral`` to ``stt.fallback.chain`` only if you accept that risk.

This composes the native backends by calling the built-in transcribe functions
in :mod:`tools.transcription_tools` directly (rather than re-implementing each
API). Those are internal APIs, so every access is defensively guarded; if an
upstream rename breaks a tier, the chain logs it and falls through to the next.

Note: this is outage/availability fallback, not quality fallback — a backend
that returns a *successful but wrong* transcript is accepted (the chain only
advances on error or an empty transcript).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent.transcription_provider import TranscriptionProvider

logger = logging.getLogger(__name__)

# Default chain when ``stt.fallback.chain`` is not set in config. The configured
# value (respecting the user's order / primary) always wins — this is only the
# safety-net default so the plugin still works out of the box.
_DEFAULT_CHAIN: List[str] = ["groq", "xai", "openai", "elevenlabs", "local"]

# Built-in STT backends a configured chain may reference. Unknown names and a
# self-reference to ``stt-fallback`` are filtered out so a typo can't break it.
_KNOWN_BACKENDS = frozenset(
    {"groq", "xai", "openai", "elevenlabs", "mistral", "local", "local_command"}
)


def _tt():
    """Import the built-in transcription module lazily (runtime-only dep)."""
    import tools.transcription_tools as tt  # noqa: WPS433

    return tt


def _env(name: str) -> str:
    """Resolve an env/secret value the way the built-ins do, with a fallback."""
    try:
        getter = getattr(_tt(), "get_env_value", None)
        if callable(getter):
            return getter(name) or ""
    except Exception:  # noqa: BLE001
        pass
    import os

    return os.getenv(name, "") or ""


def _get_chain() -> List[str]:
    """Resolve the fallback order from ``stt.fallback.chain`` in config.

    Falls back to ``_DEFAULT_CHAIN`` when unset/empty. Unknown backend names and
    a self-reference to ``stt-fallback`` are filtered out so a typo can't break
    dispatch. Keeping the order config-driven respects the user's configured
    primary instead of hardcoding a head in the plugin.
    """
    try:
        cfg = _tt()._load_stt_config() or {}
        fallback = cfg.get("fallback") or {}
        raw = fallback.get("chain")
        if isinstance(raw, list):
            cleaned = [str(x).strip().lower() for x in raw if str(x).strip()]
            cleaned = [c for c in cleaned if c in _KNOWN_BACKENDS]
            if cleaned:
                return cleaned
    except Exception as exc:  # noqa: BLE001 — config must never break dispatch
        logger.debug("stt-fallback: chain config read failed: %s", exc)
    return list(_DEFAULT_CHAIN)


class FallbackSTTProvider(TranscriptionProvider):
    """Virtual STT backend that dispatches to an ordered chain of providers."""

    @property
    def name(self) -> str:
        return "stt-fallback"

    @property
    def display_name(self) -> str:
        return "STT fallback (" + " -> ".join(_get_chain()) + ")"

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "chain",
            "tag": "tries each STT backend in order; falls through on error",
            "env_vars": [],
        }

    # -- per-backend availability ----------------------------------------
    def _available(self, backend: str) -> bool:
        try:
            tt = _tt()
            if backend == "groq":
                return bool(getattr(tt, "_HAS_OPENAI", False) and _env("GROQ_API_KEY"))
            if backend == "xai":
                from tools.xai_http import resolve_xai_http_credentials

                return bool(resolve_xai_http_credentials().get("api_key"))
            if backend == "openai":
                checker = getattr(tt, "_has_openai_audio_backend", None)
                return bool(
                    getattr(tt, "_HAS_OPENAI", False) and callable(checker) and checker()
                )
            if backend == "elevenlabs":
                return bool(_env("ELEVENLABS_API_KEY"))
            if backend == "local":
                if getattr(tt, "_HAS_FASTER_WHISPER", False):
                    return True
                has_cmd = getattr(tt, "_has_local_command", None)
                return bool(callable(has_cmd) and has_cmd())
        except Exception as exc:  # noqa: BLE001 — availability must never raise
            logger.debug("stt-fallback: availability(%s) failed: %s", backend, exc)
        return False

    # -- run one backend via the built-in transcribe functions ------------
    def _run(self, backend: str, file_path: str) -> Dict[str, Any]:
        tt = _tt()
        try:
            cfg = tt._load_stt_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}

        if backend == "groq":
            return tt._transcribe_groq(
                file_path, getattr(tt, "DEFAULT_GROQ_STT_MODEL", "whisper-large-v3-turbo")
            )
        if backend == "xai":
            return tt._transcribe_xai(file_path, "grok-stt")
        if backend == "openai":
            model = (cfg.get("openai", {}) or {}).get("model") or getattr(
                tt, "DEFAULT_STT_MODEL", "whisper-1"
            )
            return tt._transcribe_openai(file_path, model)
        if backend == "elevenlabs":
            model = (cfg.get("elevenlabs", {}) or {}).get("model_id") or getattr(
                tt, "DEFAULT_ELEVENLABS_STT_MODEL", "scribe_v2"
            )
            return tt._transcribe_elevenlabs(file_path, model)
        if backend == "local":
            raw = (cfg.get("local", {}) or {}).get("model") or getattr(
                tt, "DEFAULT_LOCAL_MODEL", "base"
            )
            normalize = getattr(tt, "_normalize_local_model", lambda value: value)
            return tt._transcribe_local(file_path, normalize(raw))
        return {
            "success": False,
            "transcript": "",
            "error": f"unknown backend {backend}",
            "provider": backend,
        }

    def is_available(self) -> bool:
        return any(self._available(b) for b in _get_chain())

    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        attempts: List[str] = []
        for backend in _get_chain():
            if not self._available(backend):
                attempts.append(f"{backend}: unavailable (no creds)")
                continue
            try:
                result = self._run(backend, file_path)
            except Exception as exc:  # noqa: BLE001 — built-ins shouldn't raise; defend
                logger.warning("stt-fallback: %s raised %s", backend, exc, exc_info=True)
                attempts.append(f"{backend}: {exc}")
                continue
            if (
                isinstance(result, dict)
                and result.get("success")
                and str(result.get("transcript", "")).strip()
            ):
                out = dict(result)
                out["provider"] = f"stt-fallback->{backend}"
                logger.info("stt-fallback: transcribed via %s", backend)
                return out
            err = (result or {}).get("error") if isinstance(result, dict) else None
            attempts.append(f"{backend}: {err or 'empty transcript'}")

        return {
            "success": False,
            "transcript": "",
            "provider": self.name,
            "error": "all STT backends failed -> " + " | ".join(attempts),
        }


def register(ctx) -> None:
    """Plugin entry point — register the fallback-chain STT provider."""
    ctx.register_transcription_provider(FallbackSTTProvider())
