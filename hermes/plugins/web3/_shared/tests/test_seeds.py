"""New Hermes wallets end to end in the web3 venv, against a stand-in ``secret`` CLI (a JSON file, no
Keychain): the card shows every piece of metadata, the stored item matches the approved spec, and the
seed phrase never leaves the signer."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

HERMES = Path(__file__).resolve().parents[4]
PYTHON = HERMES / "local" / "web3" / "venv" / "bin" / "python"
SIGNER = HERMES / "plugins" / "web3" / "_shared" / "signer.py"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

FAKE_SECRET = '''#!{python}
"""A stand-in for the secret CLI: items in a JSON file; MODE in the file next to it bends one behaviour."""
import json, re, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
store = here / "store.json"
mode = (here / "mode").read_text().strip() if (here / "mode").exists() else ""
items = json.loads(store.read_text()) if store.exists() else []
args = sys.argv[1:]

def opt(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default

if args[0] == "projects":
    print("\\n".join(sorted({{i["project"] for i in items}} | {{"empty"}})))
elif args[0] == "ls":
    project = opt("-p")
    if mode == "ls-fail" and any(i["name"].startswith("HERMES_T") for i in items):
        sys.exit(1)
    print("%-24s%-14s%-18s%-18s%-5s%s" % ("NAME", "SCOPE", "KIND", "MODIFIED", "ENV", "COMMENT"))
    for i in items:
        if i["project"] == project:
            print("%-24s%-14s%-18s%-18s%-5s%s" % (i["name"], i["scope"] or "Shared", i["kind"], "2026-10-08 10:00",
                                                   i["env"], i["comment"]))
elif args[0] == "get":
    scope = opt("--scope")
    for i in items:
        if i["name"] == args[1] and i["project"] == opt("-p") and i["scope"] == scope:
            print(i["value"])
            break
    else:
        sys.exit(1)
elif args[0] == "set":
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", args[1]):
        sys.exit(2)
    scope = opt("--scope")
    scope = None if scope == opt("-p") else scope  # secret's rule: --scope <project> is the shared layer
    if mode == "race":  # someone else stores the name between the check and this write
        items.append({{"project": opt("-p"), "scope": scope, "name": args[1], "kind": "MNEMONIC", "comment": "theirs",
                      "env": "no", "value": "legal winner thank year wave sausage worth useful legal winner thank "
                                            "yellow"}})
        store.write_text(json.dumps(items))
    if mode == "fail" or ("--new" in args and any(
            i["name"] == args[1] and i["project"] == opt("-p") and i["scope"] == scope for i in items)):
        sys.exit(1)
    value = sys.stdin.readline().rstrip("\\n")
    assert "--stdin" in args and "--new" in args and value not in " ".join(args)
    if mode == "corrupt":
        value = "abandon " * 11 + "about"
    items.append({{"project": opt("-p"), "scope": scope, "name": args[1], "kind": opt("-D"),
                  "comment": opt("-j", ""), "env": "yes" if mode == "env" or "--no-env" not in args else "no",
                  "value": value}})
    if mode == "slow":
        time.sleep(5)  # cut off before the write lands (in the real CLI, it may still land later)
    store.write_text(json.dumps(items))
'''

MAIN_WORDS = "test test test test test test test test test test test junk"
EXISTING = [
    {"project": "work", "scope": None, "name": "HERMES_MAIN", "kind": "MNEMONIC", "comment": "main", "env": "no",
     "value": MAIN_WORDS},
    {"project": "work", "scope": None, "name": "EXCHANGE_API_KEY", "kind": "API KEY", "comment": "", "env": "yes",
     "value": "k"},
    {"project": "other", "scope": None, "name": "TEAM_SEED", "kind": "MNEMONIC", "comment": "", "env": "yes",
     "value": "abandon " * 11 + "about"},
]


@pytest.fixture
def keychain(tmp_path):
    folder = tmp_path / "keychain"
    folder.mkdir()
    cli = folder / "secret"
    cli.write_text(FAKE_SECRET.format(python=PYTHON))
    cli.chmod(0o755)
    (folder / "store.json").write_text(json.dumps(EXISTING))
    return folder


def stored(keychain) -> list[dict]:
    return json.loads((keychain / "store.json").read_text())


def signer(tmp_path, keychain, op, **fields) -> dict:
    payload = {"op": op, "state": str(tmp_path / "state"), "_secret": str(keychain / "secret"),
               "_secret_timeout": 2, **fields}
    proc = subprocess.run([str(PYTHON), str(SIGNER)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=120, env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8",
                                            "WEB3_ENGINE_TEST": "1"})
    for item in stored(keychain):
        if item["value"] != "k":
            assert item["value"] not in proc.stdout, "a seed phrase leaked"
    return json.loads(proc.stdout)


SPEC = {"name": "HERMES_TESTNET", "purpose": "Testnet checks for the web3 wallet"}


def create(tmp_path, keychain, **spec) -> dict:
    """What the plugin does: the hook's check (the card), then the creation under its digest."""
    spec = {**SPEC, **spec}
    checked = signer(tmp_path, keychain, "wallet_check", **spec)
    if not checked["ok"]:
        return checked
    return signer(tmp_path, keychain, "wallet_create", digest=checked["data"]["digest"], **spec)


