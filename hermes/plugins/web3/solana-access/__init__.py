"""solana-access: Solana for the Assistant, Researcher, Searcher and Marketer.

One tool, ``solana`` (toolset ``solana_access``): blocks, transactions, accounts, portfolios,
tokens, delegations, decoding, fees and prices on mainnet-beta and devnet; the Assistant also lists
the user's wallets and sends SOL and SPL tokens, each external transfer on an approval card. The
logic is shared with evm-access in ``../_shared/access.py``. The plugin ships read-only skills (``skills/``), registered as
``solana-access:<skill>``: reading for every profile with the tool, the wallet procedure for the
Assistant alone. Contract: docs/web3.md.
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


access = _load("hermes_web3_access", SHARED / "access.py")
FAMILY = "solana"
PLUGIN = "solana-access"
logger = logging.getLogger(__name__)
# Skill -> the profiles it is registered for. A skill is read-only to Hermes (not editable through
# skill_manage); the wallet procedure reaches only the profiles that can sign.
SKILLS = {"solana": set(access.PROFILES), "solana-wallet": set(access.SIGNING)}


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
    access.register(ctx, FAMILY)
    register_skills(ctx, ctx.profile_name)
