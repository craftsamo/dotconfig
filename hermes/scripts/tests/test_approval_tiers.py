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

SAFE_ONLY = ("safe",)
AT_CAUTION_TOO = ("caution", "safe")

# plugin -> action -> (tier, the name its key carries, the card levels it applies at). The target
# each key binds is the rule's ``scope`` (account, channel, ...), checked below.
EXPECTED = {
    "google-access": {
        "add_sheet": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "append": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "batch_update": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "chart": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "layout": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "pivot": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "update": ("standing", "sheets-edit", AT_CAUTION_TOO),
        "upload": ("standing", "my-drive-upload", SAFE_ONLY),
    },
    "youtube-access": {
        "thumbnail": ("standing", "edit", AT_CAUTION_TOO),
        "update": ("standing", "edit", AT_CAUTION_TOO),
        "playlist_move": ("standing", "playlist-order", SAFE_ONLY),
        "playlist_remove": ("standing", "playlist-order", SAFE_ONLY),
        "watermark_remove": ("standing", "watermark-off", SAFE_ONLY),
        "moderate": ("standing", "moderate-hold", SAFE_ONLY),
    },
    "note-access": {"create_draft": ("standing", "new-draft", SAFE_ONLY)},
    "substack-access": {
        "create_draft": ("standing", "private-draft", SAFE_ONLY),
        "update_draft": ("standing", "private-draft", SAFE_ONLY),
        "unschedule": ("standing", "unschedule-draft", SAFE_ONLY),
    },
    "stripe-access": {
        # Test mode only (the plugin marks every test-mode card safe and passes the mode as eligibility).
        # The ONCE actions (refunds, finalizing or sending an invoice, cancelling) are not here: they ask each time.
        "customer_create": ("standing", "test-write", SAFE_ONLY),
        "customer_update": ("standing", "test-write", SAFE_ONLY),
        "product_create": ("standing", "test-write", SAFE_ONLY),
        "product_update": ("standing", "test-write", SAFE_ONLY),
        "price_create": ("standing", "test-write", SAFE_ONLY),
        "price_update": ("standing", "test-write", SAFE_ONLY),
        "coupon_create": ("standing", "test-write", SAFE_ONLY),
        "coupon_update": ("standing", "test-write", SAFE_ONLY),
        "promotion_code_create": ("standing", "test-write", SAFE_ONLY),
        "promotion_code_update": ("standing", "test-write", SAFE_ONLY),
        "invoice_create": ("standing", "test-write", SAFE_ONLY),
        "payment_link_create": ("standing", "test-write", SAFE_ONLY),
        "payment_link_update": ("standing", "test-write", SAFE_ONLY),
    },
    "cloudflare-access": {
        # An empty storage container (account), a purge of listed URLs and turning development mode on
        # (it ends on its own in 3 hours), per zone. A purge of everything, a host or a prefix, every
        # other setting and every card that reaches visitors keeps asking per request.
        "storage_create": ("standing", "empty-storage", SAFE_ONLY),
        "cache_purge": ("standing", "purge-urls", SAFE_ONLY),
        "zone_setting": ("standing", "dev-mode-on", SAFE_ONLY),
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


def test_a_standing_name_is_never_an_action_and_its_rules_agree():
    """The key is name + target, an exact key is action + digest: a name that is also an action could be read as
    one. Actions that share a name share one key, so they must bind the same target at the same levels."""
    by_name = {}
    for plugin, actions in approval_tier.TIERS.items():
        for action, rule in actions.items():
            assert rule.name and rule.name not in actions, f"{plugin}:{action} is named like an action"
            by_name.setdefault((plugin, rule.name), set()).add((rule.scope, rule.levels))
    assert all(len(shapes) == 1 for shapes in by_name.values()), by_name


def test_no_free_or_mandate_rule_exists_yet():
    # The free tier starts empty on purpose until explicitly approved.
    tiers_used = {rule.tier for actions in approval_tier.TIERS.values() for rule in actions.values()}
    assert tiers_used <= {approval_tier.STANDING}
