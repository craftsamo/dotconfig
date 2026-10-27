"""Profile configuration for the OpenCode 2 plugin: `opencode` in config.yaml.

Nothing here is secret or per-run. Roles are data: a role names an installed
OpenCode agent, one of two policies, and optionally a model, an alternate model,
whether the caller's own model is allowed, a short note and a progress-line emoji.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

import hermes_yaml as yaml

KEY = "opencode"
# Where `opencode_session workspace` puts a task branch's worktree: <root>/<repo>/<branch>.
DEFAULT_WORKTREE_ROOT = "~/Worktrees"
# Source checkouts every run may read (never edit) without a round trip to the
# caller; the worktree root is added to them. Credentials live outside them.
DEFAULT_READ_ROOTS = ("~/ghq",)
POLICIES = ("read-only", "write")
# Whether a role may run on the caller's own model. `refuse` keeps the caller from
# judging or building what it then accepts itself; `allow` is a maintainer's choice.
CALLER_MODEL_MODES = ("refuse", "allow")
DEFAULT_ROLES = {
    "plan": {"agent": "plan", "policy": "read-only", "emoji": "📝"},
    "review": {"agent": "review", "policy": "read-only", "emoji": "👀"},
    "debug": {"agent": "debug", "policy": "read-only", "emoji": "🐛"},
    "build": {"agent": "build", "policy": "write", "emoji": "🔨"},
}
# The progress-line emoji of a role that names none of its own.
POLICY_EMOJI = {"read-only": "👀", "write": "🔨"}
EMOJI_LIMIT = 16
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
    if not isinstance(raw, dict) or set(raw) - {"agent", "policy", "model", "alternate", "caller_model", "note",
                                                 "emoji"}:
        raise ValueError(f"{KEY}.roles.{name} takes agent, policy, model, alternate, caller_model, note and "
                         "emoji only")
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
    if raw.get("alternate") is not None:
        if not pinned(raw["alternate"]):
            raise ValueError(f"{KEY}.roles.{name}.alternate must be provider/model or provider/model#variant")
        role["alternate"] = raw["alternate"]
    if raw.get("caller_model") is not None:
        if raw["caller_model"] not in CALLER_MODEL_MODES:
            raise ValueError(f"{KEY}.roles.{name}.caller_model must be one of {', '.join(CALLER_MODEL_MODES)}")
        role["caller_model"] = raw["caller_model"]
    note = raw.get("note")
    if note is not None:
        if not isinstance(note, str) or len(note) > NOTE_LIMIT:
            raise ValueError(f"{KEY}.roles.{name}.note must be text of at most {NOTE_LIMIT} characters")
        role["note"] = note
    emoji = raw.get("emoji")
    if emoji is not None:
        if not isinstance(emoji, str) or not 0 < len(emoji) <= EMOJI_LIMIT or any(c.isspace() for c in emoji):
            raise ValueError(f"{KEY}.roles.{name}.emoji must be a short symbol without spaces")
        role["emoji"] = emoji
    return role


def emoji(role):
    """The progress-line emoji of a role: its own, else its policy's."""
    return role.get("emoji") or POLICY_EMOJI[role["policy"]]


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
    unknown = set(config) - {"enabled", "wait_timeout", "allowed_providers", "roles", "worktree_root", "read_roots"}
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
    for name, role in configured.items():
        # A rerun on the alternate goes through the same provider allowlist as any model=.
        if role.get("alternate") and role["alternate"].split("/", 1)[0] not in providers:
            raise ValueError(f"{KEY}.roles.{name}.alternate is not from {KEY}.allowed_providers")
    root = config.get("worktree_root", DEFAULT_WORKTREE_ROOT)
    if not _directory(root):
        raise ValueError(f"{KEY}.worktree_root must be an absolute path (or start with ~/) without wildcards")
    reads = config.get("read_roots", list(DEFAULT_READ_ROOTS))
    if not isinstance(reads, list) or not all(_directory(v) for v in reads):
        raise ValueError(f"{KEY}.read_roots must be a list of absolute paths (or ~/…) without wildcards")
    worktree_root = str(Path(root).expanduser())
    read_roots = []
    home = Path.home()
    above = {home, *home.parents, home.resolve(), *home.resolve().parents}
    for value in [*reads, worktree_root]:
        path = Path(os.path.normpath(Path(value).expanduser()))
        # A root holding the home directory would open every credential store in it; the
        # ruleset also allows the resolved spelling, so a link to the home is refused too.
        if path in above or path.resolve() in above:
            raise ValueError(f"{KEY}.read_roots: {value} must lie below the home directory or elsewhere, "
                             "never the home directory itself or above it")
        if str(path) not in read_roots:
            read_roots.append(str(path))
    return {"wait_timeout": wait, "allowed_providers": providers, "roles": configured,
            "worktree_root": worktree_root, "read_roots": read_roots}


def _directory(value):
    return isinstance(value, str) and value.startswith(("/", "~/")) and not any(c in value for c in "*?")
