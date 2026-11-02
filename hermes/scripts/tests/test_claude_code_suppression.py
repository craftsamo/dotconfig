"""Tests for claude-code-suppression.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "claude-code-suppression.py"
SPEC = importlib.util.spec_from_file_location("claude_code_suppression", SCRIPT)
assert SPEC and SPEC.loader
CCS = importlib.util.module_from_spec(SPEC)
sys.modules["claude_code_suppression"] = CCS
SPEC.loader.exec_module(CCS)

pytest.importorskip("hermes_cli.auth")

INITIAL_WORK_PROVIDERS = {"custom": {"api_key": "dummy-key"}}
INITIAL_WORK_POOL = {"custom": [{"id": "c1", "api_key": "dummy-key"}]}


@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "hermes"
    root.mkdir(parents=True)
    monkeypatch.setenv("HERMES_DIR", str(root))
    monkeypatch.setenv("HERMES_HOME", str(root))

    # Root auth.json suppressing anthropic-oauth: [claude_code]
    (root / "auth.json").write_text(
        json.dumps({
            "version": 1,
            "providers": {},
            "suppressed_sources": {
                "anthropic-oauth": ["claude_code"],
            },
        }, indent=2),
        encoding="utf-8",
    )

    profiles = root / "profiles"

    # Profile work: auth.json has anthropic suppression, custom providers, credential_pool
    work_dir = profiles / "work"
    work_dir.mkdir(parents=True)
    (work_dir / "config.yaml").write_text("model: test\n", encoding="utf-8")
    (work_dir / "auth.json").write_text(
        json.dumps({
            "version": 1,
            "providers": INITIAL_WORK_PROVIDERS,
            "suppressed_sources": {
                "anthropic": ["claude_code"],
            },
            "credential_pool": INITIAL_WORK_POOL,
        }, indent=2),
        encoding="utf-8",
    )

    # Profile personal: auth.json already suppresses anthropic-oauth: [claude_code]
    personal_dir = profiles / "personal"
    personal_dir.mkdir(parents=True)
    (personal_dir / "config.yaml").write_text("model: test\n", encoding="utf-8")
    (personal_dir / "auth.json").write_text(
        json.dumps({
            "version": 1,
            "providers": {},
            "suppressed_sources": {
                "anthropic-oauth": ["claude_code"],
            },
        }, indent=2),
        encoding="utf-8",
    )

    # Profile fresh: only config.yaml, no auth.json
    fresh_dir = profiles / "fresh"
    fresh_dir.mkdir(parents=True)
    (fresh_dir / "config.yaml").write_text("model: test\n", encoding="utf-8")

    # not-a-profile: directory without config.yaml (must be ignored)
    not_a_profile = profiles / "not-a-profile"
    not_a_profile.mkdir(parents=True)

    return root


def test_check_mode_reports_missing_and_writes_nothing(
    temp_root: Path, capsys: pytest.CaptureFixture[str]
):
    root_auth = temp_root / "auth.json"
    work_auth = temp_root / "profiles" / "work" / "auth.json"
    personal_auth = temp_root / "profiles" / "personal" / "auth.json"
    fresh_auth = temp_root / "profiles" / "fresh" / "auth.json"

    files_to_check = [root_auth, work_auth, personal_auth]
    before_state = [(p, p.read_bytes(), p.stat().st_mtime_ns) for p in files_to_check]

    ret = CCS.main(["--root", str(temp_root)])
    assert ret == 1

    out, err = capsys.readouterr()
    assert out.strip().splitlines() == [
        "ok root",
        "missing fresh",
        "ok personal",
        "missing work",
    ]
    assert "run with --fix" in err.lower()
    assert "launchd/gateway-launchctl.sh restart" in err

    assert not fresh_auth.exists()
    for p, content, mtime_ns in before_state:
        assert p.read_bytes() == content
        assert p.stat().st_mtime_ns == mtime_ns


def test_fix_mode_resolves_and_check_passes(
    temp_root: Path, capsys: pytest.CaptureFixture[str]
):
    ret = CCS.main(["--root", str(temp_root), "--fix"])
    assert ret == 0

    out, err = capsys.readouterr()
    lines = out.strip().splitlines()
    assert lines == [
        "ok root",
        "fixed fresh",
        "ok personal",
        "fixed work",
    ]
    assert "fixed fresh" in lines
    assert "fixed work" in lines
    assert err == ""

    # Afterwards check mode returns 0
    ret_check = CCS.main(["--root", str(temp_root)])
    assert ret_check == 0

    out_check, err_check = capsys.readouterr()
    assert out_check.strip().splitlines() == [
        "ok root",
        "ok fresh",
        "ok personal",
        "ok work",
    ]
    assert err_check == ""


def test_fix_preserves_other_auth_and_no_anthropic_oauth_in_credential_pool(
    temp_root: Path,
):
    ret = CCS.main(["--root", str(temp_root), "--fix"])
    assert ret == 0

    work_auth = temp_root / "profiles" / "work" / "auth.json"
    fresh_auth = temp_root / "profiles" / "fresh" / "auth.json"

    work_data = json.loads(work_auth.read_text(encoding="utf-8"))
    assert work_data["suppressed_sources"]["anthropic"] == ["claude_code"]
    assert work_data["suppressed_sources"]["anthropic-oauth"] == ["claude_code"]
    assert work_data["credential_pool"] == INITIAL_WORK_POOL
    assert work_data["providers"] == INITIAL_WORK_PROVIDERS
    assert "anthropic-oauth" not in work_data.get("credential_pool", {})

    fresh_data = json.loads(fresh_auth.read_text(encoding="utf-8"))
    assert fresh_data["suppressed_sources"]["anthropic-oauth"] == ["claude_code"]
    assert "anthropic-oauth" not in fresh_data.get("credential_pool", {})


def test_fix_twice_does_not_duplicate_entry(temp_root: Path):
    ret1 = CCS.main(["--root", str(temp_root), "--fix"])
    assert ret1 == 0

    ret2 = CCS.main(["--root", str(temp_root), "--fix"])
    assert ret2 == 0

    work_auth = temp_root / "profiles" / "work" / "auth.json"
    fresh_auth = temp_root / "profiles" / "fresh" / "auth.json"

    work_data = json.loads(work_auth.read_text(encoding="utf-8"))
    assert work_data["suppressed_sources"]["anthropic-oauth"] == ["claude_code"]

    fresh_data = json.loads(fresh_auth.read_text(encoding="utf-8"))
    assert fresh_data["suppressed_sources"]["anthropic-oauth"] == ["claude_code"]


def test_homes_follow_the_runtime_profile_rules(temp_root: Path):
    profiles = temp_root / "profiles"
    (profiles / "soul-only").mkdir()
    (profiles / "soul-only" / "SOUL.md").write_text("persona\n", encoding="utf-8")
    (profiles / "Bad_Name").mkdir()
    (profiles / "Bad_Name" / "config.yaml").write_text("model: test\n", encoding="utf-8")

    names = [name for name, _ in CCS.discover_homes(temp_root)]
    assert names == ["root", "fresh", "personal", "soul-only", "work"]


def test_default_root_uses_hermes_dir(
    temp_root: Path, capsys: pytest.CaptureFixture[str]
):
    ret = CCS.main([])
    assert ret == 1

    out, _ = capsys.readouterr()
    assert out.strip().splitlines() == [
        "ok root",
        "missing fresh",
        "ok personal",
        "missing work",
    ]
