"""The tracked ``config.example.yaml`` files must run on a stock runtime.

The real ``config.yaml`` files are private and may name providers that only the
patched runtime knows. What the repo tracks is what a fresh machine, a task
worktree and every other test reads, so it may name only providers a stock
Hermes resolves, and it must not list a tier twice: Hermes skips an identical
provider+model pair, so a duplicate is a silently dead tier.
"""

from __future__ import annotations

from pathlib import Path

import hermes_yaml as yaml
import pytest


HERMES = Path(__file__).resolve().parents[2]
CONFIGS = sorted(HERMES.glob("profiles/*/config.example.yaml")) + [HERMES / "config.example.yaml"]
PATCH_ONLY_PROVIDERS = {"anthropic-oauth"}
# A client Google's terms forbid, picked by hand only (docs/decisions/antigravity-provider.md).
HAND_PICKED_PROVIDERS = {"antigravity", "google-antigravity"}


def _load(config: Path) -> dict:
    return yaml.safe_load(config.read_text()) or {}


def _providers(node, path=""):
    """Every ``provider:`` value in the document, with where it sits."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if key == "provider" and isinstance(value, str):
                yield here, value
            else:
                yield from _providers(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _providers(value, f"{path}[{index}]")


def _id(config: Path) -> str:
    return "default" if config.parent == HERMES else config.parent.name


def test_every_profile_has_an_example():
    names = {c.parent.name for c in CONFIGS if c.parent != HERMES}
    on_disk = {p.name for p in (HERMES / "profiles").iterdir() if p.is_dir()}
    assert names == on_disk, f"profiles without config.example.yaml: {sorted(on_disk - names)}"


@pytest.mark.parametrize("config", CONFIGS, ids=_id)
def test_example_names_no_patch_only_provider(config):
    found = [f"{where}: {name}" for where, name in _providers(_load(config)) if name in PATCH_ONLY_PROVIDERS]
    assert not found, "a stock runtime does not know these providers; keep them in the private config: " + "; ".join(found)


@pytest.mark.parametrize("config", CONFIGS, ids=_id)
def test_example_names_no_hand_picked_provider(config):
    found = [f"{where}: {name}" for where, name in _providers(_load(config))
             if name.strip().lower() in HAND_PICKED_PROVIDERS]
    assert not found, "these providers are picked by hand, never named in a config: " + "; ".join(found)


def test_the_hand_picked_check_catches_an_alias_in_any_case():
    document = {"model": {"provider": "Google-Antigravity"}, "fallback_providers": [{"provider": "anthropic"}]}
    assert [name for _, name in _providers(document) if name.strip().lower() in HAND_PICKED_PROVIDERS] == [
        "Google-Antigravity"]


@pytest.mark.parametrize("config", CONFIGS, ids=_id)
def test_example_chain_has_no_duplicate_tier(config):
    data = _load(config)
    model = data.get("model") or {}
    tiers = [(model.get("provider"), model.get("default"))]
    tiers += [(t.get("provider"), t.get("model")) for t in data.get("fallback_providers") or []]
    seen: set[tuple] = set()
    duplicates = [t for t in tiers if t in seen or seen.add(t)]
    assert not duplicates, f"duplicate provider+model tiers are skipped at runtime: {duplicates}"
