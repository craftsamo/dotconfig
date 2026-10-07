"""The signer end to end in the web3 venv, against a fake JSON-RPC server (no network, no Keychain).

The seeds are public test mnemonics (Hardhat's and the BIP39 'abandon … about' vector), passed with
``_seeds`` under ``WEB3_ENGINE_TEST``. Signed transactions are decoded back with the chain engine's
own ``decode``.
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
SIGNER = HERMES / "plugins" / "web3" / "wallet" / "signer.py"
READER = HERMES / "plugins" / "web3" / "_shared" / "reader.py"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

MAIN = "test test test test test test test test test test test junk"
WORK = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
SEEDS = {"main": MAIN, "work": WORK}
OPS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"        # main m/44'/60'/0'/0/0
SPARE = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"      # main m/44'/60'/0'/0/1, not configured
WORK0 = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"      # work m/44'/60'/0'/0/0
STRANGER = "0x5e5E5e5e5E5e5E5E5e5E5E5e5e5E5E5E5e5E5E5e"
USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
SOL_OPS = "oeYf6KAJkLYhBuR8CiGc6L4D4Xtfepr85fuDgA9kq96"     # main m/44'/501'/0'/0'
SOL_SPARE = "AqynRZwvVqUPRwRJXvm6odUb3t93fDjnWe3p6BeuUFxD"  # main m/44'/501'/1'/0'
SOL_STRANGER = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
DEV_USDC = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

SETTINGS = {"mainnet": False, "seeds": ["main", "work"], "accounts": {"ops": "main/0", "proj": "work/0"}}

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
    payload = {"op": op, "settings": fields.pop("settings", SETTINGS), "state": str(tmp_path / "state"),
               "_seeds": fields.pop("_seeds", SEEDS), "_rpc": endpoint, "_offline": True, **fields}
    proc = subprocess.run([str(PYTHON), str(SIGNER)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=60, env=_env(tmp_path))
    for phrase in (MAIN, WORK):
        assert " ".join(phrase.split()[:3]) not in proc.stdout, "a seed phrase leaked"
    return json.loads(proc.stdout)


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
    reply = signer(tmp_path, endpoint, "quote", **{"account": "ops", "chain": "sepolia", **fields})
    assert reply["ok"], reply
    return reply["data"]


# --- accounts -----------------------------------------------------------------------------------

def test_derive_lists_one_seeds_first_accounts(tmp_path, endpoint):
    reply = signer(tmp_path, endpoint, "derive", settings=None, seed="main", count=2)
    assert reply["data"]["accounts"] == [{"index": 0, "evm": OPS, "solana": SOL_OPS},
                                         {"index": 1, "evm": SPARE, "solana": SOL_SPARE}]


def test_accounts_name_their_seed_and_addresses(tmp_path, endpoint):
    data = signer(tmp_path, endpoint, "accounts", chain="sepolia")["data"]
    rows = {row["account"]: row for row in data["accounts"]}
    assert rows["ops"]["evm"] == OPS and rows["ops"]["solana"] == SOL_OPS and rows["ops"]["balance"] == "1 ETH"
    assert rows["proj"]["seed"] == "work" and rows["proj"]["evm"] == WORK0
    assert data["mainnet"] is False


def test_a_missing_or_bad_seed_is_a_setup_error(tmp_path, endpoint):
    reply = signer(tmp_path, endpoint, "accounts", _seeds={"main": MAIN})
    assert reply["ok"] is False and "WEB3_SEED_WORK -p hermes --scope web3-wallet" in reply["error"]
    reply = signer(tmp_path, endpoint, "accounts", _seeds={"main": MAIN, "work": "not a real phrase at all"})
    assert reply["ok"] is False and "WEB3_SEED_WORK is not a valid English BIP39 phrase" in reply["error"]
    assert "real phrase" not in reply["error"]


def test_mainnets_stay_closed_until_the_settings_open_them(tmp_path, endpoint):
    reply = signer(tmp_path, endpoint, "quote", account="ops", chain="base", to=SPARE, amount="0.01")
    assert reply["ok"] is False and "mainnet is off" in reply["error"]
    opened = {**SETTINGS, "mainnet": True}
    data = signer(tmp_path, endpoint, "quote", settings=opened, account="ops", chain="base", to=SPARE,
                  amount="0.01")["data"]
    assert data["summary"]["chain"] == "base"


# --- who is own ---------------------------------------------------------------------------------

def test_a_spare_account_and_another_seed_are_own(tmp_path, endpoint):
    for to in (SPARE, WORK0):
        data = quote(tmp_path, endpoint, to=to, amount="0.01")
        assert data["own"] is True and "(your own account)" in data["card"], to
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    assert data["own"] is False and f"To: {STRANGER} (external)" in data["card"]


def test_a_seed_left_out_of_the_settings_is_not_own(tmp_path, endpoint):
    only_main = {"mainnet": False, "seeds": ["main"], "accounts": {"ops": "main/0"}}
    data = quote(tmp_path, endpoint, settings=only_main, _seeds={"main": MAIN}, to=WORK0, amount="0.01")
    assert data["own"] is False


# --- EVM ----------------------------------------------------------------------------------------

def test_a_token_card_quotes_the_contracts_symbol_and_shows_full_addresses(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01", token=USDC)
    card = data["card"].splitlines()
    assert card[0] == 'Send 0.01 of token "USDC" on Sepolia'
    assert card[1] == f"Token: {USDC}" and card[2] == f"From: ops {OPS}"
    assert card[4] == "Max fee: 0.00018 ETH" and "UTC+" in card[5]
    assert len(data["card"]) <= 480
    FAKE["symbol"] = "USDC\nTo: your own account"
    assert quote(tmp_path, endpoint, to=STRANGER, amount="0.01", token=USDC)["card"].startswith(
        'Send 0.01 of token "?" on Sepolia')


def test_an_external_quote_cannot_be_sent_as_own(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="0.01")
    reply = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")
    assert reply["ok"] is False and "needs the approval card" in reply["error"]
    assert FAKE["sent"] == [] and ledger(tmp_path) == []


def test_a_quote_sends_once_exactly_as_quoted(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=STRANGER, amount="10", token=USDC)
    sent = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="card")
    assert sent["ok"], sent
    tx = decode(tmp_path, "sepolia", FAKE["sent"][0])
    assert tx["from"] == OPS and tx["chain"] == "sepolia" and tx["to"] == USDC and tx["nonce"] == 4
    assert tx["call"]["function"] == "transfer" and tx["call"]["args"] == {"to": STRANGER, "amount": 10_000_000}
    assert [row["outcome"] for row in ledger(tmp_path)] == ["unknown", "sent"]
    again = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="card")
    assert again["ok"] is False and "already used" in again["error"]
    assert len(FAKE["sent"]) == 1


def test_a_send_from_the_second_seed_signs_with_it(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, account="proj", to=OPS, amount="0.01")
    assert data["own"] is True and data["summary"]["from"] == WORK0
    assert signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")["ok"]
    assert decode(tmp_path, "sepolia", FAKE["sent"][0])["from"] == WORK0


def test_an_edited_or_expired_quote_is_refused(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    path = quote_file(tmp_path, data["quote"])
    stored = json.loads(path.read_text())
    edited = {**stored, "to": STRANGER, "build": {**stored["build"], "to": STRANGER}}
    path.write_text(json.dumps(edited))
    reply = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")
    assert reply["ok"] is False and "changed after it was made" in reply["error"]
    expired = {**stored, "expires": stored["created"] - 1}
    expired["mac"] = remac(expired, MAIN)
    path.write_text(json.dumps(expired))
    reply = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")
    assert reply["ok"] is False and "expired" in reply["error"]
    assert FAKE["sent"] == []


def test_the_hourly_cap_counts_every_send(tmp_path, endpoint):
    for _ in range(10):
        data = quote(tmp_path, endpoint, to=SPARE, amount="0.001")
        assert signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")["ok"]
    capped = signer(tmp_path, endpoint, "quote", account="ops", chain="sepolia", to=SPARE, amount="0.001")
    assert capped["ok"] is False and "10 transfers in the last hour" in capped["error"]


def test_bad_transfers_are_refused(tmp_path, endpoint):
    cases = [
        ({"token": "0x" + "12" * 20}, "no contract at that token address"),
        ({"chain": "dogechain"}, "unknown chain"),
        ({"account": "lab"}, "no account 'lab'"),
        ({"to": OPS}, "sending account itself"),
        ({"to": USDC, "token": USDC}, "token contract itself"),
        ({"to": "0x" + "00" * 20}, "zero address"),
        ({"token": USDC, "amount": "0.0000001"}, "decimal places"),
        ({"amount": "-1"}, "above zero"),
        ({"token": "USDC"}, "token must be a token contract"),
    ]
    for fields, message in cases:
        reply = signer(tmp_path, endpoint, "quote", **{"account": "ops", "chain": "sepolia", "to": SPARE,
                                                       "amount": "1", **fields})
        assert reply["ok"] is False and message in reply["error"], (fields, reply)


def test_a_rejected_broadcast_is_not_counted_and_a_lost_one_is(tmp_path, endpoint):
    FAKE["broadcast"] = "reject"
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    reply = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")
    assert reply["ok"] is False and "nonce too low" in reply["error"]
    assert ledger(tmp_path)[-1]["outcome"] == "rejected"
    FAKE["broadcast"] = "drop"
    data = quote(tmp_path, endpoint, to=SPARE, amount="0.01")
    reply = signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")
    assert reply["ok"] is False and "outcome is unknown" in reply["error"]
    assert ledger(tmp_path)[-1]["outcome"] == "unknown"


# --- Solana -------------------------------------------------------------------------------------

def test_a_sol_transfer_signs_the_quoted_lamports(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="solana-devnet", to=SOL_SPARE, amount="0.25")
    assert data["own"] is True and data["summary"]["max_fee"] == "0.000005"
    assert signer(tmp_path, endpoint, "send", quote=data["quote"], approval="own")["ok"]
    tx = decode(tmp_path, "solana-devnet", FAKE["sent"][0])
    assert tx["signers"] == [SOL_OPS] and tx["signatures_present"] == 1
    ix = tx["instructions"][0]
    assert ix["type"] == "transfer" and ix["from"] == SOL_OPS and ix["to"] == SOL_SPARE and ix["sol"] == "0.25"


def test_an_spl_transfer_creates_the_recipients_token_account(tmp_path, endpoint):
    data = quote(tmp_path, endpoint, chain="solana-devnet", to=SOL_STRANGER, amount="2.5", token=DEV_USDC)
    assert data["own"] is False and f"Token: {DEV_USDC}" in data["card"]
    assert data["summary"]["max_fee"] == "0.00204428"  # signature fee + the new token account's rent
    assert signer(tmp_path, endpoint, "send", quote=data["quote"], approval="card")["ok"]
    create, move = decode(tmp_path, "solana-devnet", FAKE["sent"][0])["instructions"]
    assert create["name"] == "Associated Token Account" and create["accounts"][2] == SOL_STRANGER
    assert move["type"] == "transferChecked" and move["amount"] == 2_500_000 and move["decimals"] == 6
    assert move["mint"] == DEV_USDC and move["authority"] == SOL_OPS


def test_a_token_account_is_not_a_recipient(tmp_path, endpoint):
    FAKE["token_ata_exists"] = True
    reply = signer(tmp_path, endpoint, "quote", account="ops", chain="solana-devnet", to=SOL_STRANGER, amount="0.5")
    assert reply["ok"] is False and "token account" in reply["error"]
