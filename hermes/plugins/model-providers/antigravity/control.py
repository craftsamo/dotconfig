"""Antigravity's control plane: client version, project discovery, the model catalog and quota.

Each account's Cloud Code project is found once at login and stored on its pool row; a token
whose row cannot be read here (another profile's copy, a row added elsewhere) is discovered again
and kept in memory for the process.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from typing import Any

import httpx

from . import wire

logger = logging.getLogger(__name__)

PROVIDER = "antigravity"
PROJECT_KEY = "antigravity_project"
EMAIL_KEY = "antigravity_email"
FALLBACK_PROJECT = "rising-fact-p41fc"

HUB_MANIFEST_URL = (
    "https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/manifest/latest-arm64-mac.yml"
)
HUB_VERSION_FALLBACK = "2.24.0"
_HUB_VERSION_FLOOR = (2, 23, 0)
HUB_CHANGELISTS = {"2.23.0": "998057262", "2.23.1": "998881661", "2.24.0": "1000335682"}
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
GOOGLE_API_UA = "google-api-nodejs-client/9.15.1"

_lock = threading.Lock()
_hub_version: str | None = None
_projects: dict[str, str] = {}
_catalog: dict[str, dict[str, Any]] = {}
_catalog_fetched_at = 0.0


# ── Client version ──────────────────────────────────────────────────────────


def _manifest_version(text: str) -> str:
    for line in text.splitlines()[:40]:
        key, _, value = line.partition(":")
        if key.strip() == "version":
            version = value.strip().strip("'\"")
            match = _SEMVER.match(version)
            if match and tuple(int(g) for g in match.groups()) >= _HUB_VERSION_FLOOR:
                return version
    return ""


def hub_version(fetch: bool = True) -> str:
    """The current Antigravity release, read once per process (the fallback when unreachable)."""
    global _hub_version
    with _lock:
        if _hub_version is None:
            version = ""
            if fetch:
                try:
                    response = httpx.get(HUB_MANIFEST_URL, timeout=5.0,
                                         headers={"User-Agent": "electron-builder", "Cache-Control": "no-cache"})
                    if response.status_code == 200:
                        version = _manifest_version(response.text[:4096])
                except httpx.HTTPError as exc:
                    logger.debug("antigravity: release manifest unreachable: %s", exc)
            _hub_version = version or HUB_VERSION_FALLBACK
        return _hub_version


def user_agent() -> str:
    version = hub_version()
    return wire.hub_user_agent(version, HUB_CHANGELISTS.get(version, ""))


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "User-Agent": user_agent()}


class ControlError(RuntimeError):
    """A control-plane call refused: its HTTP status and Google's ``ErrorInfo`` reason, if any."""

    def __init__(self, method: str, status: int, reason: str = "") -> None:
        super().__init__(f"Antigravity {method} returned HTTP {status}" + (f" ({reason})" if reason else ""))
        self.status = status
        self.reason = reason


