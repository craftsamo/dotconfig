"""Image-generation fallback-chain provider plugin.

Registers one or more *virtual* image-gen backends, each of which wraps an
ordered list of real, already-registered providers (``openai-codex``, ``xai``,
``fal``). On each call it tries them in order and returns the first success,
falling through on unavailability, exception, or an error response (e.g. a
rate-limit / quota hit). This gives ``image_generate`` resilience the core tool
does not provide natively (the active provider is a single value with no
built-in failover).

Both chains are always registered ("prepare both patterns"); pick one per
profile via ``image_gen.provider`` in that profile's ``config.yaml``:

    image_gen:
      provider: img-xai-codex-fal      # or img-codex-xai
    plugins:
      enabled:
        - image-fallback

The real backends (``openai-codex``/``xai``/``fal``) are bundled and auto-load
for every profile, so the registry lookups below resolve at call time
regardless of ``plugins.enabled``. Credentials are inherited per profile
(Codex / xAI OAuth via the default profile's auth.json; ``FAL_KEY`` via the
Keychain shim), so no per-profile secret setup is needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent import image_gen_registry
from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
)

logger = logging.getLogger(__name__)


# Ordered fallback chains. Keys are the values you put in image_gen.provider.
_CHAINS: Dict[str, List[str]] = {
    "img-codex-xai": ["openai-codex", "xai"],
    "img-xai-codex-fal": ["xai", "openai-codex", "fal"],
}


class ChainProvider(ImageGenProvider):
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
                logger.warning("image-fallback chain %r references itself; skipping", self._name)
                continue
            provider = image_gen_registry.get_provider(member_name)
            if provider is None:
                logger.debug("image-fallback: chain member %r not registered", member_name)
                continue
            yield member_name, provider

    @staticmethod
    def _is_available_safe(provider: ImageGenProvider) -> bool:
        try:
            return bool(provider.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.debug("image-fallback: %s.is_available() raised %s", provider, exc)
            return False

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

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "free",
            "tag": "tries each backend in order; falls through on error/limit",
            "env_vars": [],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        aspect = resolve_aspect_ratio(aspect_ratio)
        errors: List[str] = []

        for member_name, provider in self._members():
            if not self._is_available_safe(provider):
                errors.append(f"{member_name}: unavailable (no credentials)")
                continue
            try:
                result = provider.generate(prompt, aspect_ratio=aspect, **kwargs)
            except Exception as exc:  # noqa: BLE001 — never raise out of generate
                logger.warning("image-fallback: %s raised %s", member_name, exc, exc_info=True)
                errors.append(f"{member_name}: {exc}")
                continue
            if isinstance(result, dict) and not result.get("success"):
                errors.append(f"{member_name}: {result.get('error')}")
                continue
            return result

        return error_response(
            error="All chained image backends failed: " + " | ".join(errors)
            if errors
            else "No image backends are registered for this chain",
            error_type="all_backends_failed",
            provider=self._name,
            prompt=prompt,
            aspect_ratio=aspect,
        )


def register(ctx) -> None:
    """Plugin entry point — register every configured fallback chain."""
    for name, chain in _CHAINS.items():
        ctx.register_image_gen_provider(ChainProvider(name, chain))