def test_the_card_shows_every_piece_of_metadata_and_the_project_comes_from_the_hermes_wallets(tmp_path, keychain):
    reply = signer(tmp_path, keychain, "wallet_check", **SPEC)
    assert reply["ok"], reply
    data = reply["data"]
    assert data["wallet"] == {"name": "HERMES_TESTNET", "project": "work", "scope": None, "words": 24,
                              "purpose": "Testnet checks for the web3 wallet"}
    card = data["card"]
    for line in ("Name: HERMES_TESTNET", "Project: work(Shared)", "Kind: MNEMONIC PHRASE · ENV: no",
                 "Seed: 24 words, made after approval", "never shown", "Comment: Testnet checks for the web3 wallet",
                 "24 words · created", "by Hermes · EVM#0 and SOL#0 addresses"):
        assert line in card, line
    assert "HERMES_TESTNET in work(Shared)" in data["card_short"]
    assert stored(keychain) == EXISTING  # checking stores nothing


def test_the_approved_wallet_is_stored_as_shown_and_found_as_a_hermes_wallet(tmp_path, keychain):
    reply = create(tmp_path, keychain, scope="testnet")
    assert reply["ok"], reply
    data = reply["data"]
    new = stored(keychain)[-1]
    assert (new["project"], new["scope"], new["name"], new["kind"], new["env"]) == \
        ("work", "testnet", "HERMES_TESTNET", "MNEMONIC PHRASE", "no")
    assert len(new["value"].split()) == 24
    evm, sol = data["addresses"]["evm"], data["addresses"]["solana"]
    assert new["comment"].startswith("Testnet checks for the web3 wallet · 24 words · created ")
    assert new["comment"].endswith(f"by Hermes · EVM#0 {evm} · SOL#0 {sol}")
    assert data["account"] == "work/testnet/HERMES_TESTNET#0" and data["comment"] == new["comment"]
    listed = signer(tmp_path, keychain, "accounts", count=1)["data"]["accounts"]
    row = next(r for r in listed if r["account"] == data["account"])
    assert (row["use"], row["env"], row["evm"], row["solana"]) == ("sign", "no", evm, sol)
    assert row["memo"].startswith("Testnet checks for the web3 wallet")
    rows = [json.loads(line) for line in (tmp_path / "state" / "wallets.jsonl").read_text().splitlines()]
    assert [r["outcome"] for r in rows] == ["unknown", "created"] and all("value" not in r for r in rows)


def test_twelve_words_on_request(tmp_path, keychain):
    assert create(tmp_path, keychain, words=12)["ok"]
    assert len(stored(keychain)[-1]["value"].split()) == 12


def test_a_wallet_other_than_the_approved_one_is_never_made(tmp_path, keychain):
    checked = signer(tmp_path, keychain, "wallet_check", **SPEC)["data"]
    reply = signer(tmp_path, keychain, "wallet_create", digest=checked["digest"], **{**SPEC, "scope": "elsewhere"})
    assert reply["ok"] is False and "not the wallet that was approved" in reply["error"]
    reply = signer(tmp_path, keychain, "wallet_create", **SPEC)
    assert reply["ok"] is False and stored(keychain) == EXISTING


