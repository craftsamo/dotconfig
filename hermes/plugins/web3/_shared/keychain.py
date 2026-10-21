"""Find the user's wallet secrets in the Keychain by their kind label (docs/web3.md "Accounts").

Run inside the signer only. ``secret projects`` and ``secret ls -p <project> --json`` list names,
scopes and kinds without reading a value; only items whose kind is a seed phrase (``MNEMONIC``) or
a private key (``PRIVATE_KEY``) are then read with ``secret get``, stdin closed. No other secret's
value is ever read. Without the ``secret`` CLI the wallet is unavailable.

The listing is read as JSON, never as the ``--long`` table: that one is for people and changes
with them. Items of a stage are left out — a wallet lives in a stage-less layer, which is where
``store`` writes and ``read`` reads.

The kind says what an item is; its name says whether Hermes may sign with it: a name with HERMES
as one of its ``_`` / ``-`` separated words (``HERMES_MAIN``, ``PROJECTX_HERMES``) is a Hermes wallet
("sign"), any other name is watch-only ("watch"), so a project's own wallets never sign by accident.
The listing's ``env`` says whether ``secret env`` (and so every injected environment) carries the
item; a Hermes wallet should be stored ``--no-env``.

``store`` writes one new item through ``secret set --new --stdin`` (create-only; the value on stdin,
never in argv), and ``read`` reads one back; both are for a new Hermes wallet only (``seeds.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

SECRET = Path.home() / ".config" / "bin" / "secret"
TIMEOUT = 20
KINDS = {"mnemonic": "seed", "mnemonic phrase": "seed", "seed phrase": "seed", "private key": "key",
         "privatekey": "key"}
MARK = "hermes"
UNAVAILABLE = ("the secret CLI is not available on this machine, so the wallet cannot find seed phrases or "
               "keys; it needs ~/.config/bin/secret")


class KeychainError(Exception):
    pass


class KeychainTimeout(KeychainError):
    """The ``secret`` call was cut off: what it was doing may still have happened."""


def kind_of(label: str) -> str | None:
    """'seed', 'key' or None for a secret's kind label, however it is spelled."""
    return KINDS.get(" ".join(label.lower().replace("_", " ").replace("-", " ").split()))


def use_of(name: str) -> str:
    """'sign' for a name with HERMES as one of its words, else 'watch'."""
    return "sign" if MARK in re.split(r"[_\-\s.]+", (name or "").lower()) else "watch"


def _run(args: list[str], value: str | None = None) -> str:
    if not SECRET.exists():
        raise KeychainError(UNAVAILABLE)
    try:
        # errors="replace": a stray non-UTF-8 byte in a listed comment must not hide the project
        if value is None:
            proc = subprocess.run([str(SECRET), *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  errors="replace", timeout=TIMEOUT)
        else:
            proc = subprocess.run([str(SECRET), *args], input=value + "\n", capture_output=True, text=True,
                                  errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise KeychainTimeout("the Keychain did not answer in time") from None
    if proc.returncode != 0:
        raise KeychainError(f"secret {args[0]} failed")
    return proc.stdout


def parse_rows(project: str, text: str) -> list[dict]:
    """Every stage-less item of one ``secret ls --json`` listing, of any kind, values never included.
    Anything that is not such a listing yields nothing."""
    try:
        listing = json.loads(text)
    except ValueError:
        return []
    if not isinstance(listing, list):
        return []
    found = []
    for item in listing:
        if not isinstance(item, dict) or item.get("stage"):
            continue
        name = item.get("name") or ""
        if name:
            found.append({"project": project, "scope": item.get("scope") or None,
                          "name": name, "label": item.get("kind") or "", "memo": item.get("comment") or None,
                          # "no" when stored --no-env; "yes" or unknown means injectable
                          "env": "no" if item.get("env") == "no" else "yes"})
    return found


def parse_listing(project: str, text: str) -> list[dict]:
    """Wallet items of one ``secret ls --json`` listing."""
    found = []
    for row in parse_rows(project, text):
        role = kind_of(row["label"])
        if role:
            found.append({"project": project, "scope": row["scope"], "name": row["name"], "label": row["label"],
                          "role": role, "use": use_of(row["name"]), "memo": row["memo"], "env": row["env"]})
    return found


def projects() -> list[str]:
    return _run(["projects"]).split()


def rows(project: str) -> list[dict]:
    """Every item of a project, names and metadata only."""
    return parse_rows(project, _run(["ls", "-p", project, "--json"]))


def _layer(scope: str | None) -> list[str]:
    return ["--scope", scope] if scope else ["--shared"]


def store(name: str, project: str, scope: str | None, kind: str, comment: str, value: str) -> None:
    """A new item, kept out of ``secret env``; the value goes on stdin. ``--new`` makes it create-only:
    ``secret`` (and ``security`` under it) refuses an item that already exists, never overwriting it."""
    _run(["set", name, "-p", project, *(["--scope", scope] if scope else []), "-D", kind, "-j", comment,
          "--no-env", "--new", "--stdin"], value=value)


def read(name: str, project: str, scope: str | None) -> str:
    return _run(["get", name, "-p", project, *_layer(scope)]).strip()


def source_id(item: dict) -> str:
    return "/".join(part for part in (item["project"], item.get("scope"), item["name"]) if part)


def discover(sign_only: bool = False) -> list[dict]:
    """Every wallet-labelled seed phrase and private key in the Keychain, with its value; with
    sign_only, the Hermes wallets alone (watch-only values are then never read)."""
    items = []
    for project in projects():
        try:
            items += parse_listing(project, _run(["ls", "-p", project, "--json"]))
        except KeychainError:
            continue  # one unreadable project does not hide the others
    if sign_only:
        items = [item for item in items if item["use"] == "sign"]
    for item in items:
        try:
            item["value"] = read(item["name"], item["project"], item["scope"])
        except KeychainError:
            item["value"] = None
        item["id"] = source_id(item)
    return items
