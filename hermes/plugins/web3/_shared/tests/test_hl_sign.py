"""Hyperliquid signing in the web3 venv against hyperliquid-python-sdk's own test vectors
(tests/signing_test.py), and for the user-signed actions those tests leave out, against what the SDK's
``utils/signing.py`` (0.24.0) signs for the same key and action: the same key, actions and nonces must
give the same signatures, byte for byte."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

HERMES = Path(__file__).resolve().parents[4]
PYTHON = HERMES / "local" / "web3" / "venv" / "bin" / "python"
SHARED = HERMES / "plugins" / "web3" / "_shared"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="web3 engine venv not installed (scripts/web3.sh install)")

KEY = "0x0123456789012345678901234567890123456789012345678901234567890123"
VAULT = "0x1719884eb866cb12b2287399b15f7db5e7d775ea"
DEST = "0x5e9ee1089755c3435139848e47e6635505d5a13a"
TOKEN = "USDC:0xeb62eee3685fc4c43992febcd9e75443"

# Runs in the venv: builds each SDK test case with hl_sign's builders and prints what it signs.
PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import hl_sign as s
from eth_account import Account
from eth_utils import to_hex
key = bytes.fromhex(sys.argv[2][2:])
out = {"address": Account.from_key(key).address}
order = s.order_wire(4, True, "1670.1", "0.0147", False, s.limit("Ioc"))
out["phantom"] = to_hex(s.action_hash(s.order_action([order]), None, 1677777606040, None))
dummy = {"type": "dummy", "num": 100000000000}  # the SDK's float_to_int_for_hashing(1000)
cases = {
    "dummy": dummy,
    "order": s.order_action([s.order_wire(1, True, "100", "100", False, s.limit("Gtc"))]),
    "cloid": s.order_action([s.order_wire(1, True, "100", "100", False, s.limit("Gtc"),
                                          "0x00000000000000000000000000000001")]),
    "tpsl": s.order_action([s.order_wire(1, True, "100", "100", False, s.trigger("103", True, "sl"))]),
}
for name, action in cases.items():
    for net, mainnet in (("mainnet", True), ("testnet", False)):
        sig = s.sign_l1(key, action, 0, mainnet)
        out[f"{name}/{net}"] = sig
        out[f"{name}/{net}/signer"] = s.recover_l1(action, sig, 0, mainnet)
for net, mainnet in (("mainnet", True), ("testnet", False)):
    out[f"vault/{net}"] = s.sign_l1(key, dummy, 0, mainnet, vault=sys.argv[3])
send = s.user_action({"destination": sys.argv[4], "amount": "1", "time": 1687816341423, "type": "usdSend"}, False)
out["usdSend"] = s.sign_user(key, send)
out["usdSend/signer"] = s.recover_user(send, out["usdSend"])
out["usdSend/action"] = send
withdraw = s.user_action(s.withdraw_action(sys.argv[4], "1", 1687816341423), False)
out["withdraw"] = s.sign_user(key, withdraw)
spot = s.user_action(s.spot_send_action(sys.argv[4], sys.argv[5], "1", 1687816341423), False)
out["spotSend"] = s.sign_user(key, spot)
out["spotSend/signer"] = s.recover_user(spot, out["spotSend"])
klass = s.user_action(s.usd_class_transfer_action("1", True, 1687816341423), False)
out["usdClassTransfer"] = s.sign_user(key, klass)
out["usdClassTransfer/signer"] = s.recover_user(klass, out["usdClassTransfer"])
errors = {}
for name, call in (("float", lambda: s.wire(0.1)), ("precision", lambda: s.wire("0.000000001")),
                   ("negative", lambda: s.wire("-1")), ("tif", lambda: s.limit("Fok")),
                   ("cloid", lambda: s.order_wire(1, True, "1", "1", False, s.limit("Gtc"), "0x1")),
                   ("usd", lambda: s.usd_int("1.0000001")), ("dest", lambda: s.usd_send_action("0x12", "1", 1))):
    try:
        call()
    except s.SignError as exc:
        errors[name] = str(exc)
out["errors"] = errors
out["wire"] = [s.wire(v) for v in ("100", "1670.10", "0.00000001", "0", "1e3", "83447.0")]
out["usd_int"] = [s.usd_int("12.5"), s.usd_int("0.000001")]
print(json.dumps(out))
"""


