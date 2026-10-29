"""Google OAuth for Antigravity: ``hermes auth add|status|logout antigravity`` and token refresh.

The login is Hermes' own loopback PKCE flow, except for the redirect: the Antigravity client is
registered for ``http://localhost:51121/oauth-callback`` exactly, so the listener binds 127.0.0.1
on that port and the URI names ``localhost``. Google also wants the client secret on every token
request. It is a public value shipped inside the Antigravity client, but it is still read from
the ``ANTIGRAVITY_OAUTH_CLIENT_SECRET`` Keychain item rather than kept in the repository.
"""

from __future__ import annotations

import hmac
import os
import secrets
import uuid
import webbrowser
from typing import Any, Mapping
from urllib.parse import urlencode

from . import control

CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET_ENV = "ANTIGRAVITY_OAUTH_CLIENT_SECRET"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
)
REDIRECT_PORT = 51121
REDIRECT_PATH = "/oauth-callback"
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}{REDIRECT_PATH}"
LABEL = "Google Antigravity"
TIMEOUT_SECONDS = 300.0


def _error(message: str, code: str):
    from hermes_cli.auth_constants import AuthError

    return AuthError(f"{control.PROVIDER}: {message}", provider=control.PROVIDER, code=code)


def config(*, require_secret: bool = True):
    from hermes_cli.auth_oauth_pkce_plugin import OAuthPKCEConfig

    client_secret = (os.environ.get(CLIENT_SECRET_ENV) or "").strip()
    if require_secret and not client_secret:
        raise _error(
            f"{CLIENT_SECRET_ENV} is not set. Store it in the Keychain project `hermes` "
            f"(`secret set {CLIENT_SECRET_ENV} -p hermes`) and start Hermes again.",
            "oauth_client_secret_missing",
        )
    return OAuthPKCEConfig(
        client_id=CLIENT_ID, authorize_url=AUTHORIZE_URL, token_url=TOKEN_URL, scopes=SCOPES,
        redirect_port=REDIRECT_PORT, redirect_path=REDIRECT_PATH,
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
        extra_token_params={"client_secret": client_secret} if client_secret else {},
        allowed_hosts=("accounts.google.com", "oauth2.googleapis.com"),
        timeout_seconds=TIMEOUT_SECONDS, label=LABEL,
    )


def authorize_url(state: str, challenge: str) -> str:
    params = {
        "client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": " ".join(SCOPES),
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
        "access_type": "offline", "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def login(*, open_browser: bool = True) -> dict[str, Any]:
    """Browser login; returns the pool fields plus the account's email and Cloud Code project."""
    from hermes_cli.auth_device_flow import (
        _bind_loopback_callback_server, _can_open_graphical_browser, _make_loopback_callback_handler,
        _pkce_code_challenge, _pkce_code_verifier, _print_loopback_ssh_hint, _serve_loopback_callback)
    from hermes_cli.auth_oauth_pkce_plugin import _post_token, validate_config

    cfg = config()
    validate_config(control.PROVIDER, cfg)
    handler_cls, result = _make_loopback_callback_handler(REDIRECT_PATH, display_name=LABEL)
    server = _bind_loopback_callback_server("127.0.0.1", REDIRECT_PORT, handler_cls, err=_error,
                                            bind_failed_code="oauth_callback_bind_failed")
    verifier = _pkce_code_verifier()
    state = secrets.token_urlsafe(32)
    url = authorize_url(state, _pkce_code_challenge(verifier))
    print(f"\nOpen this URL to sign in to {LABEL}:\n  {url}\n")
    print(f"Waiting for the callback on {REDIRECT_URI} (timeout {int(TIMEOUT_SECONDS)}s, Ctrl+C to cancel)...")
    _print_loopback_ssh_hint(REDIRECT_URI)
    if open_browser and _can_open_graphical_browser():
        try:
            webbrowser.open(url)
        except Exception:
            print("Could not open the browser automatically; use the URL above.")
    try:
        callback = _serve_loopback_callback(server, result, timeout_seconds=TIMEOUT_SECONDS, err=_error,
                                            timeout_code="oauth_callback_timeout")
    except KeyboardInterrupt:
        print("\nLogin cancelled.")
        raise SystemExit(130)
    if callback.get("error"):
        raise _error(f"authorization failed: {callback.get('error_description') or callback['error']}",
                     "oauth_authorization_denied")
    if not hmac.compare_digest(str(callback.get("state") or ""), state):
        raise _error("callback state mismatch: the redirect did not come from this login.", "oauth_state_mismatch")
    code = str(callback.get("code") or "").strip()
    if not code:
        raise _error("callback carried no authorization code.", "oauth_no_code")
    tokens = _post_token(control.PROVIDER, cfg, {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
    }, code="oauth_token_exchange_failed")
    if not tokens.get("refresh_token"):
        raise _error("Google returned no refresh token; sign in again.", "oauth_no_refresh_token")
    access = tokens["access_token"]
    project = control.discover_project(access)
    control.remember_project(access, project)
    try:
        models = control.fetch_catalog(access)
        print(f"{len(models)} models available to this account.")
    except Exception as exc:  # the catalog is refreshed again on the first request
        print(f"Could not read the model list yet ({type(exc).__name__}).")
    return {**tokens, "email": control.email(access), "project": project}


def auth_handler(action: str, args: Any) -> bool:
    """``hermes auth add`` signs in and adds a pool row; status and logout are Hermes' PKCE ones."""
    from agent.credential_pool import AUTH_TYPE_OAUTH, PooledCredential, load_pool
    from hermes_cli.auth_oauth_pkce_plugin import POOL_SOURCE, pkce_auth_handler

    if action != "add":
        return pkce_auth_handler(config(require_secret=False))(action, args)
    signed_in = login(open_browser=not getattr(args, "no_browser", False))
    account, project = signed_in.pop("email"), signed_in.pop("project")
    label = str(getattr(args, "label", "") or "").strip() or account or LABEL
    entry = load_pool(control.PROVIDER).add_entry(PooledCredential(
        provider=control.PROVIDER, id=uuid.uuid4().hex[:6], label=label, auth_type=AUTH_TYPE_OAUTH, priority=0,
        source=POOL_SOURCE, **signed_in,
        extra={"oauth_pkce": {"client_id": CLIENT_ID, "scope": " ".join(SCOPES)},
               control.PROJECT_KEY: project, control.EMAIL_KEY: account},
    ))
    print(f"Signed in to {LABEL} as {account or 'an unknown account'} (project {project}); "
          f"credential {entry.id} added to the pool.")
    return True


def refresh_credential(entry: Any) -> Mapping[str, Any]:
    from hermes_cli.auth_oauth_pkce_plugin import pkce_refresh_credential

    return pkce_refresh_credential(config())(entry)