@pytest.mark.parametrize("spec, message", [
    ({"name": "TESTNET_WALLET"}, "HERMES as one of its words"),
    ({"name": "HERMES MAIN"}, "name must be"),
    ({"name": "HERMES-TESTNET"}, "name must be"),
    ({"name": "1_HERMES"}, "name must be"),
    ({"name": "EXCHANGE_HERMES", "project": "nowhere"}, "no project 'nowhere'"),
    ({"name": "HERMES_MAIN"}, "already has a secret named HERMES_MAIN"),
    ({"words": 18}, "words must be 12 or 24"),
    ({"purpose": " \n "}, "purpose is required"),
    ({"purpose": "x" * 121}, "keep it to 120"),
    ({"scope": "../x"}, "scope must be"),
])
def test_what_is_refused_before_any_card(tmp_path, keychain, spec, message):
    reply = signer(tmp_path, keychain, "wallet_check", **{**SPEC, **spec})
    assert reply["ok"] is False and message in reply["error"], reply


def test_an_existing_name_is_refused_in_any_layer(tmp_path, keychain):
    assert create(tmp_path, keychain, scope="testnet")["ok"]
    reply = signer(tmp_path, keychain, "wallet_check", **SPEC)
    assert reply["ok"] is False and "already has a secret named HERMES_TESTNET (testnet)" in reply["error"]


def test_the_project_is_asked_for_when_the_hermes_wallets_do_not_name_one(tmp_path, keychain):
    (keychain / "store.json").write_text(json.dumps(EXISTING[1:]))
    reply = signer(tmp_path, keychain, "wallet_check", **SPEC)
    assert reply["ok"] is False and "no project holds a Hermes wallet yet" in reply["error"]
    assert signer(tmp_path, keychain, "wallet_check", project="other", **SPEC)["ok"]
    (keychain / "store.json").write_text(json.dumps(EXISTING + [{**EXISTING[0], "project": "other"}]))
    reply = signer(tmp_path, keychain, "wallet_check", **SPEC)
    assert reply["ok"] is False and "several projects (other, work)" in reply["error"]


def test_a_refused_store_creates_nothing(tmp_path, keychain):
    (keychain / "mode").write_text("fail")
    reply = create(tmp_path, keychain)
    assert reply["ok"] is False and "nothing was created" in reply["error"] and stored(keychain) == EXISTING


def test_a_scope_named_like_the_project_is_the_shared_layer_on_the_card_too(tmp_path, keychain):
    reply = create(tmp_path, keychain, scope="work")
    assert reply["ok"], reply
    assert reply["data"]["scope"] == "Shared" and stored(keychain)[-1]["scope"] is None


@pytest.mark.parametrize("mode, problem", [("env", "ENV yes"), ("corrupt", "not the one made here"),
                                           ("slow", "did not answer in time, and it is not listed yet"),
                                           ("ls-fail", "could not be listed back")])
def test_a_wallet_that_may_exist_is_never_called_absent(tmp_path, keychain, mode, problem):
    (keychain / "mode").write_text(mode)
    reply = create(tmp_path, keychain)
    assert reply["ok"] is False and problem in reply["error"], reply
    assert "nothing was created" not in reply["error"] and "Do not fund it" in reply["error"]
    assert "secret show HERMES_TESTNET -p work --shared" in reply["error"]
    assert "secret rm HERMES_TESTNET -p work --shared" in reply["error"]
    assert "only if its comment ends in EVM#0 0x" in reply["error"]
    rows = [json.loads(line) for line in (tmp_path / "state" / "wallets.jsonl").read_text().splitlines()]
    assert rows[-1]["outcome"] == "unverified"  # counted against the hourly cap


def test_a_name_taken_during_the_write_is_left_alone(tmp_path, keychain):
    (keychain / "mode").write_text("race")
    reply = create(tmp_path, keychain)
    assert reply["ok"] is False and "nothing was created" in reply["error"]
    assert "not this wallet, and it was left untouched" in reply["error"] and "secret rm" not in reply["error"]
    assert stored(keychain)[-1]["comment"] == "theirs"


def test_three_new_wallets_an_hour(tmp_path, keychain):
    for n in range(3):
        assert create(tmp_path, keychain, name=f"HERMES_T{n}")["ok"]
    reply = signer(tmp_path, keychain, "wallet_check", **{**SPEC, "name": "HERMES_T3"})
    assert reply["ok"] is False and "3 new wallets in the last hour" in reply["error"]
    assert not (tmp_path / "state" / "ledger.jsonl").exists()  # the transfer cap is untouched
