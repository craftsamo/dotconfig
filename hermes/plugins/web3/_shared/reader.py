"""The read engine of the ``evm`` and ``solana`` tools: one read per process, run by the web3 venv's interpreter.

The plugin writes one JSON request to stdin and reads one JSON reply from stdout:

    {"action": "block" | "tx" | …, "chain": "<table key>", …the action's arguments}
    → {"ok": true, "data": {…}} or {"ok": false, "error": "…"}

Nothing here signs, holds a key or writes a file. ``_rpc`` (an endpoint), ``_offline`` (no
Sourcify, Etherscan, 4byte or CoinGecko lookups) and ``_http`` (one server standing in for
Sourcify, Etherscan and the signature database) are honoured only when the engine's own tests set
``WEB3_ENGINE_TEST=1``; the plugin never passes them. Contract: docs/web3.md "Reads".
"""

from __future__ import annotations

import json
import sys

import abi
import chains
import contracts
import evm
import prices
import rpc
import sol

EVM_ACTIONS = {**evm.ACTIONS, **contracts.ACTIONS}


class Ctx:
    def __init__(self, chain: str, payload: dict):
        self.chain = chain
        self.payload = payload
        test = rpc.testing()
        self.override = payload.get("_rpc") if test else None
        self.online = not (test and payload.get("_offline"))
        self.rpc = rpc.Rpc(chain, self.override)
        self.prices = prices.Prices(self.online)
        info = chains.info(chain)
        self.decoder = abi.Decoder(info["id"], self.online, payload.get("_http") if test else None) \
            if chain in chains.EVM else None

    def child(self, chain: str) -> "Ctx":
        sub = Ctx(chain, self.payload)
        sub.prices = self.prices
        return sub

    def rpc_for(self, chain: str) -> rpc.Rpc:
        return rpc.Rpc(chain, self.override)


def run(payload: dict) -> dict:
    action, chain = payload.get("action"), payload.get("chain")
    kind = chains.family(chain) if isinstance(chain, str) else None
    if kind is None:
        raise rpc.ChainError(f"unknown chain {chain!r}; use one of: {', '.join(chains.CHAINS)}")
    table = EVM_ACTIONS if kind == "evm" else sol.ACTIONS
    if action not in table:
        raise rpc.ChainError(f"{action!r} is not available on {chain}; use one of: {', '.join(table)}")
    return table[action](Ctx(chain, payload), payload)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise rpc.ChainError("the request must be a JSON object")
        reply = {"ok": True, "data": run(payload)}
    except rpc.ChainError as exc:
        reply = {"ok": False, "error": rpc.mask(exc)}
    except Exception as exc:  # an engine bug or an unexpected reply: say what, never where
        reply = {"ok": False, "error": rpc.mask(f"{type(exc).__name__}: {exc}")[:500]}
    sys.stdout.write(rpc.mask(json.dumps(reply, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
