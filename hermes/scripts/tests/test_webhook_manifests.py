"""The tracked webhook manifests: every profiles/<p>/webhook.d/<name>/ in this repository must
load through webhook-sync exactly as the installed link will, its filter must be executable in
Git (the wrapper execs it by path), and nothing in it may be a secret or a conversation.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
PROFILES = HERMES_ROOT / "profiles"
SCRIPT = HERMES_ROOT / "scripts" / "webhook-sync.py"
SPEC = importlib.util.spec_from_file_location("webhook_sync_manifests", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules["webhook_sync_manifests"] = S
SPEC.loader.exec_module(S)


def manifest_dirs() -> list[Path]:
    return sorted(d for d in PROFILES.glob(f"*/{S.MANIFEST_DIR}/*") if d.is_dir())


def test_every_tracked_manifest_loads():
    errors = []
    for profile in sorted(p for p in PROFILES.iterdir() if (p / S.MANIFEST_DIR).is_dir()):
        _routes, found = S.load_routes(profile, profile.name)
        errors.extend(found)
    assert errors == []


def test_filters_are_executable_in_git():
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", *(f"profiles/*/{S.MANIFEST_DIR}/*/{f}" for f in S.FILTER_SCRIPTS)],
        cwd=HERMES_ROOT, capture_output=True, text=True, check=True).stdout
    modes = {line.split()[3]: line.split()[0] for line in out.splitlines()}
    tracked = {str((d / f).relative_to(HERMES_ROOT)) for d in manifest_dirs() for f in S.FILTER_SCRIPTS
               if (d / f).is_file()}
    assert set(modes) == tracked, "every filter is tracked"
    assert all(mode == "100755" for mode in modes.values()), modes


def test_a_manifest_directory_holds_only_its_route():
    allowed = {S.MANIFEST_FILE, *S.FILTER_SCRIPTS}
    for d in manifest_dirs():
        extra = sorted(p.name for p in d.iterdir() if p.name not in allowed)
        assert extra == [], f"{d}: {extra}"


def test_a_tracked_manifest_holds_no_secret_and_no_chat():
    """A route's secret is the gateway's global one (a Keychain item); a chat id names a
    person's conversation. Neither belongs in a repository (the validator refuses `secret`
    outright; `deliver_extra` is what a private overlay's manifest may carry)."""
    for d in manifest_dirs():
        spec = S.yaml.safe_load((d / S.MANIFEST_FILE).read_text(encoding="utf-8")) or {}
        assert "secret" not in spec and "deliver_extra" not in spec, d


def test_the_repository_tracks_at_least_one_manifest():
    """ping is the first; a repository with none would leave the install path untested."""
    assert any(d.name == "ping" for d in manifest_dirs())
