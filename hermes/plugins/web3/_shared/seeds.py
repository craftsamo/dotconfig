"""A new Hermes wallet: its spec, approval card and Keychain comment (docs/web3.md "New wallets").

Used by the signer in the engine venv. A spec is what the user approves — name, project, scope,
word count and purpose — normalized against the Keychain's listing (names and metadata only, no
value read): the name has HERMES as one of its words, no item of that name exists in the project
(an existing secret is never overwritten), and a project left out is the one already holding the
Hermes wallets (a scope named like the project is the shared layer, as ``secret`` stores it). The
card shows every piece of metadata the item will get; the seed phrase is made
only after approval, and the comment gains the word count, the date and account #0's addresses then.
The spec's digest ties the approved card to the item that is stored.
"""

from __future__ import annotations

import hashlib
import html
import json
import re

from rpc import ChainError
import keychain

KIND = "MNEMONIC PHRASE"
STRENGTH = {12: 128, 24: 256}
DEFAULT_WORDS = 24
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")          # secret's own rule for a name
LAYER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")       # projects and scopes
PURPOSE_MAX = 120
PURPOSE_SHORT = 80
CARD_BUDGET = 480          # Telegram cuts an approval card's reason at 500 escaped UTF-16 units
SHORT_BUDGET = 290         # Discord cuts it at 300
CREATOR = "Hermes"


def _one_line(text) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())


def _clip(text: str, size: int) -> str:
    return text if len(text) <= size else text[:size - 1] + "…"


def _units(text: str) -> int:
    return len(html.escape(text).encode("utf-16-le")) // 2


def _identifier(value, what: str) -> str:
    if not isinstance(value, str) or not LAYER.match(value.strip()):
        raise ChainError(f"{what} must be letters, digits, '_', '.' or '-' (at most 64), starting with a letter "
                         "or digit")
    return value.strip()


def hermes_projects(inventory: dict[str, list[dict] | None]) -> list[str]:
    """Projects that hold a Hermes wallet (a seed phrase or key with HERMES in its name)."""
    return sorted(project for project, rows in inventory.items() if rows and any(
        keychain.kind_of(row["label"]) and keychain.use_of(row["name"]) == "sign" for row in rows))


def normalize(args: dict, inventory: dict[str, list[dict] | None]) -> dict:
    """The spec to approve and store, or a ChainError saying what to fix. ``inventory`` maps each
    project to its listing (None when it could not be listed)."""
    name = args.get("name").strip() if isinstance(args.get("name"), str) else None
    if not name or not NAME.match(name):
        raise ChainError("name must be letters, digits and '_' (at most 64), not starting with a digit, like "
                         "HERMES_TESTNET")
    if keychain.use_of(name) != "sign":
        raise ChainError("a Hermes wallet's name has HERMES as one of its words, like HERMES_TESTNET or "
                         "PROJECTX_HERMES; any other name would be watch-only")
    words = args.get("words", DEFAULT_WORDS)
    if words is None:
        words = DEFAULT_WORDS
    if isinstance(words, bool) or words not in STRENGTH:
        raise ChainError("words must be 12 or 24")
    purpose = _one_line(args.get("purpose"))
    if not purpose:
        raise ChainError("purpose is required: what this wallet is for, in one line, like 'Testnet checks for "
                         "the web3 wallet'; it becomes the item's comment")
    if len(purpose) > PURPOSE_MAX:
        raise ChainError(f"purpose is {len(purpose)} characters; keep it to {PURPOSE_MAX}")
    scope = args.get("scope")
    scope = None if scope in (None, "", "Shared", "shared") else _identifier(scope, "scope")
    project = args.get("project")
    if project in (None, ""):
        held = hermes_projects(inventory)
        if len(held) != 1:
            why = "no project holds a Hermes wallet yet" if not held else \
                "Hermes wallets are in several projects (" + ", ".join(held) + ")"
            raise ChainError(f"project is required: {why}; name the project to store it in")
        project = held[0]
    project = _identifier(project, "project")
    if scope == project:
        scope = None  # secret stores a scope named like its project in the shared layer
    if project not in inventory:
        raise ChainError(f"there is no project {project!r} in the Keychain; the user creates it, or names an "
                         "existing one")
    rows = inventory[project]
    if rows is None:
        raise ChainError(f"project {project!r} could not be listed; nothing was created")
    taken = [row for row in rows if row["name"] == name]
    if taken:
        where = ", ".join(row["scope"] or "Shared" for row in taken)
        raise ChainError(f"project {project} already has a secret named {name} ({where}); an existing secret is "
                         "never overwritten, so choose another name")
    return {"name": name, "project": project, "scope": scope, "words": words, "purpose": purpose}


def digest(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def source(spec: dict) -> str:
    return keychain.source_id(spec)


def _tail(spec: dict, today: str) -> str:
    return f"{spec['words']} words · created {today} by {CREATOR}"


def comment(spec: dict, today: str, evm: str, solana: str) -> str:
    """The item's comment: the purpose, then what the wallet is, then account #0 on each family."""
    return f"{spec['purpose']} · {_tail(spec, today)} · EVM#0 {evm} · SOL#0 {solana}"


def card(spec: dict, today: str) -> str:
    """The detailed approval card: every piece of metadata the Keychain item will carry."""
    return "\n".join([
        "Create: a new Hermes wallet (seed phrase)",
        f"Name: {spec['name']}",
        f"Project: {spec['project']}({spec['scope'] or 'Shared'})",
        f"Kind: {KIND} · ENV: no (never injected)",
        f"Seed: {spec['words']} words, made after approval; kept only in the Keychain, never shown",
        f"Comment: {spec['purpose']}",
        f"  + {_tail(spec, today)} · EVM#0 and SOL#0 addresses",
    ])


def card_short(spec: dict) -> str:
    return "\n".join([
        f"Create Hermes wallet {spec['name']} in {spec['project']}({spec['scope'] or 'Shared'})",
        f"{KIND}, {spec['words']} words, ENV no; the seed is never shown",
        f"Comment: {_clip(spec['purpose'], PURPOSE_SHORT)}",
    ])


def cards(spec: dict, today: str) -> tuple[str, str]:
    """(detailed, compact); the compact one stands in where the detailed one would be cut."""
    short = card_short(spec)
    if _units(short) > SHORT_BUDGET:
        short = short.rsplit("\n", 1)[0]  # long names: the purpose line goes, the facts stay
    detailed = card(spec, today)
    return (detailed if _units(detailed) <= CARD_BUDGET else short), short


def generate(words: int) -> str:
    from mnemonic import Mnemonic
    return Mnemonic("english").generate(strength=STRENGTH[words])
