"""Approval tiers decide what allowlist key an approval card gets.

Standing rules coalesce approvals to a target (such as a spreadsheet or video) instead of
requiring human review on every individual payload. This table is the review point: any change
to a tier or rule scope must be updated here on purpose.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

HERMES = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "approval_tier",
    HERMES / "plugins" / "_shared" / "approval_tier.py",
)
approval_tier = importlib.util.module_from_spec(spec)
sys.modules["approval_tier"] = approval_tier
spec.loader.exec_module(approval_tier)

EXPECTED = {
    "google-access": {
        "add_sheet": ("standing", "sheets-edit", ("caution", "safe")),
        "append": ("standing", "sheets-edit", ("caution", "safe")),
        "batch_update": ("standing", "sheets-edit", ("caution", "safe")),
        "chart": ("standing", "sheets-edit", ("caution", "safe")),
        "layout": ("standing", "sheets-edit", ("caution", "safe")),
        "pivot": ("standing", "sheets-edit", ("caution", "safe")),
        "update": ("standing", "sheets-edit", ("caution", "safe")),
    },
    "youtube-access": {
        "thumbnail": ("standing", "edit", ("caution", "safe")),
        "update": ("standing", "edit", ("caution", "safe")),
    },
}

GRANDFATHERED_AT_CAUTION = {
    ("google-access", "add_sheet"),
    ("google-access", "append"),
    ("google-access", "batch_update"),
    ("google-access", "chart"),
    ("google-access", "layout"),
    ("google-access", "pivot"),
    ("google-access", "update"),
    ("youtube-access", "thumbnail"),
    ("youtube-access", "update"),
}


def test_tiers_match_expected():
    flattened = {
        plugin: {
            action: (rule.tier, rule.name, tuple(sorted(rule.levels)))
            for action, rule in sorted(actions.items())
        }
        for plugin, actions in sorted(approval_tier.TIERS.items())
    }
    assert flattened == EXPECTED


def test_every_plugin_key_names_a_plugin_directory():
    plugins_dir = HERMES / "plugins"
    for plugin in approval_tier.TIERS:
        matches = (list(plugins_dir.glob(f"**/{plugin}/plugin.yaml"))
                   + list(plugins_dir.glob(f"**/{plugin}/__init__.py")))
        assert len(matches) > 0, f"no plugin directory found for {plugin}"


def test_danger_never_in_levels_and_caution_only_for_grandfathered():
    for plugin, actions in approval_tier.TIERS.items():
        for action, rule in actions.items():
            assert approval_tier.DANGER not in rule.levels, f"{plugin}:{action} has DANGER in levels"
            if approval_tier.CAUTION in rule.levels:
                assert (plugin, action) in GRANDFATHERED_AT_CAUTION, (
                    f"{plugin}:{action} has CAUTION in levels but is not grandfathered"
                )


def test_no_free_or_mandate_rule_exists_yet():
    # The free tier starts empty on purpose until explicitly approved.
    tiers_used = {rule.tier for actions in approval_tier.TIERS.values() for rule in actions.values()}
    assert tiers_used <= {approval_tier.STANDING}
