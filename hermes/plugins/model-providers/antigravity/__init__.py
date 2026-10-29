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

USAGE_TITLE = "Antigravity quota"
USAGE_SOURCE = "fetch_available_models"
VERIFICATION_REQUIRED = "VALIDATION_REQUIRED"
VERIFICATION_MESSAGE = ("Google asks to verify this account before it serves Antigravity again; "
                        "complete the check in a browser signed in to it")
NO_QUOTA_MESSAGE = "Antigravity reported no quota for this account's models"


def _reset_at(value: str) -> Any:
    from datetime import datetime, timezone

    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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

    def fetch_account_usage(self, *, base_url: str | None = None, api_key: str | None = None) -> Any:
        """``/usage``: one line per quota the account's models share, with its reset time."""
        from datetime import datetime, timezone

        from agent.account_usage import AccountUsageSnapshot, AccountUsageWindow

        from .client import _origin

        token = str(api_key or "").strip()
        if not token:
            from hermes_cli.runtime_provider import resolve_runtime_provider

            token = str(resolve_runtime_provider(requested=self.name, explicit_base_url=base_url).get("api_key") or "")
        if not token:
            return None
        fetched_at = datetime.now(timezone.utc)
        try:
            groups = control.fetch_quota(token, _origin(base_url))
        except control.ControlError as exc:
            if exc.reason != VERIFICATION_REQUIRED:
                raise
            return AccountUsageSnapshot(provider=self.name, source=USAGE_SOURCE, fetched_at=fetched_at,
                                        title=USAGE_TITLE, unavailable_reason=VERIFICATION_MESSAGE)
        windows = tuple(
            AccountUsageWindow(label=group["label"], used_percent=round((1.0 - group["remaining"]) * 100.0, 2),
                               reset_at=_reset_at(group["reset"]), scope="model")
            for group in groups)
        return AccountUsageSnapshot(provider=self.name, source=USAGE_SOURCE, fetched_at=fetched_at,
                                    title=USAGE_TITLE, windows=windows,
                                    unavailable_reason=None if windows else NO_QUOTA_MESSAGE)

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
