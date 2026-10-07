"""solana-access: Solana for the Assistant, Researcher, Searcher and Marketer.

One tool, ``solana`` (toolset ``solana_access``): blocks, transactions, accounts, portfolios,
tokens, delegations, decoding, fees and prices on mainnet-beta and devnet; the Assistant also lists
the user's wallets and sends SOL and SPL tokens, each external transfer on an approval card. The
logic is shared with evm-access in ``../_shared/access.py``. Contract: docs/web3.md.
"""

from __future__ import annotations

import importlib.util
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


def register(ctx):
    access.register(ctx, FAMILY)
