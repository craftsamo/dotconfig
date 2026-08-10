"""TTS fallback-chain provider.

Tries a chain of text-to-speech backends in order and returns the first that
produces audio — so a single backend outage (e.g. the local qwen3-tts server
being down) still yields speech. Select with ``tts.provider: tts-fallback``.

Order comes from ``tts.fallback.chain`` in config (so the user's primary/order is
respected); when unset it defaults to:

    qwen3-tts -> edge

Each tier is either a registered TTS *plugin* (e.g. ``qwen3-tts``) resolved from the
registry, or a *built-in* provider (``edge`` / ``openai`` / ``gemini`` / ``xai`` /
``elevenlabs`` / ``mistral`` / ``minimax`` / ``neutts`` / ``kittentts`` /
``piper``) invoked through the native ``_generate_*`` functions in
:mod:`tools.tts_tool`.

This is outage fallback, not quality fallback: a tier that writes a non-empty
audio file wins; the chain advances only on error or empty output. Built-in
tiers read their *own* config (e.g. ``tts.edge.voice``) — set a Japanese
``tts.edge.voice`` (e.g. ``ja-JP-NanamiNeural``) so the edge fallback isn't an
English voice.

The built-in generators are internal APIs, so every call is defensively guarded;
if an upstream rename breaks a tier the chain logs it and advances to the next.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from agent.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

# Default chain when ``tts.fallback.chain`` is unset. The configured value
# (respecting the user's order / primary) always wins — this is the safety net.
_DEFAULT_CHAIN: List[str] = ["qwen3-tts", "edge"]


def _tt():
    """Import the built-in TTS module lazily (runtime-only dependency)."""
    import tools.tts_tool as tt  # noqa: WPS433

    return tt


def _get_chain() -> List[str]:
    """Resolve the fallback order from ``tts.fallback.chain`` in config.

    Falls back to ``_DEFAULT_CHAIN`` when unset/empty. Empty entries and a
    self-reference to ``tts-fallback`` are filtered out; unknown names are left
    in (they simply fail at runtime and the chain advances). Keeping the order
    config-driven respects the user's configured primary.
    """
    try:
        cfg = _tt()._load_tts_config() or {}
        fallback = cfg.get("fallback") or {}
        raw = fallback.get("chain")
        if isinstance(raw, list):
            cleaned = [str(x).strip().lower() for x in raw if str(x).strip()]
            cleaned = [c for c in cleaned if c != "tts-fallback"]
            if cleaned:
                return cleaned
    except Exception as exc:  # noqa: BLE001 — config must never break dispatch
        logger.debug("tts-fallback: chain config read failed: %s", exc)
    return list(_DEFAULT_CHAIN)


def _run_builtin(tt, provider: str, text: str, output_path: str, cfg: Dict[str, Any]) -> None:
    """Invoke a built-in TTS generator, writing audio to *output_path*."""
    if provider == "edge":
        tt._import_edge_tts()
        import asyncio

        try:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(
                    lambda: asyncio.run(tt._generate_edge_tts(text, output_path, cfg))
                ).result(timeout=60)
        except RuntimeError:
            asyncio.run(tt._generate_edge_tts(text, output_path, cfg))
        return
    if provider == "elevenlabs":
        tt._import_elevenlabs()
        tt._generate_elevenlabs(text, output_path, cfg)
        return
    if provider == "openai":
        tt._import_openai_client()
        tt._generate_openai_tts(text, output_path, cfg)
        return
    if provider == "gemini":
        tt._generate_gemini_tts(text, output_path, cfg)
        return
    if provider == "xai":
        tt._generate_xai_tts(text, output_path, cfg)
        return
    if provider == "minimax":
        tt._generate_minimax_tts(text, output_path, cfg)
        return
    if provider == "mistral":
        tt._import_mistral_client()
        tt._generate_mistral_tts(text, output_path, cfg)
        return
    if provider == "neutts":
        tt._generate_neutts(text, output_path, cfg)
        return
    if provider == "kittentts":
        tt._import_kittentts()
        tt._generate_kittentts(text, output_path, cfg)
        return
    if provider == "piper":
        tt._import_piper()
        tt._generate_piper_tts(text, output_path, cfg)
        return
    raise RuntimeError(f"unknown built-in TTS provider '{provider}'")


class FallbackTTSProvider(TTSProvider):
    """Virtual TTS backend that dispatches to an ordered chain of providers."""

    @property
    def name(self) -> str:
        return "tts-fallback"

    @property
    def display_name(self) -> str:
        return "TTS fallback (" + " -> ".join(_get_chain()) + ")"

    @property
    def voice_compatible(self) -> bool:
        # The winning tier may be WAV (qwen3-tts) or MP3 (edge); the gateway runs
        # ffmpeg -> Opus for voice delivery either way.
        return True

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "chain",
            "tag": "tries each TTS backend in order; falls through on error",
            "env_vars": [],
        }

    def is_available(self) -> bool:
        return True

    def _run_tier(
        self,
        tier: str,
        text: str,
        output_path: str,
        voice: Optional[str],
        model: Optional[str],
        speed: Optional[float],
        fmt: str,
    ) -> None:
        tt = _tt()
        builtins = set(getattr(tt, "BUILTIN_TTS_PROVIDERS", frozenset()))
        if tier in builtins:
            try:
                cfg = tt._load_tts_config() or {}
            except Exception:  # noqa: BLE001
                cfg = {}
            _run_builtin(tt, tier, text, output_path, cfg)
            return
        # Plugin tier (e.g. qwen3-tts): resolve from the TTS registry.
        from agent import tts_registry

        provider = tts_registry.get_provider(tier)
        if provider is None:
            raise RuntimeError(f"TTS plugin '{tier}' is not registered")
        provider.synthesize(
            text, output_path, voice=voice, model=model, speed=speed, format=fmt
        )

    def synthesize(
        self,
        text: str,
        output_path: str,
        *,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        speed: Optional[float] = None,
        format: str = "mp3",
        **extra: Any,
    ) -> str:
        attempts: List[str] = []
        for tier in _get_chain():
            # Clear any partial output a previous failed tier may have left.
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
            try:
                self._run_tier(tier, text, output_path, voice, model, speed, format)
            except Exception as exc:  # noqa: BLE001 — try the next tier
                logger.warning("tts-fallback: %s failed: %s", tier, exc)
                attempts.append(f"{tier}: {exc}")
                continue
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info("tts-fallback: synthesized via %s", tier)
                return output_path
            attempts.append(f"{tier}: produced no audio")

        raise RuntimeError("all TTS backends failed -> " + " | ".join(attempts))


def register(ctx) -> None:
    """Plugin entry point — register the fallback-chain TTS provider."""
    ctx.register_tts_provider(FallbackTTSProvider())
