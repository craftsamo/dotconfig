"""hyperliquid-access: Hyperliquid for the Assistant, Researcher, Searcher and Marketer.

One tool, ``hyperliquid`` (toolset ``hyperliquid_access``): perp and spot markets, builder perp
dexs, candles, funding, order books, any account's positions, balances, fills and orders, trade
reviews and normalized dataset exports, on mainnet and testnet, through Hyperliquid's public
``/info`` endpoint; the Assistant also trades from its Hermes wallets, each action that can add
exposure on an approval card. The logic is in ``../_shared/hl_access.py`` (the tool and its hook),
``../_shared/hl.py`` (reads) and ``../_shared/hl_trader.py`` (trades). The plugin ships read-only
skills (``skills/``), registered as ``hyperliquid-access:<skill>``: reading for every profile with
the tool, the trade procedure for the Assistant alone. Contract: docs/hyperliquid.md.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys

SHARED = Path(__file__).resolve().parent.parent / "_shared"


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


hl_access = _load("hermes_web3_hl_access", SHARED / "hl_access.py")
access = hl_access.access
PLUGIN = "hyperliquid-access"
logger = logging.getLogger(__name__)
# Skill -> the profiles it is registered for. A skill is read-only to Hermes (not editable through
# skill_manage); the trade and strategy procedures reach only the profiles that can sign.
SKILLS = {"hyperliquid": set(access.PROFILES), "hyperliquid-trade": set(access.SIGNING),
          "configure-strategy": set(access.SIGNING), "run-strategy": set(access.SIGNING),
          "manage-strategy": set(access.SIGNING)}


def register_skills(ctx, profile):
    """Register this profile's skills; a skill that cannot be read is logged and never costs the tool."""
    for name, profiles in SKILLS.items():
        if profile not in profiles:
            continue
        try:
            from agent.skill_utils import parse_frontmatter

            path = Path(__file__).resolve().parent / "skills" / name / "SKILL.md"
            meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            ctx.register_skill(name, path, description=meta["description"], frontmatter=meta)
        except Exception as exc:
            logger.warning("%s skill %s not registered: %s", PLUGIN, name, exc)


def register(ctx):
    hl_access.register(ctx)
    register_skills(ctx, ctx.profile_name)
