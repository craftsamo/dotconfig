"""Circle CCTP (V2) pieces of a Hyperliquid deposit, for the signer (docs/hyperliquid.md "Deposits").

A deposit burns the chain's native USDC with ``TokenMessengerV2.depositForBurnWithHook`` towards HyperEVM
(domain 19), minted to Circle's ``CctpForwarder`` there and callable only by it, with hook data that
names the HyperCore account and its balance; the forwarder credits that account through
``CoreDepositWallet``. Every address comes from ``chains``; nothing here takes one from a caller but
the HyperCore recipient, and nothing here signs.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
import json
import urllib.error
import urllib.request

import chains
import rpc
from rpc import ChainError

BURN = "779b432d"           # depositForBurnWithHook(uint256,uint32,bytes32,address,bytes32,uint256,uint32,bytes)
APPROVE = "095ea7b3"        # approve(address,uint256)
NEW_ACCOUNT_FEE = "820b3e1e"  # CoreDepositWallet.newCoreAccountFee(): HyperCore units, 8 decimals
FAST = 1000                 # minFinalityThreshold: Circle's fast attestation, seconds rather than minutes
MAGIC = b"cctp-forward"
DEX = {"perp": 0, "spot": 0xFFFFFFFF}  # the HyperCore balance the forwarder credits
IRIS_TIMEOUT = 15


def hook(recipient: str, dex: str) -> bytes:
    """The forwarder's 56-byte hook: magic padded to 24 bytes, version 0, payload length 24, the HyperCore
    recipient's 20 bytes and the destination balance (CctpForwarderHookData)."""
    address = bytes.fromhex(recipient.removeprefix("0x"))
    if len(address) != 20 or not any(address):
        raise ChainError("the Hyperliquid account must be a 0x address that is not zero")
    return MAGIC.ljust(24, b"\0") + (0).to_bytes(4, "big") + (24).to_bytes(4, "big") + address + \
        DEX[dex].to_bytes(4, "big")


def burn_data(amount: int, usdc: str, network: str, max_fee: int, recipient: str, dex: str) -> str:
    """depositForBurnWithHook's calldata: the mint goes to the forwarder, which alone may relay it."""
    from eth_abi import encode as abi_encode
    forwarder = bytes.fromhex(chains.HYPEREVM[network]["forwarder"][2:]).rjust(32, b"\0")
    args = abi_encode(["uint256", "uint32", "bytes32", "address", "bytes32", "uint256", "uint32", "bytes"],
                      [amount, chains.HYPEREVM_DOMAIN, forwarder, usdc, forwarder, max_fee, FAST,
                       hook(recipient, dex)])
    return "0x" + BURN + args.hex()


def approve_data(spender: str, amount: int) -> str:
    from eth_abi import encode as abi_encode
    return "0x" + APPROVE + abi_encode(["address", "uint256"], [spender, amount]).hex()


def opening_fee(network: str, override: str | None = None) -> int:
    """What Circle's CoreDepositWallet keeps from a deposit into an account HyperCore does not have yet,
    in USDC base units (6 decimals), as its contract states it now (owner-set; 0 turns it off)."""
    url = override if override and rpc.testing() else chains.HYPEREVM[network]["rpc"]
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": chains.HYPEREVM[network]["core_deposit_wallet"], "data": "0x" + NEW_ACCOUNT_FEE},
                       "latest"]}
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": rpc.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=IRIS_TIMEOUT) as response:
            found = json.loads(response.read()).get("result")
        return -(-int(found, 16) // 100)  # 8 decimals on HyperCore, 6 for USDC here: rounded up, never under
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError):
        raise ChainError(f"{chains.HYPEREVM[network]['name']} did not say what opening a new account costs; nothing "
                         "was quoted") from None


def max_fee(network: str, domain: int, amount: int, override: str | None = None) -> int:
    """The most Circle may keep, in USDC base units: its fast-transfer rate on the amount, rounded up, plus
    the forwarding fee's high estimate, both from its fee API for a HyperCore deposit from this domain."""
    base = override if override and rpc.testing() else chains.CCTP_IRIS[network]
    url = f"{base}/v2/burn/USDC/fees/{domain}/{chains.HYPEREVM_DOMAIN}?forward=true&hyperCoreDeposit=true"
    request = urllib.request.Request(url, headers={"User-Agent": rpc.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=IRIS_TIMEOUT) as response:
            found = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ChainError(f"Circle's fee service could not be read ({type(exc).__name__}); nothing was quoted") \
            from None
    rows = [r for r in found if isinstance(r, dict) and r.get("finalityThreshold") == FAST] \
        if isinstance(found, list) else []
    try:
        bps = Decimal(str(rows[0]["minimumFee"]))
        forward = int(rows[0]["forwardFee"]["high"])
    except (IndexError, KeyError, TypeError, ValueError, ArithmeticError):
        raise ChainError("Circle's fee service returned an unexpected answer; nothing was quoted") from None
    if bps < 0 or forward < 0:
        raise ChainError("Circle's fee service returned a negative fee; nothing was quoted")
    return int((Decimal(amount) * bps / 10_000).to_integral_value(ROUND_CEILING)) + forward
