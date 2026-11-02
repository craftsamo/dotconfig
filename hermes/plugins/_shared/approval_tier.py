"""approval_tier: decide what allowlist key an approval card gets.

When a plugin's ``pre_tool_call`` hook returns an ``approve`` directive, Hermes stores "session"
or "always" decisions under the returned ``rule_key``. Most calls hash their exact arguments so an
approval never covers a different call. Standing rules coalesce similar calls to the same target
(for example, edits to one Google Sheet or one YouTube video), so the human approves the target
once.

Shared by plugins that build approval keys (each loads this file by path; it is not a plugin and
has no manifest).
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys


def _load_card():
    if "hermes_card" not in sys.modules:
        spec = importlib.util.spec_from_file_location("hermes_card", Path(__file__).resolve().parent / "card.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["hermes_card"] = module
        spec.loader.exec_module(module)
    return sys.modules["hermes_card"]


_card = _load_card()

FREE = "free"
STANDING = "standing"
MANDATE = "mandate"
EACH = "each"

SAFE, CAUTION, DANGER = _card.SAFE, _card.CAUTION, _card.DANGER


# A dataclass looks its module up in sys.modules, so a loader registers this module under its key
# before executing it (every _load_shared does).
@dataclass(frozen=True)
class Rule:
    """Approval tier rule for a plugin action."""

    tier: str = EACH
    name: str = ""
    scope: str = ""
    levels: frozenset[str] = frozenset({SAFE})

    def __post_init__(self) -> None:
        if self.tier not in (FREE, STANDING, MANDATE, EACH):
            raise ValueError(f"unknown tier: {self.tier}")
        if self.tier in (STANDING, FREE) and not self.scope:
            raise ValueError(f"scope required for tier: {self.tier}")
        if self.tier == STANDING and not self.name:
            raise ValueError("a standing rule needs a name of its own, apart from every action's")
        if not isinstance(self.levels, frozenset):
            object.__setattr__(self, "levels", frozenset(self.levels))
        if DANGER in self.levels:
            raise ValueError("DANGER cannot be in rule levels")


# These two coalesced keys predate the tiers (the user chose them; the spreadsheet's version
# history and the video's edit history undo them) and are the only standing rules allowed at CAUTION.
GRANDFATHERED = frozenset({SAFE, CAUTION})

# A standing rule's name never equals an action's, so its key (name + target) cannot be read as an
# exact key (action + digest). The rest of the table applies at SAFE only: the card's own level is
# read on each call, so a call that reaches others or cannot be undone keeps its exact key.
TIERS: dict[str, dict[str, Rule]] = {
    "google-access": {
        **{action: Rule(STANDING, "sheets-edit", "spreadsheet", GRANDFATHERED)
           for action in ("add_sheet", "append", "batch_update", "chart", "layout", "pivot", "update")},
        "upload": Rule(STANDING, "my-drive-upload", "profile"),
    },
    "youtube-access": {
        "update": Rule(STANDING, "edit", "video", GRANDFATHERED),
        "thumbnail": Rule(STANDING, "edit", "video", GRANDFATHERED),
        "playlist_move": Rule(STANDING, "playlist-order", "channel"),
        "playlist_remove": Rule(STANDING, "playlist-order", "channel"),
        "watermark_remove": Rule(STANDING, "watermark-off", "channel"),
        "moderate": Rule(STANDING, "moderate-hold", "channel"),
    },
    "signal-access": {"send": Rule(STANDING, "send-self", "account")},
    "telegram-access": {"send": Rule(STANDING, "send-self", "account")},
    "discord-access": {
        "unreact": Rule(STANDING, "unreact-in", "channel"),
        "unpin": Rule(STANDING, "unpin-in", "channel"),
    },
    "note-access": {"create_draft": Rule(STANDING, "new-draft", "account")},
    "substack-access": {
        "create_draft": Rule(STANDING, "private-draft", "publication"),
        "update_draft": Rule(STANDING, "private-draft", "publication"),
        "unschedule": Rule(STANDING, "unschedule-draft", "publication"),
    },
    "stripe-access": {
        action: Rule(STANDING, "test-write", "account")
        for action in ("customer_create", "customer_update", "product_create", "product_update", "price_create",
                       "price_update", "coupon_create", "coupon_update", "promotion_code_create",
                       "promotion_code_update", "invoice_create", "payment_link_create", "payment_link_update")
    },
    "cloudflare-access": {
        "storage_create": Rule(STANDING, "empty-storage", "account"),
        "cache_purge": Rule(STANDING, "purge-urls", "zone"),
        "zone_setting": Rule(STANDING, "dev-mode-on", "zone"),
    },
}


def rule_for(plugin: str, action: str) -> Rule:
    """Return the configured Rule for a plugin action, or a default Rule() (EACH)."""
    return TIERS.get(plugin, {}).get(action, Rule())


def each_key(plugin: str, action: str, digest: str) -> str:
    """Return an exact payload allowlist key."""
    return f"{plugin}:{action}:{digest}"


def rule_key(plugin: str, action: str, level: str, digest: str, *,
             scope: tuple | list = (), eligible: bool = True, exact: str | None = None) -> str:
    """Return the allowlist rule key: standing when eligible and within rule levels, else exact."""
    rule = rule_for(plugin, action)
    if eligible and rule.tier == STANDING and level in rule.levels and scope and all(scope):
        return ":".join((plugin, rule.name or action, *map(str, scope)))
    return each_key(plugin, exact or action, digest)


def needs_card(plugin: str, action: str, level: str) -> bool:
    """Return False only when the rule is FREE and level is within rule.levels; else True."""
    rule = rule_for(plugin, action)
    return not (rule.tier == FREE and level in rule.levels)
