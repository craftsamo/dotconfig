"""evm-access: EVM chains for the Assistant, Researcher, Searcher and Marketer.

One tool, ``evm`` (toolset ``evm_access``): blocks, transactions, addresses, portfolios, logs,
tokens, allowances, decoding, gas and prices on Ethereum, Base, Arbitrum, OP Mainnet, Polygon, BNB
Chain, Avalanche and their testnets; the Assistant also lists the user's wallets and sends coins and
ERC-20 tokens, each external transfer on an approval card. The logic is shared with solana-access
in ``../_shared/access.py``. Contract: docs/web3.md.
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
FAMILY = "evm"


def register(ctx):
    access.register(ctx, FAMILY)
