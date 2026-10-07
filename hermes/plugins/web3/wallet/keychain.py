"""Find the user's wallet secrets in the Keychain by their kind label (docs/web3.md "Accounts").

Run inside the signer only. ``secret projects`` and ``secret ls -p <project> --long`` list names,
scopes and kinds without reading a value; only items whose kind is a seed phrase (``MNEMONIC``) or
a private key (``PRIVATE_KEY``) are then read with ``secret get``, stdin closed. No other secret's
value is ever read. Without the ``secret`` CLI the wallet is unavailable.

The kind says what an item is; its name says whether Hermes may sign with it: a name with HERMES
as one of its ``_`` / ``-`` separated words (``HERMES_MAIN``, ``PROJECTX_HERMES``) is a Hermes wallet
("sign"), any other name is watch-only ("watch"), so a project's own wallets never sign by accident.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

SECRET = Path.home() / ".config" / "bin" / "secret"
TIMEOUT = 20
KINDS = {"mnemonic": "seed", "seed phrase": "seed", "private key": "key", "privatekey": "key"}
COLUMNS = ("NAME", "SCOPE", "KIND", "MODIFIED")
MARK = "hermes"
UNAVAILABLE = ("the secret CLI is not available on this machine, so the wallet cannot find seed phrases or "
               "keys; it needs ~/.config/bin/secret")


class KeychainError(Exception):
    pass


def kind_of(label: str) -> str | None:
    """'seed', 'key' or None for a secret's kind label, however it is spelled."""
    return KINDS.get(" ".join(label.lower().replace("_", " ").replace("-", " ").split()))


def use_of(name: str) -> str:
    """'sign' for a name with HERMES as one of its words, else 'watch'."""
    return "sign" if MARK in re.split(r"[_\-\s.]+", (name or "").lower()) else "watch"


def _run(args: list[str]) -> str:
    if not SECRET.exists():
        raise KeychainError(UNAVAILABLE)
    try:
        proc = subprocess.run([str(SECRET), *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise KeychainError("the Keychain did not answer in time") from None
    if proc.returncode != 0:
        raise KeychainError(f"secret {args[0]} failed")
    return proc.stdout


def parse_listing(project: str, text: str) -> list[dict]:
    """Wallet items of one ``secret ls --long`` listing (columns are space-padded under a header)."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("NAME"):
        return []
    header = lines[0]
    starts = [header.find(column) for column in COLUMNS]
    if min(starts) < 0:
        return []
    comment_at = header.find("COMMENT")
    found = []
    for row in lines[1:]:
        name = row[starts[0]:starts[1]].strip()
        scope = row[starts[1]:starts[2]].strip()
        label = row[starts[2]:starts[3]].strip()
        memo = row[comment_at:].strip() if comment_at > 0 else ""
        role = kind_of(label)
        if name and role:
            found.append({"project": project, "scope": None if scope in ("", "Shared") else scope,
                          "name": name, "label": label, "role": role, "use": use_of(name), "memo": memo or None})
    return found


def source_id(item: dict) -> str:
    return "/".join(part for part in (item["project"], item.get("scope"), item["name"]) if part)


def discover() -> list[dict]:
    """Every wallet-labelled seed phrase and private key in the Keychain, with its value."""
    items = []
    for project in _run(["projects"]).split():
        try:
            items += parse_listing(project, _run(["ls", "-p", project, "--long"]))
        except KeychainError:
            continue  # one unreadable project does not hide the others
    for item in items:
        layer = ["--scope", item["scope"]] if item["scope"] else ["--shared"]
        try:
            item["value"] = _run(["get", item["name"], "-p", item["project"], *layer]).strip()
        except KeychainError:
            item["value"] = None
        item["id"] = source_id(item)
    return items
