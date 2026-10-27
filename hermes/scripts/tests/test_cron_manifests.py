"""The tracked cron manifests: every profiles/<p>/cron.d/<name>/ in this repository must load
through cron-sync exactly as the installed link will, and its run.sh must be executable in Git
(the wrapper execs it by path, so a lost mode bit fails only at the first tick).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
PROFILES = HERMES_ROOT / "profiles"
SCRIPT = HERMES_ROOT / "scripts" / "cron-sync.py"
SPEC = importlib.util.spec_from_file_location("cron_sync_manifests", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules["cron_sync_manifests"] = S
SPEC.loader.exec_module(S)


def manifest_dirs() -> list[Path]:
    return sorted(d for d in PROFILES.glob(f"*/{S.MANIFEST_DIR}/*") if d.is_dir())


def test_every_tracked_manifest_loads():
    errors = []
    for profile in sorted(p for p in PROFILES.iterdir() if (p / S.MANIFEST_DIR).is_dir()):
        _manifests, found = S.load_manifests(profile)
        errors.extend(f"{profile.name}/{e}" for e in found)
    assert errors == []


def test_run_scripts_are_executable_in_git():
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", f"profiles/*/{S.MANIFEST_DIR}/*/{S.RUN_SCRIPT}"],
        cwd=HERMES_ROOT, capture_output=True, text=True, check=True).stdout
    modes = {line.split()[3]: line.split()[0] for line in out.splitlines()}
    tracked = {str(d.relative_to(HERMES_ROOT) / S.RUN_SCRIPT) for d in manifest_dirs()
               if (d / S.RUN_SCRIPT).is_file()}
    assert set(modes) == tracked, "every run.sh is tracked"
    assert all(mode == "100755" for mode in modes.values()), modes


def test_a_manifest_directory_holds_only_its_job():
    allowed = {S.MANIFEST_FILE, S.RUN_SCRIPT}
    for d in manifest_dirs():
        extra = sorted(p.name for p in d.iterdir() if p.name not in allowed)
        assert extra == [], f"{d}: {extra}"


def test_the_repository_tracks_at_least_one_manifest():
    """x-snapshot is the first; a repository with none would leave the install path untested."""
    assert any(d.name == "x-snapshot" for d in manifest_dirs())


def test_no_tracked_script_registers_its_own_job():
    """A job's definition lives in cron.d/<name>/job.yaml, never in a `hermes cron create`
    command quoted in a script header (that is what cron-sync replaced)."""
    for script in sorted(PROFILES.glob("*/scripts/**/*")):
        if script.is_file():
            text = script.read_text(encoding="utf-8", errors="replace")
            assert "cron create" not in text, script