def _post(base_url: str, method: str, access_token: str, body: dict[str, Any], *, timeout: float,
          headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = httpx.post(f"{base_url.rstrip('/')}/v1internal:{method}", json=body,
                          headers=headers or _headers(access_token), timeout=timeout)
    if response.status_code != 200:
        raise ControlError(method, response.status_code, wire.error_reason(response.text))
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


# ── Account ─────────────────────────────────────────────────────────────────


def email(access_token: str) -> str:
    try:
        response = httpx.get(USERINFO_URL, timeout=10.0,
                             headers={"Authorization": f"Bearer {access_token}", "User-Agent": GOOGLE_API_UA})
        if response.status_code == 200:
            return str(response.json().get("email") or "")
    except (httpx.HTTPError, ValueError):
        pass
    return ""


def _project_of(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("id")
    return str(value or "").strip()


def _tier(payload: dict[str, Any]) -> str:
    tiers = [t for t in payload.get("allowedTiers") or [] if isinstance(t, dict) and t.get("id")]
    default = next((t["id"] for t in tiers if t.get("isDefault")), "")
    current = (payload.get("currentTier") or {}).get("id") if isinstance(payload.get("currentTier"), dict) else ""
    return default or (tiers[0]["id"] if tiers else "") or current or "free-tier"


def discover_project(access_token: str, base_url: str = wire.DAILY_ENDPOINT, *, sleep=time.sleep) -> str:
    """``loadCodeAssist``, then ``onboardUser`` when no project is assigned yet, else the fallback."""
    try:
        loaded = _post(base_url, "loadCodeAssist", access_token, {"metadata": {"ideType": "ANTIGRAVITY"}}, timeout=10.0)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("antigravity: loadCodeAssist failed: %s", exc)
        return FALLBACK_PROJECT
    if project := _project_of(loaded.get("cloudaicompanionProject")):
        return project
    version = hub_version()
    body = {"tier_id": _tier(loaded),
            "metadata": {"ide_type": "ANTIGRAVITY", "ide_version": version, "ide_name": "antigravity"}}
    headers = {**_headers(access_token), "Accept": "*/*",
               "User-Agent": f"{user_agent()} google-api-nodejs-client/10.3.0", "X-Goog-Api-Client": "gl-node/22.21.1"}
    for attempt in range(10):
        try:
            onboarded = _post(base_url, "onboardUser", access_token, body, timeout=30.0, headers=headers)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("antigravity: onboardUser failed: %s", exc)
            break
        if onboarded.get("done"):
            return _project_of((onboarded.get("response") or {}).get("cloudaicompanionProject")) or FALLBACK_PROJECT
        if attempt < 9:
            sleep(5.0)
    return FALLBACK_PROJECT


def _token_key(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def _pooled_project(access_token: str) -> str:
    try:
        from hermes_cli.auth import read_credential_pool
        rows = read_credential_pool(PROVIDER)
    except Exception:
        return ""
    for row in rows if isinstance(rows, list) else []:
        token = str((row or {}).get("access_token") or "")
        if token and hmac.compare_digest(token, access_token):
            return str(row.get(PROJECT_KEY) or "")
    return ""


def remember_project(access_token: str, project: str) -> None:
    with _lock:
        _projects[_token_key(access_token)] = project


def project_for(access_token: str, base_url: str = wire.DAILY_ENDPOINT) -> str:
    key = _token_key(access_token)
    with _lock:
        if key in _projects:
            return _projects[key]
    project = _pooled_project(access_token) or discover_project(access_token, base_url)
    with _lock:
        _projects[key] = project
    return project


# ── Catalog ─────────────────────────────────────────────────────────────────
#
# The account's model list, kept on disk under the profile's home so a new process (and the
# model picker, which reads the profile's ``fallback_models``) knows the models and their limits
# without a request. A request refreshes it in the background once it is an hour old, and so
# does a quota read, which comes from the same reply.

CATALOG_MAX_AGE = 3600.0
_refreshing = threading.Event()


def _catalog_path():
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "cache" / "antigravity" / "catalog.json"


def _remember(catalog: list[dict[str, Any]], fetched_at: float) -> None:
    global _catalog_fetched_at
    with _lock:
        _catalog.clear()
        _catalog.update({entry["id"]: entry for entry in catalog})
        _catalog_fetched_at = fetched_at


def _load_cached() -> None:
    if _catalog:
        return
    try:
        saved = json.loads(_catalog_path().read_text(encoding="utf-8"))
        entries = [e for e in saved.get("models") or [] if isinstance(e, dict) and e.get("id")]
        _remember(entries, float(saved.get("fetched_at") or 0.0))
    except Exception:
        return


def _available_models(access_token: str, base_url: str, timeout: float) -> dict[str, Any]:
    project = project_for(access_token, base_url)
    return _post(base_url, "fetchAvailableModels", access_token, {"project": project} if project else {}, timeout=timeout)


def fetch_catalog(access_token: str, base_url: str = wire.DAILY_ENDPOINT, *, timeout: float = 10.0) -> list[dict[str, Any]]:
    catalog = wire.parse_catalog(_available_models(access_token, base_url, timeout))
    if catalog:
        _save_catalog(catalog)
    return catalog


def fetch_quota(access_token: str, base_url: str = wire.DAILY_ENDPOINT, *, timeout: float = 8.0) -> list[dict[str, Any]]:
    """The account's quota groups (``wire.quota_groups``); the same reply refreshes the saved catalog."""
    payload = _available_models(access_token, base_url, timeout)
    if catalog := wire.parse_catalog(payload):
        _save_catalog(catalog)
    return wire.quota_groups(payload)


def _save_catalog(catalog: list[dict[str, Any]]) -> None:
    fetched_at = time.time()
    _remember(catalog, fetched_at)
    try:
        path = _catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # A usage read and a request may save at once; each writer gets its own temporary file.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at, "models": catalog}), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.debug("antigravity: catalog not saved: %s", exc)


def refresh_in_background(access_token: str, base_url: str = wire.DAILY_ENDPOINT) -> None:
    """Start one background refresh when the saved catalog is missing or an hour old."""
    _load_cached()
    with _lock:
        fresh = _catalog and time.time() - _catalog_fetched_at < CATALOG_MAX_AGE
    if fresh or _refreshing.is_set():
        return
    _refreshing.set()

    def run() -> None:
        try:
            fetch_catalog(access_token, base_url)
        except Exception as exc:
            logger.debug("antigravity: catalog refresh failed: %s", exc)
        finally:
            _refreshing.clear()

    threading.Thread(target=run, name="antigravity-catalog", daemon=True).start()


def model_ids() -> list[str]:
    _load_cached()
    with _lock:
        return list(_catalog)


def known(model: str) -> dict[str, Any] | None:
    _load_cached()
    with _lock:
        return _catalog.get(model)


def limits(model: str) -> tuple[int, int]:
    """``(context, output)`` from the account's catalog, else the family's usual values."""
    if entry := known(model):
        return entry["context"], entry["output"]
    if (model or "").lower().startswith("gemini-"):
        return 1048576, 65536
    return 200000, 64000
