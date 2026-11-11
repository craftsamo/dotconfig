"""external-plugins.py: manifest shape, OpenCode version agreement, status computation."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "external-plugins.py"
SPEC = importlib.util.spec_from_file_location("external_plugins", SCRIPT)
ep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ep)

OPENCODE_CONFIG = Path(__file__).resolve().parents[3] / "opencode" / "opencode.jsonc"
MANIFEST = ep.load_manifest()
PIN = "a" * 40


def _entry(commit: str = PIN) -> dict:
    return {"repo": "o/n", "version": "1.2.3", "commit": commit}


def _write_metadata(home: Path, data: dict) -> None:
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    (home / "plugins" / ep.METADATA_FILE).write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_manifest_entry_shape(name):
    entry = MANIFEST[name]
    assert re.fullmatch(r"[0-9a-f]{40}", entry["commit"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", entry["version"])
    assert re.fullmatch(r"[^/\s]+/[^/\s]+", entry["repo"])
    if "npm" in entry:
        assert entry["npm"].startswith("@")


@pytest.mark.parametrize("name", [n for n, e in sorted(MANIFEST.items()) if "npm" in e])
def test_opencode_loads_the_pinned_release(name):
    entry = MANIFEST[name]
    text = OPENCODE_CONFIG.read_text(encoding="utf-8")
    found = re.findall(re.escape(entry["npm"]) + r"@([0-9][^\s\"']*)", text)
    assert found and set(found) == {entry["version"]}


def test_status_ok_missing_unpinned_differs():
    entry = _entry()
    good = {"pinned": True, "revision": PIN}
    assert ep.compute_status(entry, good, PIN) == "ok"
    assert ep.compute_status(entry, good, None) == "missing"
    assert ep.compute_status(entry, {"revision": PIN}, PIN) == "unpinned"
    assert ep.compute_status(entry, None, PIN) == "unpinned"
    other = "b" * 40
    assert ep.compute_status(entry, {"pinned": True, "revision": other}, other) == (
        "differs (installed bbbbbbb, pinned aaaaaaa)"
    )
    assert ep.compute_status(entry, good, other).startswith("differs (installed bbbbbbb")


def test_collect_status_reads_metadata_with_injected_head(tmp_path):
    manifest = {"one": _entry(), "two": _entry(), "three": _entry()}
    _write_metadata(tmp_path, {"one": {"pinned": True, "revision": PIN}, "two": {"pinned": True, "revision": PIN}})
    heads = {"one": PIN, "two": "c" * 40}
    result = ep.collect_status(manifest, tmp_path, lambda d: heads.get(d.name))
    assert result["one"] == "ok"
    assert result["two"].startswith("differs")
    assert result["three"] == "missing"


def test_live_checkout_check_false_under_temp_dir(tmp_path):
    script = tmp_path / "hermes" / "scripts" / "external-plugins.py"
    script.parent.mkdir(parents=True)
    script.touch()
    assert ep.is_live_checkout(script) is False
    assert ep.is_live_checkout(script, live=tmp_path / "hermes") is True


VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "external_plugins_validator", Path(__file__).resolve().parents[1] / "validate-profile-skills.py")
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(validator)


def test_a_plugin_is_enabled_only_with_the_guard_it_requires(tmp_path):
    required = {(name, needed) for name, entry in MANIFEST.items() for needed in entry.get("requires", ())}
    assert ("signal-tools", "signal-tools-guard") in required
    assert ("github-tools", "github-tools-guard") in required
    config = tmp_path / "config.yaml"
    base = "skills:\n  create_dir: skills/learned\nplugins:\n  enabled:\n  - skill-topology\n"
    config.write_text(base + "  - signal-tools\n", encoding="utf-8")
    errors: list[str] = []
    validator.validate_plugin_enabled("assistant", config, errors)
    assert errors == [f"signal-tools is enabled without signal-tools-guard: {config}"]
    config.write_text(base + "  - signal-tools\n  - signal-tools-guard\n", encoding="utf-8")
    errors = []
    validator.validate_plugin_enabled("assistant", config, errors)
    assert errors == []


def test_the_skills_a_pin_lists_are_known_to_the_validator():
    errors: list[str] = []
    validator.validate_plugin_skills(errors)
    assert not [e for e in errors if "signal-tools:" in e]
