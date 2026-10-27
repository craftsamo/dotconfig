"""manifestlib — what cron-sync and webhook-sync share: a ``<thing>.d/<name>/`` directory is the
tracked definition of one job or route, its name is the directory's, its source is how the
directory got into the profile home (a link into a repository, or a real directory the profile
wrote for itself), and the derived record carries a ``managed`` marker naming the manifest.

A script in such a directory is reached through a generated wrapper under the profile's
``scripts/`` (the runtime runs only scripts inside that directory, by real path); the wrapper
exports the owning profile's home as ``HERMES_HOME`` and execs the manifest's path under it, so
no checkout path is written anywhere.

Loaded by path from ``cron-sync.py`` and ``webhook-sync.py`` (``scripts/`` is not a package).
"""

from __future__ import annotations

import argparse
import os
import re
import stat
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

try:  # Hermes' own YAML reader (its runtime and test interpreter ship no PyYAML)
    import hermes_yaml as yaml
except ImportError:
    import yaml

MARKER = "managed"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ManifestError(ValueError):
    """A manifest that cannot become a record; the message names the manifest and the reason."""


def check_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ManifestError(f"{name}: directory name must match {NAME_RE.pattern}")


def read_spec(directory: Path, manifest_file: str) -> Any:
    """The YAML of ``<directory>/<manifest_file>``; a missing or unparsable file is a ManifestError
    naming the directory."""
    name = directory.name
    path = directory / manifest_file
    if not path.is_file():
        raise ManifestError(f"{name}: no {manifest_file}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestError(f"{name}: {manifest_file} is not valid YAML: {exc}") from exc


def source_of(directory: Path) -> str:
    """``repo`` when the directory is a link (the installer's, into a repository), else ``local``."""
    return "repo" if directory.is_symlink() else "local"


def executable_script(directory: Path, filename: str) -> Optional[Path]:
    """``<directory>/<filename>`` resolved, when present; a present but non-executable one is an
    error (Git tracks the bit, so a lost bit is a tracked mistake)."""
    script = directory / filename
    if not script.is_file():
        return None
    if not script.stat().st_mode & stat.S_IXUSR:
        raise ManifestError(f"{directory.name}: {filename} must be executable (chmod +x)")
    return script.resolve()


def iter_manifest_dirs(root: Path, kind: str) -> Iterator[tuple[Optional[Path], Optional[str]]]:
    """Every entry of ``root`` as ``(directory, None)`` or ``(None, error)``; dot-entries are
    skipped. ``kind`` names what an entry is, for the error text."""
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            yield None, f"{child.name}: not a directory (every entry of {root.name}/ is a {kind})"
            continue
        yield child, None


def text_field(value: Any, key: str, name: str) -> Optional[str]:
    """A string field, stripped; None when absent or blank. Anything else is a ManifestError."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"{name}: `{key}` must be a string")
    return value.strip() or None


def string_list(value: Any, key: str, name: str) -> Optional[list[str]]:
    """A list of non-empty strings, stripped; None when absent. ``[]`` is kept (an explicit
    empty list means something to some keys)."""
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(s, str) and s.strip() for s in value):
        raise ManifestError(f"{name}: `{key}` must be a list of non-empty strings")
    return [s.strip() for s in value]


def bool_field(value: Any, key: str, name: str) -> Optional[bool]:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ManifestError(f"{name}: `{key}` must be true or false")
    return value


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------

def wrapper_text(tool: str, manifest_dir: str, name: str, script: str) -> str:
    """The wrapper lives at ``<home>/scripts/<wrapper_dir>/<name>.sh``, so it is the one party
    that knows which profile owns the manifest: it names that home in ``HERMES_HOME`` for the
    script, whatever the gateway's own process environment says under multiplex, and reaches
    the script through the manifest's path under that home (a link for a repository entry), so
    a moved checkout needs only the installer's relink."""
    return (
        "#!/bin/sh\n"
        f"# Generated by {tool} from {manifest_dir}/{name}/{script} — do not edit.\n"
        'HERMES_HOME="$(cd "$(dirname "$0")/../.." && pwd)"\n'
        "export HERMES_HOME\n"
        f'exec "$HERMES_HOME/{manifest_dir}/{name}/{script}" "$@"\n'
    )


def sync_wrappers(home: Path, wrapper_dir: str, wanted: dict[str, str], write: bool) -> list[str]:
    """Write ``scripts/<wrapper_dir>/<filename>`` for every ``wanted`` entry and drop the ``.sh``
    files there that nothing wants any more. Returns the changes (made, or pending when not
    writing)."""
    changes: list[str] = []
    directory = home / "scripts" / wrapper_dir
    for filename, text in wanted.items():
        path = directory / filename
        if path.is_file() and path.read_text(encoding="utf-8") == text and path.stat().st_mode & stat.S_IXUSR:
            continue
        changes.append(f"wrapper {path.relative_to(home)}")
        if write:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
    if directory.is_dir():
        for path in sorted(directory.glob("*.sh")):
            if path.name in wanted:
                continue
            changes.append(f"drop wrapper {path.relative_to(home)}")
            if write:
                path.unlink()
    return changes


# ---------------------------------------------------------------------------
# Markers and the runtime
# ---------------------------------------------------------------------------

def marker(name: str, source: str, now: str) -> dict[str, str]:
    return {"manifest": name, "source": source, "synced_at": now}


def marker_of(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The record's ``managed`` marker when it has a well-formed one."""
    found = record.get(MARKER)
    return found if isinstance(found, dict) and found.get("manifest") else None


def with_home(home: Path, fn: Callable[[], Any]) -> Any:
    """Run ``fn()`` with the runtime's ``HERMES_HOME`` pointed at ``home``, without touching the
    process environment (the runtime's own override, read by everything that asks for the home)."""
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    token = set_hermes_home_override(home)
    try:
        return fn()
    finally:
        reset_hermes_home_override(token)


# ---------------------------------------------------------------------------
# Homes
# ---------------------------------------------------------------------------

def hermes_dir() -> Path:
    return Path(os.environ.get("HERMES_DIR") or "~/.hermes").expanduser()


def profile_homes(args: argparse.Namespace, manifest_dir: str) -> list[Path]:
    """The homes a command runs on: ``--home``, ``--profile``, or every profile with a
    ``<manifest_dir>/``."""
    if getattr(args, "home", None):
        return [Path(args.home)]
    if getattr(args, "profile", None):
        return [hermes_dir() / "profiles" / args.profile]
    root = hermes_dir() / "profiles"
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / manifest_dir).is_dir())


def add_scope_arguments(parser: argparse.ArgumentParser, manifest_dir: str) -> None:
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--profile", help=f"a profile under $HERMES_DIR/profiles (default: all with {manifest_dir}/)")
    scope.add_argument("--home", help="a HERMES_HOME directory")
