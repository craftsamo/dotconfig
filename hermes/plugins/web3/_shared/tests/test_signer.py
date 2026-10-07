"""The signer end to end in the web3 venv, against a fake JSON-RPC server (no network, no Keychain).

The wallet secrets are public test vectors (Hardhat's mnemonic, the BIP39 'abandon … about' vector and
throwaway keys), passed as ``_sources`` under ``WEB3_ENGINE_TEST`` in the shape ``keychain.discover``
returns. Signed transactions are decoded back with the chain engine's own ``decode``.
"""

from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import subprocess
import threading

import pytest

HERMES = Path(__file__).resolve().parents[4]
PYTHON = HERMES / "local" / "web3" / "venv" / "bin" / "python"
SIGNER = HERMES / "plugins" / "web3" / "_shared" / "signer.py"
READER = HERMES / "plugins" / "web3" / "_shared" / "reader.py"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

MAIN_WORDS = "test test test test test test test test test test test junk"
WORK_WORDS = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
EVM_KEY = "0x" + "4c" * 32  # a throwaway key, nobody's funds
TEAM_WORDS = "legal winner thank year wave sausage worth useful legal winner thank yellow"
MAIN, WORK, KEY = "hermes/HERMES_MAIN", "projectx/ops/PROJECTX-HERMES", "hermes/HERMES_DEPLOYER"
TEAM = "team/PROD_MNEMONIC"  # no HERMES in the name: watch-only


def item(source, role, value, memo=None):
    """A source as keychain.discover returns it; whether it signs follows from its name."""
    project, *rest = source.split("/")
    return {"id": source, "project": project, "scope": rest[0] if len(rest) == 2 else None, "name": rest[-1],
            "label": "MNEMONIC" if role == "seed" else "PRIVATE_KEY", "role": role, "value": value, "memo": memo}


SOURCES = [
    item(MAIN, "seed", MAIN_WORDS, memo="main ops wallet"),
    item(WORK, "seed", WORK_WORDS),
    item(KEY, "key", EVM_KEY),
    item(TEAM, "seed", TEAM_WORDS),
    item("hermes/HERMES_BROKEN", "seed", "not a real phrase at all"),
    item("other/COPY", "seed", "  " + MAIN_WORDS + " "),
]
OPS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"        # MAIN #0
SPARE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"      # MAIN #1
WORK0 = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"      # WORK #0
STRANGER = "0x5e5E5e5e5E5e5E5E5e5E5E5e5e5E5E5E5e5E5E5e"
USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
SOL_OPS = "oeYf6KAJkLYhBuR8CiGc6L4D4Xtfepr85fuDgA9kq96"     # MAIN #0
SOL_SPARE = "AqynRZwvVqUPRwRJXvm6odUb3t93fDjnWe3p6BeuUFxD"  # MAIN #1
SOL_STRANGER = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
DEV_USDC = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

FAKE = {"broadcast": "ok", "sent": [], "token_ata_exists": False, "symbol": "USDC"}


def word(value: int) -> str:
    return format(value, "064x")


def abi_string(text: str) -> str:
    raw = text.encode()
    return "0x" + word(32) + word(len(raw)) + raw.hex().ljust(64, "0")


