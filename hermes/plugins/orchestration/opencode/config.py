"""Profile configuration for the OpenCode 2 plugin: `opencode` in config.yaml.

Nothing here is secret or per-run. Roles are data: a role names an installed
OpenCode agent, one of two policies, and optionally a model and a short note.
"""

from __future__ import annotations

import re

import hermes_yaml as yaml

KEY = "opencode"
POLICIES = ("read-only", "write")
DEFAULT_ROLES = {
    "plan": {"agent": "plan", "policy": "read-only"},
    "review": {"agent": "review", "policy": "read-only"},
    "debug": {"agent": "debug", "policy": "read-only"},
    "build": {"agent": "build", "policy": "write"},
}
DEFAULT_WAIT_TIMEOUT = 3300
MAX_WAIT_TIMEOUT = 5400
ROLE_NAME = re.compile(r"[a-z][a-z0-9_]{0,23}\Z")
AGENT_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
MODEL_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.:/-]+\Z")
VARIANT_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
PROVIDER_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
NOTE_LIMIT = 2000


def read(home):
    """The profile's config.yaml, read directly: upstream may rewrite it on load."""
    return yaml.safe_load((home / "config.yaml").read_text()) or {}


def pinned(value):
    """`provider/model[#variant]` as (model, variant), or None when malformed."""
    if not isinstance(value, str):
        return None
    model, _, variant = value.partition("#")
    if not MODEL_NAME.fullmatch(model) or ("#" in value and not VARIANT_NAME.fullmatch(variant)):
        return None
    return model, variant or None


def _role(name, raw):
    if not ROLE_NAME.fullmatch(name):
        raise ValueError(f"{KEY}.roles: {name!r} is not a role name (lowercase letters, digits, _)")
    if not isinstance(raw, dict) or set(raw) - {"agent", "policy", "model", "note"}:
        raise ValueError(f"{KEY}.roles.{name} takes agent, policy, model and note only")
    agent, policy = raw.get("agent"), raw.get("policy")
    if not isinstance(agent, str) or not AGENT_NAME.fullmatch(agent):
        raise ValueError(f"{KEY}.roles.{name}.agent must be an OpenCode agent name")
    if policy not in POLICIES:
        raise ValueError(f"{KEY}.roles.{name}.policy must be one of {', '.join(POLICIES)}")
    role = {"agent": agent, "policy": policy}
    if raw.get("model") is not None:
        if not pinned(raw["model"]):
            raise ValueError(f"{KEY}.roles.{name}.model must be provider/model or provider/model#variant")
        role["model"] = raw["model"]
    note = raw.get("note")
    if note is not None:
        if not isinstance(note, str) or len(note) > NOTE_LIMIT:
            raise ValueError(f"{KEY}.roles.{name}.note must be text of at most {NOTE_LIMIT} characters")
        role["note"] = note
    return role


def roles(home):
    """The configured roles; the four defaults when none are configured. Never raises:
    tools are registered from this, and a broken file must not unregister them."""
    try:
        raw = (read(home).get(KEY) or {}).get("roles")
        if raw is None:
            return {name: dict(role) for name, role in DEFAULT_ROLES.items()}
        return {name: _role(name, value) for name, value in raw.items()}
    except Exception:
        return {name: dict(role) for name, role in DEFAULT_ROLES.items()}


def load(home):
    """The validated configuration of an enabled integration. Raises ValueError otherwise."""
    config = read(home).get(KEY) or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        raise ValueError(f"OpenCode integration is not enabled ({KEY}.enabled)")
    unknown = set(config) - {"enabled", "wait_timeout", "allowed_providers", "roles"}
    if unknown:
        raise ValueError(f"{KEY}: unknown keys {', '.join(sorted(unknown))}")
    wait = config.get("wait_timeout", DEFAULT_WAIT_TIMEOUT)
    if type(wait) is not int or not 1 <= wait <= MAX_WAIT_TIMEOUT:
        raise ValueError(f"{KEY}.wait_timeout must be 1..{MAX_WAIT_TIMEOUT} seconds")
    providers = config.get("allowed_providers", [])
    if not isinstance(providers, list) or not all(isinstance(v, str) and PROVIDER_NAME.fullmatch(v)
                                                   for v in providers):
        raise ValueError(f"{KEY}.allowed_providers must be a list of provider names")
    raw = config.get("roles")
    configured = ({name: dict(role) for name, role in DEFAULT_ROLES.items()} if raw is None
                  else {name: _role(name, value) for name, value in raw.items()})
    if not configured:
        raise ValueError(f"{KEY}.roles must name at least one role")
    return {"wait_timeout": wait, "allowed_providers": providers, "roles": configured}
