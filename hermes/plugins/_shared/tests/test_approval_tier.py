"""approval_tier: decide what allowlist key an approval card gets."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "approval_tier_under_test",
    Path(__file__).resolve().parents[1] / "approval_tier.py",
)
approval_tier = importlib.util.module_from_spec(spec)
sys.modules["approval_tier_under_test"] = approval_tier
spec.loader.exec_module(approval_tier)


def test_broad_key_shape_and_exact_key_shape():
    # Standing rule with matching level returns broad coalesced key
    broad = approval_tier.rule_key(
        "google-access", "update", approval_tier.CAUTION, "digest1234567890", scope=("SID123",)
    )
    assert broad == "google-access:sheets-edit:SID123"

    # Default/EACH rule returns exact payload key
    exact = approval_tier.rule_key(
        "other-plugin", "action", approval_tier.SAFE, "digest1234567890", scope=("SID123",)
    )
    assert exact == "other-plugin:action:digest1234567890"


def test_danger_level_returns_exact_key():
    key = approval_tier.rule_key(
        "google-access", "update", approval_tier.DANGER, "digest1234567890", scope=("SID123",)
    )
    assert key == "google-access:update:digest1234567890"


def test_caution_level_on_rule_with_safe_only_returns_exact_key(monkeypatch):
    synthetic_tiers = {
        "test-plugin": {
            "write": approval_tier.Rule(
                tier=approval_tier.STANDING,
                name="standing-write",
                scope="target",
                levels=frozenset({approval_tier.SAFE}),
            ),
        },
    }
    monkeypatch.setattr(approval_tier, "TIERS", synthetic_tiers)
    key = approval_tier.rule_key(
        "test-plugin", "write", approval_tier.CAUTION, "digest1234567890", scope=("target1",)
    )
    assert key == "test-plugin:write:digest1234567890"


def test_eligible_false_returns_exact_key():
    key = approval_tier.rule_key(
        "google-access", "update", approval_tier.CAUTION, "digest1234567890",
        scope=("SID123",), eligible=False,
    )
    assert key == "google-access:update:digest1234567890"


@pytest.mark.parametrize("bad_scope", [(), ("",), ("SID123", ""), (None,), ("SID123", None)])
def test_empty_scope_or_empty_scope_part_returns_exact_key(bad_scope):
    key = approval_tier.rule_key(
        "google-access", "update", approval_tier.CAUTION, "digest1234567890", scope=bad_scope
    )
    assert key == "google-access:update:digest1234567890"


def test_unknown_plugin_or_action_returns_exact_key():
    key1 = approval_tier.rule_key("unknown-plugin", "action", approval_tier.SAFE, "digest123")
    assert key1 == "unknown-plugin:action:digest123"

    key2 = approval_tier.rule_key("google-access", "unknown_action", approval_tier.SAFE, "digest123")
    assert key2 == "google-access:unknown_action:digest123"


def test_exact_overrides_action_segment_of_exact_key():
    # When falling through, exact= overrides the action segment
    key = approval_tier.rule_key(
        "google-access", "clear", approval_tier.CAUTION, "digest1234567890",
        scope=("SID123",), exact="google_sheets",
    )
    assert key == "google-access:google_sheets:digest1234567890"


def test_each_key():
    assert approval_tier.each_key("my-plugin", "do_thing", "abcdef1234567890") == "my-plugin:do_thing:abcdef1234567890"


def test_rule_validation_errors():
    with pytest.raises(ValueError, match="scope required"):
        approval_tier.Rule(tier=approval_tier.STANDING, name="edit", scope="")

    with pytest.raises(ValueError, match="scope required"):
        approval_tier.Rule(tier=approval_tier.FREE, name="read", scope="")

    with pytest.raises(ValueError, match="needs a name"):
        approval_tier.Rule(tier=approval_tier.STANDING, scope="account")

    with pytest.raises(ValueError, match="DANGER"):
        approval_tier.Rule(levels=frozenset({approval_tier.DANGER}))

    with pytest.raises(ValueError, match="unknown tier"):
        approval_tier.Rule(tier="invalid_tier")


def test_needs_card_with_synthetic_free_rule(monkeypatch):
    synthetic_tiers = {
        "test-plugin": {
            "read": approval_tier.Rule(
                tier=approval_tier.FREE,
                scope="target",
                levels=frozenset({approval_tier.SAFE}),
            ),
            "standing_act": approval_tier.Rule(
                tier=approval_tier.STANDING,
                name="act-on",
                scope="target",
                levels=frozenset({approval_tier.SAFE}),
            ),
        },
    }
    monkeypatch.setattr(approval_tier, "TIERS", synthetic_tiers)

    # Free rule at SAFE level does not need card
    assert approval_tier.needs_card("test-plugin", "read", approval_tier.SAFE) is False
    # Free rule at level not in rule.levels still needs card
    assert approval_tier.needs_card("test-plugin", "read", approval_tier.CAUTION) is True
    # Non-free rules need card
    assert approval_tier.needs_card("test-plugin", "standing_act", approval_tier.SAFE) is True
    # Unconfigured actions need card
    assert approval_tier.needs_card("test-plugin", "other", approval_tier.SAFE) is True
