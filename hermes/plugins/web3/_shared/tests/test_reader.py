"""The chain engine end to end in its own venv, against a fake JSON-RPC server (no network)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest

HERMES = Path(__file__).resolve().parents[4]
PYTHON = HERMES / "local" / "web3" / "venv" / "bin" / "python"
READER = HERMES / "plugins" / "web3" / "_shared" / "reader.py"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

ALICE = "0x" + "a1" * 20
BOB = "0x" + "b2" * 20
USDC = "0x1c7d4b196cb0c7b01d743fbc6116a902379c7238"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
HASH_OK = "0x" + "11" * 32
HASH_FAILED = "0x" + "22" * 32
# Signed with Hardhat's public account #0: an ERC-20 transfer of 1.5 USDC on Sepolia.
EVM_RAW = ("0x02f8b283aa36a707843b9aca0084b2d05e0082fde8941c7d4b196cb0c7b01d743fbc6116a902379c723880b844a9059cbb"
           "00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8000000000000000000000000000000000000"
           "000000000000000000000016e360c001a0c5a72ef262ca600dde10c9dfcec3739bab3ee91985bf444d98d2f84f92ec3311a0"
           "7ee3c6e0a9bd7f788cc3bdd4e70e90e06f805c2058edd4a748b621778c35a3ae")
# A signed System Program transfer of 0.25 SOL between the Hardhat mnemonic's first two Solana accounts.
SOL_RAW = ("AUlUypfomeZlg0Den3k7EF53IN/jaSjvmfFKLtFB6vX9J/MRSpmuV8UL5bNT4TXxZFjQWOEtqQOmStsblt7lUQkBAAEDC/Mrnw2w"
           "lnIDj+o2E5sY+YpfAUnvTOAzLkS5p36Dwi2SRUQfSnUupjKMbY0tKvyzbRMduZikfKBNbV2Fh9CwEgAAAAAAAAAAAAAAAAAAAAAA"
           "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAgIAAQwCAAAAgLLmDgAAAAA=")
SOL_FROM = "oeYf6KAJkLYhBuR8CiGc6L4D4Xtfepr85fuDgA9kq96"
SOL_TO = "AqynRZwvVqUPRwRJXvm6odUb3t93fDjnWe3p6BeuUFxD"


def word(value: int) -> str:
    return format(value, "064x")


def padded(address: str) -> str:
    return "0x" + address[2:].rjust(64, "0")


def abi_string(text: str) -> str:
    raw = text.encode()
    return "0x" + word(32) + word(len(raw)) + raw.hex().ljust(((len(raw) + 31) // 32) * 64, "0")


TX_BASE = {"from": ALICE, "to": USDC, "nonce": "0x7", "type": "0x2", "value": "0x0", "gas": "0xfde8",
           "transactionIndex": "0x3", "blockNumber": "0x64",
           "input": "0xa9059cbb" + padded(BOB)[2:] + word(1_500_000)}


def handle(method: str, params: list):
    """(result, error) for one fake JSON-RPC call."""
    if method == "eth_getTransactionByHash":
        return ({**TX_BASE, "hash": params[0]} if params[0] in (HASH_OK, HASH_FAILED) else None), None
    if method == "eth_getTransactionReceipt":
        if params[0] == HASH_OK:
            log = {"address": USDC, "topics": [TRANSFER_TOPIC, padded(ALICE), padded(BOB)],
                   "data": "0x" + word(1_500_000), "logIndex": "0x0", "blockNumber": "0x64"}
            return {"status": "0x1", "blockNumber": "0x64", "gasUsed": "0xc350",
                    "effectiveGasPrice": hex(2 * 10 ** 9), "logs": [log]}, None
        if params[0] == HASH_FAILED:
            return {"status": "0x0", "blockNumber": "0x64", "gasUsed": "0x5208",
                    "effectiveGasPrice": hex(2 * 10 ** 9), "logs": []}, None
        return None, None
    if method == "eth_getBlockByNumber":
        return {"number": "0x64", "timestamp": hex(1_790_000_000), "baseFeePerGas": hex(10 ** 9)}, None
    if method == "eth_call":
        call, block = params[0], params[1]
        data = call.get("data") or ""
        if block == "0x63":  # the revert replay of the failed transaction
            return None, {"code": 3, "message": "execution reverted",
                          "data": "0x08c379a0" + abi_string("too little received")[2:]}
        if data == "0x95d89b41":
            return abi_string("USDC"), None
        if data == "0x313ce567":
            return "0x" + word(6), None
        return "0x", None
    if method == "eth_getBalance":
        return hex(3 * 10 ** 18), None
    if method == "eth_getTransactionCount":
        return "0x5", None
    if method == "eth_getCode":
        if params[0].lower() == ALICE:
            return "0xef0100" + "cd" * 20, None  # an EIP-7702 delegated account
        return "0x", None
    return None, {"code": -32601, "message": f"no fake for {method}"}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        items = body if isinstance(body, list) else [body]
        replies = []
        for item in items:
            result, error = handle(item["method"], item.get("params") or [])
            reply = {"jsonrpc": "2.0", "id": item["id"]}
            reply.update({"error": error} if error else {"result": result})
            replies.append(reply)
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def engine(payload: dict, tmp_path: Path, test: bool = True) -> dict:
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}
    if test:
        env["WEB3_ENGINE_TEST"] = "1"
    proc = subprocess.run([str(PYTHON), str(READER)], input=json.dumps({"_offline": True, **payload}),
                          capture_output=True, text=True, timeout=60, env=env)
    return json.loads(proc.stdout)


def test_a_token_transfer_is_decoded_with_balance_changes(endpoint, tmp_path):
    reply = engine({"action": "tx", "chain": "sepolia", "_rpc": endpoint, "hash": HASH_OK}, tmp_path)
    assert reply["ok"], reply
    data = reply["data"]
    assert data["status"] == "success" and data["block"] == 100
    assert data["call"]["function"] == "transfer" and data["call"]["source"] == "known"
    assert data["call"]["args"]["amount"] == 1_500_000
    assert data["fee"] == {"total": "0.0001", "total_usd": None, "burned": "0.00005", "priority": "0.00005"}
    event = data["events"][0]
    assert event["event"] == "Transfer" and event["args"]["value"] == 1_500_000
    changes = {row["address"].lower(): row["changes"] for row in data["balance_changes"]}
    assert {"token": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238", "symbol": {"untrusted": "USDC"},
            "change": "1.5"} in changes[BOB]
    assert {"asset": "ETH", "change": "-0.0001"} in changes[ALICE]


def test_a_failed_transaction_reports_its_revert_reason(endpoint, tmp_path):
    data = engine({"action": "tx", "chain": "sepolia", "_rpc": endpoint, "hash": HASH_FAILED}, tmp_path)["data"]
    assert data["status"] == "failed"
    assert data["revert"] == {"replayed": True, "error": "Error", "reason": {"untrusted": "too little received"}}


def test_an_eip7702_account_shows_its_delegate(endpoint, tmp_path):
    data = engine({"action": "address", "chain": "sepolia", "_rpc": endpoint, "address": ALICE}, tmp_path)["data"]
    assert data["kind"].startswith("EOA with delegated code")
    assert data["delegate_to"].lower() == "0x" + "cd" * 20 and data["balance"] == "3"


def test_a_signed_raw_transaction_is_decoded(tmp_path):
    data = engine({"action": "decode", "chain": "sepolia", "data": EVM_RAW}, tmp_path)["data"]
    assert data["kind"] == "transaction" and data["type"] == "eip-1559" and data["signed"] is True
    assert data["from"] == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    assert data["chain"] == "sepolia" and data["nonce"] == 7
    assert data["call"]["args"] == {"to": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "amount": 1_500_000}


def test_a_solana_transfer_is_decoded(tmp_path):
    data = engine({"action": "decode", "chain": "solana-devnet", "data": SOL_RAW}, tmp_path)["data"]
    assert data["signers"] == [SOL_FROM] and data["signatures_present"] == 1
    ix = data["instructions"][0]
    assert ix["name"] == "System Program" and ix["type"] == "transfer"
    assert ix["from"] == SOL_FROM and ix["to"] == SOL_TO and ix["sol"] == "0.25"


def test_bad_requests_are_errors_not_crashes(endpoint, tmp_path):
    reply = engine({"action": "tx", "chain": "nowhere"}, tmp_path)
    assert reply["ok"] is False and "unknown chain" in reply["error"]
    reply = engine({"action": "logs", "chain": "solana"}, tmp_path)
    assert reply["ok"] is False and "not available" in reply["error"]
    reply = engine({"action": "tx", "chain": "sepolia", "_rpc": endpoint, "hash": "0x12"}, tmp_path)
    assert reply["ok"] is False and "64 hex digits" in reply["error"]


def test_the_endpoint_override_needs_the_test_switch(tmp_path):
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import rpc; "
            "print(rpc.Rpc('sepolia', 'http://127.0.0.1:9').url)")
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}  # no secret CLI under this HOME
    out = subprocess.run([str(PYTHON), "-c", code, str(READER.parent)], capture_output=True, text=True,
                         env=env, timeout=30).stdout.strip()
    assert out == "https://ethereum-sepolia-rpc.publicnode.com"
    out = subprocess.run([str(PYTHON), "-c", code, str(READER.parent)], capture_output=True, text=True,
                         env={**env, "WEB3_ENGINE_TEST": "1"}, timeout=30).stdout.strip()
    assert out == "http://127.0.0.1:9"


def test_errors_never_carry_a_provider_key(tmp_path):
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import rpc; rpc.SECRETS.append('k3y-SECRET'); "
            "print(rpc.mask('https://eth-mainnet.g.alchemy.com/v2/k3y-SECRET failed'))")
    out = subprocess.run([str(PYTHON), "-c", code, str(READER.parent)], capture_output=True, text=True,
                         env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}, timeout=30).stdout
    assert "k3y-SECRET" not in out and "…" in out
