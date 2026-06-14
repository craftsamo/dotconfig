"""Video-generation fallback-chain provider plugin.

Registers one or more *virtual* video-gen backends, each of which wraps an
ordered list of real, already-registered providers (``xai``, ``fal``). On each
call it tries them in order and returns the first success, falling through on
unavailability, exception, or an error response (e.g. a rate-limit / quota hit
or a missing subscription tier). This gives ``video_generate`` resilience the
core tool does not provide natively (the active provider is a single value with
no built-in failover).

Both chains are always registered ("prepare both patterns"); pick one per
profile via ``video_gen.provider`` in that profile's ``config.yaml``:

    video_gen:
      provider: vid-xai-fal      # or vid-fal-xai
    plugins:
      enabled:
        - video-fallback

The real backends (``xai``/``fal``) are bundled and auto-load for every profile,
so the registry lookups below resolve at call time regardless of
``plugins.enabled``. Credentials are inherited per profile (xAI Grok OAuth via
the default profile's auth.json — SuperGrok / Premium+ — or ``XAI_API_KEY``;
``FAL_KEY`` via the Keychain shim), so no per-profile secret setup is needed.

This mirrors the image-gen fallback plugin (``plugins/image_gen/image-fallback``)
so the two surfaces stay learnable together.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent import video_gen_registry
from agent.video_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
)

logger = logging.getLogger(__name__)


# Ordered fallback chains. Keys are the values you put in video_gen.provider.
#   vid-xai-fal : Grok Imagine first (OAuth/SuperGrok), FAL.ai as the safety net.
#   vid-fal-xai : FAL.ai first (FAL_KEY), Grok Imagine as the fallback.
_CHAINS: Dict[str, List[str]] = {
    "vid-xai-fal": ["xai", "fal"],
    "vid-fal-xai": ["fal", "xai"],
}


class ChainProvider(VideoGenProvider):
    """A virtual backend that dispatches to an ordered list of real backends."""

    def __init__(self, name: str, chain: List[str]) -> None:
        self._name = name
        self._chain = list(chain)

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return " \u2192 ".join(self._chain) + " (fallback)"

    def _members(self):
        """Yield (name, provider) for each resolvable, non-self chain member."""
        for member_name in self._chain:
            if member_name == self._name:
                # Guard against a chain that references itself -> infinite loop.
                logger.warning("video-fallback chain %r references itself; skipping", self._name)
                continue
            provider = video_gen_registry.get_provider(member_name)
            if provider is None:
                logger.debug("video-fallback: chain member %r not registered", member_name)
                continue
            yield member_name, provider

    @staticmethod
    def _is_available_safe(provider: VideoGenProvider) -> bool:
        try:
            return bool(provider.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.debug("video-fallback: %s.is_available() raised %s", provider, exc)
            return False

    def _first_available(self) -> Optional[VideoGenProvider]:
        for _, provider in self._members():
            if self._is_available_safe(provider):
                return provider
        return None

    def is_available(self) -> bool:
        return any(self._is_available_safe(p) for _, p in self._members())

    def list_models(self) -> List[Dict[str, Any]]:
        # Surface the first resolvable member's catalog for the `hermes tools` picker.
        for _, provider in self._members():
            try:
                models = provider.list_models()
            except Exception:  # noqa: BLE001
                continue
            if models:
                return models
        return []

    def default_model(self) -> Optional[str]:
        for _, provider in self._members():
            try:
                model = provider.default_model()
            except Exception:  # noqa: BLE001
                continue
            if model:
                return model
        return None

    def capabilities(self) -> Dict[str, Any]:
        # The video_generate tool rebuilds its description from the active
        # provider's capabilities at session start, so reflect the real backend
        # (modalities, aspect ratios, durations, audio) instead of the text-only
        # ABC default. Prefer the first *available* member; fall back to the
        # first resolvable one, then to the base default.
        provider = self._first_available()
        if provider is not None:
            try:
                return provider.capabilities()
            except Exception:  # noqa: BLE001
                pass
        for _, provider in self._members():
            try:
                return provider.capabilities()
            except Exception:  # noqa: BLE001
                continue
        return super().capabilities()

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "paid",
            "tag": "tries each backend in order; falls through on error/limit/tier",
            "env_vars": [],
        }

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        errors: List[str] = []

        for member_name, provider in self._members():
            if not self._is_available_safe(provider):
                errors.append(f"{member_name}: unavailable (no credentials)")
                continue
            try:
                result = provider.generate(
                    prompt,
                    model=model,
                    image_url=image_url,
                    reference_image_urls=reference_image_urls,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                    negative_prompt=negative_prompt,
                    audio=audio,
                    seed=seed,
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001 — never raise out of generate
                logger.warning("video-fallback: %s raised %s", member_name, exc, exc_info=True)
                errors.append(f"{member_name}: {exc}")
                continue
            if isinstance(result, dict) and not result.get("success"):
                errors.append(f"{member_name}: {result.get('error')}")
                continue
            return result

        return error_response(
            error="All chained video backends failed: " + " | ".join(errors)
            if errors
            else "No video backends are registered for this chain",
            error_type="all_backends_failed",
            provider=self._name,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )


def register(ctx) -> None:
    """Plugin entry point — register every configured fallback chain."""
    for name, chain in _CHAINS.items():
        ctx.register_video_gen_provider(ChainProvider(name, chain))