def handle(method: str, params: list):
    if method == "eth_getBalance":
        return hex(10 ** 18), None
    if method == "eth_getCode":
        return ("0x6080604052" if params[0].lower() == USDC.lower() else "0x"), None
    if method == "eth_call":
        data = params[0].get("data", "")
        if params[0].get("to", "").lower() == "0x420000000000000000000000000000000000000f":
            return "0x" + word(10 ** 12), None  # GasPriceOracle.getL1Fee
        if data.startswith("0x70a08231"):
            return "0x" + word(500 * 10 ** 6), None
        if data == "0x95d89b41":
            return abi_string(FAKE["symbol"]), None
        if data == "0x313ce567":
            return "0x" + word(6), None
        if data.startswith("0xa9059cbb"):
            return "0x" + word(1), None
        return "0x", None
    if method == "eth_estimateGas":
        return ("0x5208" if params[0].get("data") in (None, "0x") else hex(50_000)), None
    if method == "eth_getBlockByNumber":
        return {"number": "0x10", "baseFeePerGas": hex(10 ** 9)}, None
    if method == "eth_maxPriorityFeePerGas":
        return hex(10 ** 9), None
    if method == "eth_getTransactionCount":
        return "0x4", None
    if method in ("eth_sendRawTransaction", "sendTransaction"):
        if FAKE["broadcast"] == "reject":
            return None, {"code": -32000, "message": "nonce too low"}
        FAKE["sent"].append(params[0])
        return ("0x" + "ab" * 32 if method == "eth_sendRawTransaction" else "5" * 88), None
    # Solana
    if method == "getAccountInfo":
        address = params[0]
        if address == DEV_USDC:
            return {"value": {"owner": TOKEN, "executable": False, "lamports": 10 ** 7,
                              "data": {"parsed": {"type": "mint", "info": {"decimals": 6}}}}}, None
        if address in (SOL_OPS, SOL_SPARE):
            return {"value": {"owner": "11111111111111111111111111111111", "executable": False,
                              "lamports": 5 * 10 ** 9, "data": ["", "base64"]}}, None
        if FAKE["token_ata_exists"]:
            return {"value": {"owner": TOKEN, "executable": False, "lamports": 2039280,
                              "data": {"parsed": {"type": "account", "info": {}}}}}, None
        return {"value": None}, None
    if method == "getMultipleAccounts":
        return {"value": [{"lamports": 5 * 10 ** 9} if a == SOL_OPS else None for a in params[0]]}, None
    if method == "getMinimumBalanceForRentExemption":
        return (890880 if params[0] == 0 else 2039280), None
    if method == "getBalance":
        return {"value": 5 * 10 ** 9}, None
    if method == "getTokenAccountBalance":
        return {"value": {"amount": str(100 * 10 ** 6), "decimals": 6, "uiAmountString": "100"}}, None
    if method == "simulateTransaction":
        return {"value": {"err": None, "logs": []}}, None
    if method == "getLatestBlockhash":
        return {"value": {"blockhash": "EkSnNWid2cvwEVnVx9aBqawnmiCNiDgp3gUdkDPTKN1N", "lastValidBlockHeight": 1}}, None
    return None, {"code": -32601, "message": f"no fake for {method}"}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        items = body if isinstance(body, list) else [body]
        if FAKE["broadcast"] == "drop" and any(i["method"] in ("eth_sendRawTransaction", "sendTransaction")
                                               for i in items):
            self.close_connection = True
            return
        replies = []
        for item in items:
            result, error = handle(item["method"], item.get("params") or [])
            replies.append({"jsonrpc": "2.0", "id": item["id"], **({"error": error} if error else {"result": result})})
        out = json.dumps(replies if isinstance(body, list) else replies[0]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def endpoint():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def fresh():
    FAKE.update(broadcast="ok", sent=[], token_ata_exists=False, symbol="USDC")


def _env(tmp_path: Path) -> dict:
    return {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "WEB3_ENGINE_TEST": "1"}


def signer(tmp_path: Path, endpoint: str, op: str, **fields) -> dict:
    payload = {"op": op, "state": str(tmp_path / "state"), "_sources": fields.pop("_sources", SOURCES),
               "_rpc": endpoint, "_offline": True, **fields}
    proc = subprocess.run([str(PYTHON), str(SIGNER)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=120, env=_env(tmp_path))
    for leaked in ("test test test", "abandon abandon", "legal winner", "4c4c4c4c", "real phrase"):
        assert leaked not in proc.stdout, f"a secret leaked: {leaked}"
    return json.loads(proc.stdout)


def send(tmp_path: Path, endpoint: str, quote_id: str, approval: str, mac: str | None = None, **fields) -> dict:
    """What the plugin does: verify the quote (the hook), then send it with the approved MAC."""
    if mac is None:
        verified = signer(tmp_path, endpoint, "verify", quote=quote_id, **fields)
        if not verified["ok"]:
            return verified
        mac = verified["data"]["mac"]
    return signer(tmp_path, endpoint, "send", quote=quote_id, approval=approval, mac=mac, **fields)


def decode(tmp_path: Path, chain: str, data: str) -> dict:
    payload = {"action": "decode", "chain": chain, "data": data, "_offline": True}
    proc = subprocess.run([str(PYTHON), str(READER)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=60, env=_env(tmp_path))
    return json.loads(proc.stdout)["data"]


def ledger(tmp_path: Path) -> list[dict]:
    path = tmp_path / "state" / "ledger.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def quote_file(tmp_path: Path, quote_id: str) -> Path:
    return tmp_path / "state" / "quotes" / f"{quote_id}.json"


def remac(quote: dict, words: str) -> str:
    seed = hashlib.pbkdf2_hmac("sha512", words.encode(), b"mnemonic", 2048)
    key = hashlib.sha256(b"hermes-web3-quote\x00" + seed).digest()
    body = json.dumps({k: v for k, v in quote.items() if k not in ("mac", "consumed")}, sort_keys=True,
                      ensure_ascii=False)
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


def quote(tmp_path, endpoint, **fields) -> dict:
    reply = signer(tmp_path, endpoint, "quote", **{"account": f"{MAIN}#0", "chain": "sepolia", **fields})
    assert reply["ok"], reply
    return reply["data"]


# --- accounts -----------------------------------------------------------------------------------

def test_accounts_list_every_labelled_secret_with_its_metadata(tmp_path, endpoint):
    data = signer(tmp_path, endpoint, "accounts", count=2, chain="sepolia")["data"]
    rows = {row["account"]: row for row in data["accounts"]}
    assert list(rows) == [f"{MAIN}#0", f"{MAIN}#1", f"{WORK}#0", f"{WORK}#1", f"{TEAM}#0", f"{TEAM}#1", KEY]
    assert rows[f"{MAIN}#0"] == {"account": f"{MAIN}#0", "project": "hermes", "scope": None, "name": "HERMES_MAIN",
                                 "label": "MNEMONIC", "kind": "seed", "use": "sign", "memo": "main ops wallet",
                                 "env": "yes", "index": 0, "evm": OPS, "solana": SOL_OPS, "balance": "1 ETH"}
    assert rows[f"{WORK}#0"]["project"] == "projectx" and rows[f"{WORK}#0"]["scope"] == "ops"
    assert rows[f"{WORK}#0"]["use"] == "sign"
    assert rows[f"{MAIN}#1"]["evm"] == SPARE and rows[f"{WORK}#0"]["evm"] == WORK0
    assert rows[f"{TEAM}#0"]["use"] == "watch" and rows[f"{TEAM}#0"]["label"] == "MNEMONIC"
    assert rows[KEY]["kind"] == "key" and "solana" not in rows[KEY]


def test_bad_and_duplicate_secrets_are_skipped_keeping_the_hermes_copy(tmp_path, endpoint):
    data = signer(tmp_path, endpoint, "accounts", count=1)["data"]
    skipped = {s["source"]: s["problem"] for s in data["skipped"]}
    assert "not a valid English BIP39 phrase" in skipped["hermes/HERMES_BROKEN"]
    assert skipped["other/COPY"] == f"the same secret as {MAIN}; ignored"
    # listed first, the watch-only copy still loses to the Hermes one
    reordered = [SOURCES[5]] + SOURCES[:5]
    rows = {r["account"]: r for r in signer(tmp_path, endpoint, "accounts", count=1, _sources=reordered)["data"]["accounts"]}
    assert rows[f"{MAIN}#0"]["use"] == "sign" and "other/COPY#0" not in rows


def test_each_tool_lists_its_own_familys_addresses(tmp_path, endpoint):
    rows = {r["account"]: r for r in signer(tmp_path, endpoint, "accounts", count=1, family="solana")["data"]["accounts"]}
    assert rows[f"{MAIN}#0"]["solana"] == SOL_OPS and "evm" not in rows[f"{MAIN}#0"]
    assert KEY not in rows  # an EVM key has no place in the solana tool's list
    reply = signer(tmp_path, endpoint, "accounts", family="solana", chain="sepolia")
    assert reply["ok"] is False and "is not a Solana chain" in reply["error"]


def test_solana_balances_come_in_one_batch(tmp_path, endpoint):
    data = signer(tmp_path, endpoint, "accounts", count=1, chain="solana-devnet")["data"]
    rows = {row["account"]: row for row in data["accounts"]}
    assert rows[f"{MAIN}#0"]["balance"] == "5 SOL" and rows[f"{WORK}#0"]["balance"] == "0 SOL"
    assert "balance" not in rows[KEY]  # an EVM key has no Solana address


def test_without_any_hermes_wallet_the_wallet_says_how_to_label_one(tmp_path, endpoint):
    data = signer(tmp_path, endpoint, "accounts", _sources=[])["data"]
    assert data["accounts"] == [] and "secret set HERMES_MAIN" in data["setup"]
    for sources in ([], [SOURCES[3]]):
        reply = signer(tmp_path, endpoint, "quote", _sources=sources, account=f"{TEAM}#0", chain="sepolia",
                       to=SPARE, amount="0.01")
        assert reply["ok"] is False and "no Hermes seed phrase or private key" in reply["error"]


def test_a_watch_only_wallet_never_signs_and_is_not_own(tmp_path, endpoint):
    reply = signer(tmp_path, endpoint, "quote", account=f"{TEAM}#0", chain="sepolia", to=SPARE, amount="0.01")
    assert reply["ok"] is False and "watch-only (no HERMES in its name)" in reply["error"]
    team0 = {r["account"]: r for r in signer(tmp_path, endpoint, "accounts", count=1)["data"]["accounts"]}[f"{TEAM}#0"]
    data = quote(tmp_path, endpoint, to=team0["evm"], amount="0.01")
    to_block = data["card"].split("\n\n")[2].splitlines()
    assert data["own"] is False and to_block == [
        "--- To ---", "Type: Watch-only (external)", "Project: team(Shared)", "Name: PROD_MNEMONIC",
        f"Address #0: {team0['evm']}"]
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "needs the approval card" in reply["error"]


# --- who is own ---------------------------------------------------------------------------------

def test_spare_accounts_other_seeds_and_keys_are_own(tmp_path, endpoint):
    key_address = signer(tmp_path, endpoint, "accounts", count=1)["data"]["accounts"][-1]["evm"]
    for to in (SPARE, WORK0, key_address):
        data = quote(tmp_path, endpoint, to=to, amount="0.01")
        assert data["own"] is True and "--- To ---\nType: Your own\n" in data["card"], to
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    assert data["own"] is False and data["card"].endswith(f"--- To ---\nType: External\nAddress: {STRANGER}")


def test_a_secret_no_longer_labelled_is_not_own(tmp_path, endpoint):
    only_main = [SOURCES[0]]
    data = quote(tmp_path, endpoint, _sources=only_main, to=WORK0, amount="0.01")
    assert data["own"] is False


def test_account_names_are_checked(tmp_path, endpoint):
    cases = [(f"{MAIN}", "is a seed phrase; name an account in it"), (f"{MAIN}#x", "must be a number"),
             ("hermes/NOPE#0", "no seed phrase 'hermes/NOPE'"), ("hermes/NOPE", "no account 'hermes/NOPE'")]
    for account, message in cases:
        reply = signer(tmp_path, endpoint, "quote", account=account, chain="sepolia", to=SPARE, amount="0.01")
        assert reply["ok"] is False and message in reply["error"], (account, reply)
    reply = signer(tmp_path, endpoint, "quote", account=KEY, chain="solana-devnet", to=SOL_SPARE, amount="0.01")
    assert reply["ok"] is False and "is an EVM key; it cannot sign on Solana" in reply["error"]


# --- EVM ----------------------------------------------------------------------------------------

def test_mainnet_cards_say_so(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="base", to=STRANGER, amount="0.01")
    assert data["card"].startswith("Chain: Base(MAINNET)\nSend: 0.01 ETH\n")
    assert quote(tmp_path, endpoint, to=STRANGER, amount="0.01")["card"].startswith("Chain: Sepolia(testnet)\n")


def card_units(text: str) -> int:
    import html
    return len(html.escape(text).encode("utf-16-le")) // 2


def test_the_card_has_a_block_per_side_with_the_keychain_metadata(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01", token=USDC)
    head, sender, recipient = data["card"].split("\n\n")
    assert head.splitlines()[:4] == ["Chain: Sepolia(testnet)", f"Token: {USDC}", 'Send: 0.01 "USDC" token',
                                     "Fee: up to 0.00018 ETH"]
    assert head.splitlines()[4].startswith(f"Quote: {data['quote']} · expires ") and "UTC+" in head
    assert sender.splitlines() == ["--- From ---", "Project: hermes(Shared)", "Name: HERMES_MAIN",
                                   f"Address #0: {OPS}", "Memo: main ops wallet"]
    assert recipient.splitlines() == ["--- To ---", "Type: External", f"Address: {STRANGER}"]
    assert card_units(data["card"]) <= 480
    stored = json.loads(quote_file(tmp_path, data["quote"]).read_text())
    assert stored["card_short"].splitlines() == [
        'Send 0.01 "USDC" token on Sepolia', f"Token: {USDC}", f"From {MAIN}#0: {OPS}",
        f"To (external): {STRANGER}", f"Fee ≤ 0.00018 ETH · {data['quote']}"]
    assert card_units(stored["card_short"]) <= 290


def test_an_untidy_symbol_shows_as_a_question_mark(tmp_path, endpoint):
    FAKE["symbol"] = "USDC\nTo · your own account"
    assert 'Send: 0.01 "?" token' in quote(tmp_path, endpoint, to=STRANGER, amount="0.01", token=USDC)["card"]


def test_a_long_card_sheds_memo_and_scope_before_falling_back_to_the_compact_one(tmp_path, endpoint):
    long = "x" * 60
    sources = [item(f"{'p' * 40}/{'s' * 40}/HERMES_{'N' * 40}", "seed", MAIN_WORDS, memo="m" * 80),
               item(f"{'q' * 40}/{'t' * 40}/HERMES_{'W' * 40}", "seed", WORK_WORDS, memo="n" * 80)]
    account = f"{sources[0]['id']}#0"
    data = quote(tmp_path, endpoint, _sources=sources, account=account, to=WORK0, amount="0.01", token=USDC)
    card = data["card"]
    assert card_units(card) <= 480 and "Memo:" not in card
    assert f"Address #0: {OPS}" in card or card.startswith("Send ")  # detailed, or the compact fallback
    assert long not in card
    stored = json.loads(quote_file(tmp_path, data["quote"]).read_text())
    assert card_units(stored["card_short"]) <= 300
    assert stored["from_party"]["memo"].endswith("…") and len(stored["from_party"]["memo"]) == 40


def test_an_external_quote_cannot_be_sent_as_own(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "needs the approval card" in reply["error"]
    assert FAKE["sent"] == [] and ledger(tmp_path) == []


def test_a_quote_sends_once_exactly_as_quoted(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="10", token=USDC)
    sent = send(tmp_path, endpoint, data["quote"], "card")
    assert sent["ok"], sent
    tx = decode(tmp_path, "sepolia", FAKE["sent"][0])
    assert tx["from"] == OPS and tx["chain"] == "sepolia" and tx["to"] == USDC and tx["nonce"] == 4
    assert tx["call"]["function"] == "transfer" and tx["call"]["args"] == {"to": STRANGER, "amount": 10_000_000}
    assert [row["outcome"] for row in ledger(tmp_path)] == ["unknown", "sent"]
    again = send(tmp_path, endpoint, data["quote"], "card")
    assert again["ok"] is False and "already used" in again["error"]
    assert len(FAKE["sent"]) == 1


def test_seed_accounts_and_keys_sign_with_their_own_secret(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, account=f"{WORK}#0", to=OPS, amount="0.01")
    assert data["own"] is True and data["summary"]["from"] == WORK0
    assert send(tmp_path, endpoint, data["quote"], "own")["ok"]
    assert decode(tmp_path, "sepolia", FAKE["sent"][0])["from"] == WORK0
    data = quote(tmp_path, endpoint, account=KEY, to=OPS, amount="0.01")
    assert f"Address (key): {data['summary']['from']}" in data["card"]
    assert data["card"].endswith(f"--- To ---\nType: Your own\nProject: hermes(Shared)\nName: HERMES_MAIN\n"
                                 f"Address #0: {OPS}\nMemo: main ops wallet")
    assert send(tmp_path, endpoint, data["quote"], "own")["ok"]
    assert decode(tmp_path, "sepolia", FAKE["sent"][1])["from"] == data["summary"]["from"]


def test_an_edited_or_expired_quote_is_refused(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    path = quote_file(tmp_path, data["quote"])
    stored = json.loads(path.read_text())
    edited = {**stored, "to": STRANGER, "build": {**stored["build"], "to": STRANGER}}
    path.write_text(json.dumps(edited))
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "changed after it was made" in reply["error"]
    expired = {**stored, "expires": stored["created"] - 1}
    expired["mac"] = remac(expired, MAIN_WORDS)
    path.write_text(json.dumps(expired))
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "expired" in reply["error"]
    assert FAKE["sent"] == []


def test_a_quote_whose_secret_is_gone_is_refused(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, account=f"{WORK}#0", to=OPS, amount="0.01")
    reply = send(tmp_path, endpoint, data["quote"], "own", _sources=[SOURCES[0]])
    assert reply["ok"] is False and "no longer in the Keychain" in reply["error"]


def test_verify_returns_the_authentic_cards_and_mac(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    verified = signer(tmp_path, endpoint, "verify", quote=data["quote"])["data"]
    stored = json.loads(quote_file(tmp_path, data["quote"]).read_text())
    assert verified == {"quote": data["quote"], "chain": "sepolia", "own": False, "card": stored["card"],
                        "card_short": stored["card_short"], "mac": stored["mac"]}


def test_another_quotes_file_under_this_id_is_refused(tmp_path, endpoint):
    benign = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    evil = quote(tmp_path, endpoint, to=STRANGER, amount="0.05")
    quote_file(tmp_path, benign["quote"]).write_text(quote_file(tmp_path, evil["quote"]).read_text())
    reply = signer(tmp_path, endpoint, "verify", quote=benign["quote"])
    assert reply["ok"] is False and "holds another quote" in reply["error"]


def test_a_send_must_present_the_approved_quotes_mac(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    reply = send(tmp_path, endpoint, data["quote"], "card", mac="0" * 64)
    assert reply["ok"] is False and "not the quote that was approved" in reply["error"]
    assert FAKE["sent"] == []


def test_clearing_the_consumed_mark_does_not_send_twice(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    verified = signer(tmp_path, endpoint, "verify", quote=data["quote"])["data"]
    assert send(tmp_path, endpoint, data["quote"], "card", mac=verified["mac"])["ok"]
    path = quote_file(tmp_path, data["quote"])
    stored = json.loads(path.read_text())
    stored.pop("consumed")
    path.write_text(json.dumps(stored))  # the MAC still checks out: consumed is outside it
    for reply in (signer(tmp_path, endpoint, "verify", quote=data["quote"]),
                  send(tmp_path, endpoint, data["quote"], "card", mac=verified["mac"])):
        assert reply["ok"] is False and "already used" in reply["error"]
    assert len(FAKE["sent"]) == 1


def test_every_send_attempt_counts_on_its_own(tmp_path, endpoint):
    for _ in range(3):
        data = quote(tmp_path, endpoint, to=SPARE, amount="0.001")
        assert send(tmp_path, endpoint, data["quote"], "own")["ok"]
    rows = ledger(tmp_path)
    assert len({row["attempt"] for row in rows}) == 3 and all(len(row["attempt"]) == 16 for row in rows)


def test_an_op_stack_fee_includes_the_l1_data_fee(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="base-sepolia", to=STRANGER, amount="0.01")
    # 21000 gas at 3 gwei, plus twice the oracle's 1e12 wei L1 fee
    assert data["summary"]["max_fee"] == "0.000065"
    assert quote(tmp_path, endpoint, to=STRANGER, amount="0.01")["summary"]["max_fee"] == "0.000063"


def test_a_hermes_wallet_in_the_environment_gets_a_warning(tmp_path, endpoint):
    sources = [dict(SOURCES[0], env="no"), dict(SOURCES[1], env="yes"), SOURCES[3]]
    data = signer(tmp_path, endpoint, "accounts", count=1, _sources=sources)["data"]
    warned = {w["source"]: w["warning"] for w in data.get("warnings", [])}
    assert set(warned) == {WORK}
    assert "secret update PROJECTX-HERMES -p projectx --scope ops --no-env" in warned[WORK]
    rows = {r["account"]: r for r in data["accounts"]}
    assert rows[f"{MAIN}#0"]["env"] == "no" and rows[f"{WORK}#0"]["env"] == "yes"


def test_the_hourly_cap_counts_every_send(tmp_path, endpoint):
    for _ in range(10):
        data = quote(tmp_path, endpoint, to=SPARE, amount="0.001")
        assert send(tmp_path, endpoint, data["quote"], "own")["ok"]
    capped = signer(tmp_path, endpoint, "quote", account=f"{MAIN}#0", chain="sepolia", to=SPARE, amount="0.001")
    assert capped["ok"] is False and "10 transfers in the last hour" in capped["error"]


def test_bad_transfers_are_refused(tmp_path, endpoint):
    cases = [
        ({"token": "0x" + "12" * 20}, "no contract at that token address"),
        ({"chain": "dogechain"}, "unknown chain"),
        ({"to": OPS}, "sending account itself"),
        ({"to": USDC, "token": USDC}, "token contract itself"),
        ({"to": "0x" + "00" * 20}, "zero address"),
        ({"token": USDC, "amount": "0.0000001"}, "decimal places"),
        ({"amount": "-1"}, "above zero"),
        ({"token": "USDC"}, "token must be a token contract"),
    ]
    for fields, message in cases:
        reply = signer(tmp_path, endpoint, "quote", **{"account": f"{MAIN}#0", "chain": "sepolia", "to": SPARE,
                                                       "amount": "1", **fields})
        assert reply["ok"] is False and message in reply["error"], (fields, reply)


def test_a_rejected_broadcast_is_not_counted_and_a_lost_one_is(tmp_path, endpoint):
    FAKE["broadcast"] = "reject"
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "nonce too low" in reply["error"]
    assert ledger(tmp_path)[-1]["outcome"] == "rejected"
    FAKE["broadcast"] = "drop"
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    reply = send(tmp_path, endpoint, data["quote"], "own")
    assert reply["ok"] is False and "outcome is unknown" in reply["error"]
    assert ledger(tmp_path)[-1]["outcome"] == "unknown"


# --- Solana -------------------------------------------------------------------------------------

def test_a_sol_transfer_signs_the_quoted_lamports(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="solana-devnet", to=SOL_SPARE, amount="0.25")
    assert data["own"] is True and data["summary"]["max_fee"] == "0.000005"
    assert send(tmp_path, endpoint, data["quote"], "own")["ok"]
    tx = decode(tmp_path, "solana-devnet", FAKE["sent"][0])
    assert tx["signers"] == [SOL_OPS] and tx["signatures_present"] == 1
    ix = tx["instructions"][0]
    assert ix["type"] == "transfer" and ix["from"] == SOL_OPS and ix["to"] == SOL_SPARE and ix["sol"] == "0.25"


def test_a_solana_keypair_signs_as_its_own_account(tmp_path, endpoint):
    made = subprocess.run([str(PYTHON), "-c", "from solders.keypair import Keypair; k = Keypair.from_seed(bytes([7]) * 32);"
                           "print(str(k)); print(k.pubkey())"], capture_output=True, text=True, timeout=30).stdout.split()
    sources = SOURCES + [item("hermes/SOL_HERMES", "key", made[0])]
    rows = {r["account"]: r for r in signer(tmp_path, endpoint, "accounts", count=1, _sources=sources)["data"]["accounts"]}
    assert rows["hermes/SOL_HERMES"]["solana"] == made[1]
    data = quote(tmp_path, endpoint, _sources=sources, account="hermes/SOL_HERMES", chain="solana-devnet", to=SOL_OPS,
                 amount="0.25")
    assert data["own"] is True and data["summary"]["from"] == made[1]


def test_an_spl_transfer_creates_the_recipients_token_account(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="solana-devnet", to=SOL_STRANGER, amount="2.5", token=DEV_USDC)
    assert data["own"] is False and f"Token: {DEV_USDC}" in data["card"]
    assert data["summary"]["max_fee"] == "0.00204428"  # signature fee + the new token account's rent
    assert send(tmp_path, endpoint, data["quote"], "card")["ok"]
    create, move = decode(tmp_path, "solana-devnet", FAKE["sent"][0])["instructions"]
    assert create["name"] == "Associated Token Account" and create["accounts"][2] == SOL_STRANGER
    assert move["type"] == "transferChecked" and move["amount"] == 2_500_000 and move["decimals"] == 6
    assert move["mint"] == DEV_USDC and move["authority"] == SOL_OPS


def test_a_token_account_is_not_a_recipient(tmp_path, endpoint):
    FAKE["token_ata_exists"] = True
    reply = signer(tmp_path, endpoint, "quote", account=f"{MAIN}#0", chain="solana-devnet", to=SOL_STRANGER,
                   amount="0.5")
    assert reply["ok"] is False and "token account" in reply["error"]