@pytest.fixture(scope="module")
def signed():
    proc = subprocess.run([str(PYTHON), "-c", PROBE, str(SHARED), KEY, VAULT, DEST, TOKEN], capture_output=True,
                          text=True, timeout=60, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def sig(r, s, v):
    return {"r": r, "s": s, "v": v}


SDK_VECTORS = {
    "dummy/mainnet": sig("0x53749d5b30552aeb2fca34b530185976545bb22d0b3ce6f62e31be961a59298",
                         "0x755c40ba9bf05223521753995abb2f73ab3229be8ec921f350cb447e384d8ed8", 27),
    "dummy/testnet": sig("0x542af61ef1f429707e3c76c5293c80d01f74ef853e34b76efffcb57e574f9510",
                         "0x17b8b32f086e8cdede991f1e2c529f5dd5297cbe8128500e00cbaf766204a613", 28),
    "order/mainnet": sig("0xd65369825a9df5d80099e513cce430311d7d26ddf477f5b3a33d2806b100d78e",
                         "0x2b54116ff64054968aa237c20ca9ff68000f977c93289157748a3162b6ea940e", 28),
    "order/testnet": sig("0x82b2ba28e76b3d761093aaded1b1cdad4960b3af30212b343fb2e6cdfa4e3d54",
                         "0x6b53878fc99d26047f4d7e8c90eb98955a109f44209163f52d8dc4278cbbd9f5", 27),
    "cloid/mainnet": sig("0x41ae18e8239a56cacbc5dad94d45d0b747e5da11ad564077fcac71277a946e3",
                         "0x3c61f667e747404fe7eea8f90ab0e76cc12ce60270438b2058324681a00116da", 27),
    "cloid/testnet": sig("0xeba0664bed2676fc4e5a743bf89e5c7501aa6d870bdb9446e122c9466c5cd16d",
                         "0x7f3e74825c9114bc59086f1eebea2928c190fdfbfde144827cb02b85bbe90988", 28),
    "tpsl/mainnet": sig("0x98343f2b5ae8e26bb2587daad3863bc70d8792b09af1841b6fdd530a2065a3f9",
                        "0x6b5bb6bb0633b710aa22b721dd9dee6d083646a5f8e581a20b545be6c1feb405", 27),
    "tpsl/testnet": sig("0x971c554d917c44e0e1b6cc45d8f9404f32172a9d3b3566262347d0302896a2e4",
                        "0x206257b104788f80450f8e786c329daa589aa0b32ba96948201ae556d5637eac", 28),
    "vault/mainnet": sig("0x3c548db75e479f8012acf3000ca3a6b05606bc2ec0c29c50c515066a326239",
                         "0x4d402be7396ce74fbba3795769cda45aec00dc3125a984f2a9f23177b190da2c", 28),
    "vault/testnet": sig("0xe281d2fb5c6e25ca01601f878e4d69c965bb598b88fac58e475dd1f5e56c362b",
                         "0x7ddad27e9a238d045c035bc606349d075d5c5cd00a6cd1da23ab5c39d4ef0f60", 27),
    "usdSend": sig("0x637b37dd731507cdd24f46532ca8ba6eec616952c56218baeff04144e4a77073",
                   "0x11a6a24900e6e314136d2592e2f8d502cd89b7c15b198e1bee043c9589f9fad7", 27),
    "withdraw": sig("0x8363524c799e90ce9bc41022f7c39b4e9bdba786e5f9c72b20e43e1462c37cf9",
                    "0x58b1411a775938b83e29182e8ef74975f9054c8e97ebf5ec2dc8d51bfc893881", 28),
    # from the SDK's sign_spot_transfer_action and sign_usd_class_transfer_action, not its tests
    "spotSend": sig("0x9e2c79d14dc6692a8da5b321826a6da77de25be3a7d894936cf1f7e32b5a95e0",
                    "0x5d22ac3ef4c390d8941bc84318f7b7bddaa6cb5451d206eed1a73df6931e357f", 27),
    "usdClassTransfer": sig("0xe265b4f0207b3e5ba5d7f863c150b41a25449bf6f6bda1cf278f4b2b6db25279",
                            "0x2469568d152f30acad5672b7657f0aa8e2f9d897fbd03b9b6b7dc3f443a1dff9", 27),
}


def test_the_phantom_agent_matches_production(signed):
    assert signed["phantom"] == "0x0fcbeda5ae3c4950a548021552a4fea2226858c4453571bf3f24ba017eac2908"


@pytest.mark.parametrize("case", sorted(SDK_VECTORS))
def test_signatures_match_the_sdk_vectors(signed, case):
    assert signed[case] == SDK_VECTORS[case]


def test_every_signature_recovers_to_its_own_key(signed):
    for case in ("dummy", "order", "cloid", "tpsl"):
        for net in ("mainnet", "testnet"):
            assert signed[f"{case}/{net}/signer"] == signed["address"]
    for case in ("usdSend", "spotSend", "usdClassTransfer"):
        assert signed[f"{case}/signer"] == signed["address"]


def test_a_user_signed_action_names_its_network(signed):
    action = signed["usdSend/action"]
    assert action["hyperliquidChain"] == "Testnet" and action["signatureChainId"] == "0x66eee"
    assert list(action)[:4] == ["destination", "amount", "time", "type"]


def test_numbers_go_on_the_wire_as_the_sdk_writes_them(signed):
    assert signed["wire"] == ["100", "1670.1", "0.00000001", "0", "1000", "83447"]
    assert signed["usd_int"] == [12_500_000, 1]


def test_what_cannot_be_signed_exactly_is_refused(signed):
    errors = signed["errors"]
    assert set(errors) == {"float", "precision", "negative", "tif", "cloid", "usd", "dest"}
    assert "not a float" in errors["float"] and "8 decimal places" in errors["precision"]
    assert "positive" in errors["negative"] and "6 decimal places" in errors["usd"]
