#!/usr/bin/env python3
"""claude-code-suppression — audit and fix Claude Code source suppression across profiles.

Hermes reads ``suppressed_sources`` only from the ``auth.json`` of the active
``HERMES_HOME``; the root suppression does not cascade to profile directories.
Without an explicit suppression of the ``claude_code`` source under ``anthropic-oauth``,
a profile may seed local Claude Code Keychain credentials into its own pool.
This script audits every home for the required suppression and optionally applies it.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


def _load_sibling(name: str, filename: str):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


lib = _load_sibling("hermes_manifestlib", "manifestlib.py")

PROVIDER = "anthropic-oauth"
SOURCE = "claude_code"


def discover_homes(root: Path) -> list[tuple[str, Path]]:
    """The root and every live named profile, decided as the runtime decides what it serves."""
    from hermes_constants import PROFILE_ID_RE, named_profile_has_identity, named_profile_is_deleted

    homes: list[tuple[str, Path]] = [("root", root)]
    profiles_dir = root / "profiles"
    if profiles_dir.is_dir():
        for child in sorted(profiles_dir.iterdir(), key=lambda p: p.name):
            if (
                child.is_dir()
                and child.name != "default"
                and PROFILE_ID_RE.match(child.name)
                and named_profile_has_identity(child)
                and not named_profile_is_deleted(child)
            ):
                homes.append((child.name, child))
    return homes


def is_suppressed(home: Path) -> bool:
    import hermes_cli.auth

    return bool(lib.with_home(home, lambda: hermes_cli.auth.is_source_suppressed(PROVIDER, SOURCE)))


def suppress(home: Path) -> None:
    import hermes_cli.auth

    lib.with_home(home, lambda: hermes_cli.auth.suppress_credential_source(PROVIDER, SOURCE))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", help="the root HERMES_HOME (default: $HERMES_DIR or ~/.hermes)")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="suppress claude_code for anthropic-oauth in homes missing it",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser() if args.root else lib.hermes_dir()

    homes = discover_homes(root)
    any_missing = False

    for name, home in homes:
        if is_suppressed(home):
            print(f"ok {name}")
        elif args.fix:
            suppress(home)
            if is_suppressed(home):
                print(f"fixed {name}")
            else:
                print(f"missing {name}")
                any_missing = True
        else:
            print(f"missing {name}")
            any_missing = True

    if any_missing:
        print(
            "Run with --fix and then restart the gateway with launchd/gateway-launchctl.sh restart",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
