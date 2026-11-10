#!/usr/bin/env python3
"""external-plugins — pin and install the third-party Hermes plugins the runtime fetches itself.

``external-plugins.json`` lists each third-party plugin by name with its GitHub ``repo``, the
released ``version``, the full ``commit`` that release was cut at, the ``skills`` it ships (the
profile validator accepts a ``skill_view`` naming them), the dotconfig plugins it ``requires``
(the validator refuses a profile that enables it without them) and, when OpenCode loads the same
release from npm, the ``npm`` package. install.sh cannot link these: their source is not in this
repository, so the runtime's own installer clones them at the pinned commit into
``<HERMES_HOME>/plugins/<name>`` (keeping ``.git``) and records the pin under the plugin's name in
``<HERMES_HOME>/plugins/.install-metadata.json``.

  * ``status``  — print one line per plugin: ``ok``, ``missing``, ``unpinned`` (the metadata holds
    no pinned revision) or ``differs (installed <short>, pinned <short>)``; exit 0 only when all
    are ok. Read-only.
  * ``install [name ...]`` — run ``hermes plugins install <repo> --ref <commit> --force --no-deps
    --no-enable`` for every plugin (or the named ones) that is not ok, then re-check. ``--force``
    replaces the directory and accepts the scan's "caution" verdict (a prebuilt bundle over 1 MB).
    Refused (exit 2) unless this script runs from the live checkout, never a task worktree.

Both commands take ``--hermes-home`` (default ``$HERMES_HOME`` or ``~/.hermes``). The npm version
must match the pinned ``version`` in ``opencode/opencode.jsonc``: both sides share one account
state, so a test checks it.

Run on ``hermes-python``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

MANIFEST = Path(__file__).resolve().parent / "external-plugins.json"
METADATA_FILE = ".install-metadata.json"
LIVE_CHECKOUT = Path("~/.config/hermes")
SHORT_SHA = 7
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIRED_KEYS = ("repo", "version", "commit")

OK = "ok"
MISSING = "missing"
UNPINNED = "unpinned"
EXIT_NOT_LIVE = 2


class ManifestError(ValueError):
    pass


def validate_manifest(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict) or not data:
        raise ManifestError("manifest must be a non-empty object")
    for name, entry in data.items():
        if not NAME_RE.match(name):
            raise ManifestError(f"{name}: bad plugin name")
        if not isinstance(entry, dict):
            raise ManifestError(f"{name}: entry must be an object")
        for key in REQUIRED_KEYS:
            if not isinstance(entry.get(key), str):
                raise ManifestError(f"{name}: missing {key}")
        if not REPO_RE.match(entry["repo"]):
            raise ManifestError(f"{name}: repo must be owner/name")
        if not VERSION_RE.match(entry["version"]):
            raise ManifestError(f"{name}: version must be N.N.N")
        if not COMMIT_RE.match(entry["commit"]):
            raise ManifestError(f"{name}: commit must be 40 lowercase hex")
        npm = entry.get("npm")
        if npm is not None and not (isinstance(npm, str) and npm.startswith("@")):
            raise ManifestError(f"{name}: npm must be a scoped package name")
        for key in ("skills", "requires"):
            names = entry.get(key, [])
            if not (isinstance(names, list) and all(isinstance(n, str) and NAME_RE.match(n) for n in names)):
                raise ManifestError(f"{name}: {key} must be a list of names")
    return data


def load_manifest(path: Path = MANIFEST) -> dict[str, dict[str, Any]]:
    return validate_manifest(json.loads(path.read_text(encoding="utf-8")))


def default_hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or "~/.hermes").expanduser()


def read_metadata(hermes_home: Path) -> dict[str, Any]:
    try:
        data = json.loads((hermes_home / "plugins" / METADATA_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def git_head(plugin_dir: Path) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(plugin_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def compute_status(entry: dict[str, Any], record: Any, head: Optional[str]) -> str:
    """Status of one plugin from its metadata record and the installed checkout's HEAD."""
    if head is None:
        return MISSING
    if not isinstance(record, dict) or not record.get("pinned") or not record.get("revision"):
        return UNPINNED
    pinned = entry["commit"]
    if record["revision"] != pinned or head != pinned:
        installed = head if head != pinned else record["revision"]
        return f"differs (installed {installed[:SHORT_SHA]}, pinned {pinned[:SHORT_SHA]})"
    return OK


def collect_status(
    manifest: dict[str, dict[str, Any]],
    hermes_home: Path,
    head_reader: Callable[[Path], Optional[str]] = git_head,
) -> dict[str, str]:
    metadata = read_metadata(hermes_home)
    return {
        name: compute_status(entry, metadata.get(name), head_reader(hermes_home / "plugins" / name))
        for name, entry in manifest.items()
    }


def is_live_checkout(script: Path, live: Path = LIVE_CHECKOUT) -> bool:
    """True when ``script`` lives under the live checkout (``~/.config/hermes``), not a worktree."""
    root = Path(os.path.realpath(live.expanduser()))
    return Path(os.path.realpath(script)).is_relative_to(root)


def install_command(entry: dict[str, Any]) -> list[str]:
    return ["hermes", "plugins", "install", entry["repo"], "--ref", entry["commit"],
            "--force", "--no-deps", "--no-enable"]


def print_status(statuses: dict[str, str]) -> bool:
    for name, status in statuses.items():
        print(f"{name}: {status}")
    return all(status == OK for status in statuses.values())


def cmd_status(manifest: dict[str, dict[str, Any]], hermes_home: Path) -> int:
    return 0 if print_status(collect_status(manifest, hermes_home)) else 1


def cmd_install(manifest: dict[str, dict[str, Any]], hermes_home: Path, names: list[str]) -> int:
    unknown = [n for n in names if n not in manifest]
    if unknown:
        print(f"unknown plugin: {', '.join(unknown)}", file=sys.stderr)
        return 1
    if not is_live_checkout(Path(__file__)):
        print("install runs from the live checkout (~/.config/hermes) only, not a task worktree",
              file=sys.stderr)
        return EXIT_NOT_LIVE
    selected = {n: manifest[n] for n in (names or manifest)}
    env = {**os.environ, "HERMES_HOME": str(hermes_home)}
    for name, status in collect_status(selected, hermes_home).items():
        if status == OK:
            continue
        print(f"{name}: {status}; installing")
        result = subprocess.run(install_command(selected[name]), env=env)
        if result.returncode != 0:
            print(f"{name}: hermes plugins install exited {result.returncode}", file=sys.stderr)
    return 0 if print_status(collect_status(selected, hermes_home)) else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hermes-home", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="report each plugin against its pin")
    install = sub.add_parser("install", help="install the plugins that are not ok")
    install.add_argument("names", nargs="*")
    args = parser.parse_args(argv)
    hermes_home = (args.hermes_home or default_hermes_home()).expanduser()
    try:
        manifest = load_manifest()
    except (OSError, ValueError) as exc:
        print(f"manifest: {exc}", file=sys.stderr)
        return 1
    if args.command == "status":
        return cmd_status(manifest, hermes_home)
    return cmd_install(manifest, hermes_home, args.names)


if __name__ == "__main__":
    sys.exit(main())
