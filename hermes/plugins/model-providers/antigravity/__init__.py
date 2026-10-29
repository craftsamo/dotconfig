"""Google Antigravity as a Hermes model provider (``antigravity``).

Gemini and Claude on a Google Antigravity plan, through a Google OAuth login whose rows sit in
Hermes' credential pool (``hermes auth add antigravity``, from the default profile). Requests go
straight to Antigravity's Cloud Code endpoint, as the OpenCode plugin does. Google's terms forbid
third-party clients on this login; see hermes/docs/models-auth.md before signing in.
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

from . import control, oauth, wire

FALLBACK_MODELS = (
    "gemini-3-flash",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gemini-3.8-flash-low",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-high",
)


class AntigravityProfile(ProviderProfile):
    # The model picker shows an OAuth provider's ``fallback_models`` without asking the
    # provider, so this answers with the account's saved catalog when there is one.
    @property
    def fallback_models(self) -> tuple:
        return tuple(control.model_ids()) or self._static_models

    @fallback_models.setter
    def fallback_models(self, value: tuple) -> None:
        self._static_models = tuple(value or ())

    def create_client(self, **client_kwargs: Any) -> Any:
        from .client import AntigravityClient

        return AntigravityClient(**client_kwargs)

    def build_extra_body(self, *, session_id: str | None = None, **context: Any) -> dict[str, Any]:
        config = wire.thinking_config(context.get("model") or "", context.get("reasoning_config"))
        return {"thinking_config": config} if config else {}

    def fetch_models(self, *, api_key: str | None = None, base_url: str | None = None,
                     timeout: float = 8.0) -> list[str] | None:
        if not api_key:
            return None
        try:
            return [m["id"] for m in control.fetch_catalog(api_key, timeout=timeout)] or None
        except Exception:
            return None

    def get_model_context_length(self, model: str) -> int | None:
        return control.limits(model)[0]

    def get_max_tokens(self, model: str | None) -> int | None:
        return control.limits(model or "")[1]


antigravity = AntigravityProfile(
    name=control.PROVIDER,
    aliases=("google-antigravity",),
    display_name="Google Antigravity",
    description="Gemini and Claude on a Google Antigravity plan (Google OAuth, unofficial client)",
    base_url=wire.DAILY_ENDPOINT,
    auth_type="oauth_external",
    hidden=True,
    supports_health_check=False,
    supports_vision=True,
    fallback_models=FALLBACK_MODELS,
    auth_handler=oauth.auth_handler,
    refresh_credential=oauth.refresh_credential,
)

register_provider(antigravity)
