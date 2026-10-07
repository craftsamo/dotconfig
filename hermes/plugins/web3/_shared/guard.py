"""Ways around the web3 tools (docs/web3.md "Ways around the tools").

Pure Python, loaded by path in Hermes' own interpreter by both plugins. A pattern match on the
text of a terminal, code or file-tool call, not a sandbox: it stops ordinary use, not a
determined script. The wallet passes ``wallet=True`` for its stricter set (the signer, its state,
the seed's scope and signing CLIs).
"""

from __future__ import annotations

import re

TERMINAL_TOOLS = {"terminal", "execute_code"}
FILE_TOOLS = {"read_file", "write_file", "patch", "search_files"}

_READ = re.compile(
    r"(?<![\w-])web3-rpc(?![\w-])|ALCHEMY_API_KEY|HELIUS_API_KEY|local/web3(?![\w-])"
    r"|dump-keychain|secret\s+export|find-generic-password", re.IGNORECASE)
_WALLET = re.compile(
    r"(?<![\w-])web3-wallet(?![\w-])|WEB3_SEED_|signer\.py|web3/wallet"
    r"|\bcast\s+(send|wallet|mktx|publish)\b|\bsolana\s+(transfer|keygen)\b|\bspl-token\s+transfer\b"
    r"|eth_sendRawTransaction|sendTransaction", re.IGNORECASE)
_SOURCE_READ = re.compile(r"plugins/web3/[\w./-]+\.(py|yaml|md)$")

READ_MESSAGE = (
    "Chains are read only through the chain tool, never through the terminal, code or file tools; "
    "the RPC provider keys (Keychain) and the engine are never used directly.")
WALLET_MESSAGE = (
    "Funds move only through the wallet tool, never through the terminal, code or file tools: the seed "
    "phrase and keys (Keychain), the signer and the wallet's state are never touched directly, and no "
    "other program signs or sends a transaction.")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def bypass(tool: str, args, wallet: bool = False, state_dir: str | None = None) -> str | None:
    """A block message when a call would go around the web3 tools, else None."""
    if tool not in TERMINAL_TOOLS and tool not in FILE_TOOLS:
        return None
    texts = list(_strings(args if isinstance(args, dict) else {}))
    patterns = [(_READ, READ_MESSAGE)] + ([(_WALLET, WALLET_MESSAGE)] if wallet else [])
    for text in texts:
        if tool in FILE_TOOLS and tool == "read_file" and _SOURCE_READ.search(text.strip()):
            continue  # reading the plugins' own source is harmless
        if wallet and state_dir and state_dir in text:
            return WALLET_MESSAGE
        for pattern, message in patterns:
            if pattern.search(text):
                return message
    return None
