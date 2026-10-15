"""Hyperliquid action building and signing, run in the web3 venv (docs/hyperliquid.md "Signing").

Mirrors hyperliquid-python-sdk's ``utils/signing.py`` and the action shapes of its ``exchange.py`` byte
for byte, without the SDK (it pins an older eth-account than the engine's lock). Two schemes:

- **L1 actions** (order, cancel, batchModify, updateLeverage, updateIsolatedMargin): msgpack of the
  action — key order is part of the hash, so every builder here fixes it — then the nonce, the
  vault flag and the optional expiry, keccak'd into a "phantom agent" signed as EIP-712 under the
  ``Exchange`` domain (chain id 1337); ``source`` is ``a`` on mainnet, ``b`` on testnet.
- **User-signed actions** (usdSend, spotSend, sendAsset, sendToEvmWithData, usdClassTransfer):
  EIP-712 under the ``HyperliquidSignTransaction`` domain; ``hyperliquidChain`` names the network, so
  a signature for one network never replays on the other.

Prices, sizes and amounts are decimal strings throughout, never floats. Nothing here reads a key
from anywhere: the caller passes the key bytes it derived, and ``recover_*`` lets it check that a
signature is its own before anything is sent. The tests pin the SDK's own vectors.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

import msgpack
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak, to_hex

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
SIGNATURE_CHAIN_ID = "0x66eee"  # the SDK's; any chain id works, hyperliquidChain picks the network
WIRE_DECIMALS = 8
TIFS = ("Gtc", "Alo", "Ioc")
GROUPINGS = ("na", "normalTpsl", "positionTpsl")
_CLOID = re.compile(r"^0x[0-9a-f]{32}$")
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")

EIP712_DOMAIN = [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                 {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}]
USER_TYPES = {
    "usdSend": ("HyperliquidTransaction:UsdSend", [
        {"name": "hyperliquidChain", "type": "string"}, {"name": "destination", "type": "string"},
        {"name": "amount", "type": "string"}, {"name": "time", "type": "uint64"}]),
    "spotSend": ("HyperliquidTransaction:SpotSend", [
        {"name": "hyperliquidChain", "type": "string"}, {"name": "destination", "type": "string"},
        {"name": "token", "type": "string"}, {"name": "amount", "type": "string"}, {"name": "time", "type": "uint64"}]),
    "usdClassTransfer": ("HyperliquidTransaction:UsdClassTransfer", [
        {"name": "hyperliquidChain", "type": "string"}, {"name": "amount", "type": "string"},
        {"name": "toPerp", "type": "bool"}, {"name": "nonce", "type": "uint64"}]),
    "sendAsset": ("HyperliquidTransaction:SendAsset", [
        {"name": "hyperliquidChain", "type": "string"}, {"name": "destination", "type": "string"},
        {"name": "sourceDex", "type": "string"}, {"name": "destinationDex", "type": "string"},
        {"name": "token", "type": "string"}, {"name": "amount", "type": "string"},
        {"name": "fromSubAccount", "type": "string"}, {"name": "nonce", "type": "uint64"}]),
    # a call to the token's linked HyperEVM contract: for USDC, Circle's CCTP burn to another chain
    "sendToEvmWithData": ("HyperliquidTransaction:SendToEvmWithData", [
        {"name": "hyperliquidChain", "type": "string"}, {"name": "token", "type": "string"},
        {"name": "amount", "type": "string"}, {"name": "sourceDex", "type": "string"},
        {"name": "destinationRecipient", "type": "string"}, {"name": "addressEncoding", "type": "string"},
        {"name": "destinationChainId", "type": "uint32"}, {"name": "gasLimit", "type": "uint64"},
        {"name": "data", "type": "bytes"}, {"name": "nonce", "type": "uint64"}]),
}
SPOT_DEX = "spot"  # sendAsset's name for the spot balance; "" is the default perp dex


class SignError(ValueError):
    """An action that cannot be built or signed as asked; nothing was signed."""


# --- numbers on the wire ------------------------------------------------------------------------

def decimal(value, what: str = "value") -> Decimal:
    """A finite, non-negative Decimal from a string or an int; floats are refused (they round)."""
    if isinstance(value, bool) or isinstance(value, float):
        raise SignError(f"{what} must be a decimal string like 0.05, not a float")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise SignError(f"{what} must be a number like 0.05") from None
    if not number.is_finite() or number < 0:
        raise SignError(f"{what} must be a positive number")
    return number


def wire(value) -> str:
    """The SDK's float_to_wire for a Decimal: at most 8 decimals, normalized, no exponent, no -0."""
    number = value if isinstance(value, Decimal) else decimal(value)
    if number != number.quantize(Decimal(1).scaleb(-WIRE_DECIMALS)):
        raise SignError(f"{number} has more than {WIRE_DECIMALS} decimal places")
    text = format(number.normalize(), "f")
    return "0" if text in ("-0", "0", "") else text


# --- actions (key order matters: it is hashed) --------------------------------------------------

def limit(tif: str) -> dict:
    if tif not in TIFS:
        raise SignError(f"tif is one of {', '.join(TIFS)}")
    return {"limit": {"tif": tif}}


def trigger(trigger_px, is_market: bool, tpsl: str) -> dict:
    if tpsl not in ("tp", "sl"):
        raise SignError("tpsl is tp or sl")
    return {"trigger": {"isMarket": bool(is_market), "triggerPx": wire(trigger_px), "tpsl": tpsl}}


def order_wire(asset: int, is_buy: bool, price, size, reduce_only: bool, kind: dict, cloid: str | None = None) -> dict:
    if not isinstance(asset, int) or isinstance(asset, bool) or asset < 0:
        raise SignError("asset must be a non-negative integer")
    order = {"a": asset, "b": bool(is_buy), "p": wire(price), "s": wire(size), "r": bool(reduce_only), "t": kind}
    if cloid is not None:
        if not isinstance(cloid, str) or not _CLOID.match(cloid):
            raise SignError("cloid must be 0x and 32 lower-case hex digits")
        order["c"] = cloid
    return order


def order_action(orders: list[dict], grouping: str = "na") -> dict:
    if grouping not in GROUPINGS:
        raise SignError(f"grouping is one of {', '.join(GROUPINGS)}")
    if not orders:
        raise SignError("an order action needs at least one order")
    return {"type": "order", "orders": orders, "grouping": grouping}


def cancel_action(asset: int, oid: int) -> dict:
    return {"type": "cancel", "cancels": [{"a": asset, "o": oid}]}


def cancel_by_cloid_action(asset: int, cloid: str) -> dict:
    return {"type": "cancelByCloid", "cancels": [{"asset": asset, "cloid": cloid}]}


def modify_action(oid, order: dict) -> dict:
    """oid is an order id (int) or a cloid string."""
    return {"type": "batchModify", "modifies": [{"oid": oid, "order": order}]}


def leverage_action(asset: int, is_cross: bool, leverage: int) -> dict:
    if not isinstance(leverage, int) or isinstance(leverage, bool) or leverage < 1:
        raise SignError("leverage is a whole number of at least 1")
    return {"type": "updateLeverage", "asset": asset, "isCross": bool(is_cross), "leverage": leverage}


def margin_action(asset: int, ntli: int) -> dict:
    """ntli: the change in isolated margin, in millionths of a USDC (negative removes margin)."""
    if not isinstance(ntli, int) or isinstance(ntli, bool) or ntli == 0:
        raise SignError("the margin change must be a non-zero whole number of micro-USDC")
    return {"type": "updateIsolatedMargin", "asset": asset, "isBuy": True, "ntli": ntli}


def usd_int(amount) -> int:
    """USDC in millionths, exactly (the SDK's float_to_usd_int without the float)."""
    number = decimal(amount, "amount") * 1_000_000
    if number != number.to_integral_value():
        raise SignError("a USDC amount has at most 6 decimal places")
    return int(number)


def _destination(address: str) -> str:
    if not isinstance(address, str) or not _ADDRESS.match(address):
        raise SignError("the destination must be a 0x address of 40 hex digits")
    return address.lower()


def usd_send_action(destination: str, amount, time: int) -> dict:
    return {"destination": _destination(destination), "amount": wire(amount), "time": time, "type": "usdSend"}


def spot_send_action(destination: str, token: str, amount, time: int) -> dict:
    return {"destination": _destination(destination), "amount": wire(amount), "token": token, "time": time,
            "type": "spotSend"}


def usd_class_transfer_action(amount, to_perp: bool, nonce: int) -> dict:
    return {"type": "usdClassTransfer", "amount": wire(amount), "toPerp": bool(to_perp), "nonce": nonce}


def send_asset_action(destination: str, source_dex: str, destination_dex: str, token: str, amount,
                      nonce: int) -> dict:
    """A token from one balance (``spot``, or a perp dex by name, ``""`` the default one) to another
    address's balance; the account itself, never a subaccount, sends it."""
    for dex in (source_dex, destination_dex):
        if not isinstance(dex, str):
            raise SignError("a dex is spot, or a perp dex's name (empty for the default one)")
    return {"type": "sendAsset", "destination": _destination(destination), "sourceDex": source_dex,
            "destinationDex": destination_dex, "token": token, "amount": wire(amount), "fromSubAccount": "",
            "nonce": nonce}


def send_to_evm_action(token: str, amount, source_dex: str, recipient: str, domain: int, gas_limit: int,
                       nonce: int, data: str = "0x") -> dict:
    """A token from a balance (``spot``, or ``""`` the default perp dex) through its linked HyperEVM
    contract to an EVM address on another chain: for USDC, a CCTP burn to ``domain`` (Circle's domain id,
    not a chain id) that Circle mints and forwards there."""
    if not isinstance(source_dex, str):
        raise SignError("a dex is spot, or a perp dex's name (empty for the default one)")
    for value, what in ((domain, "the destination domain"), (gas_limit, "the gas limit")):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SignError(f"{what} must be a whole number")
    if not isinstance(data, str) or not re.match(r"^0x([0-9a-f]{2})*$", data):
        raise SignError("data must be 0x and lower-case hex bytes")
    return {"type": "sendToEvmWithData", "token": token, "amount": wire(amount), "sourceDex": source_dex,
            "destinationRecipient": _destination(recipient), "addressEncoding": "hex",
            "destinationChainId": domain, "gasLimit": gas_limit, "data": data, "nonce": nonce}


# --- hashing and signing ------------------------------------------------------------------------

def action_hash(action, vault: str | None, nonce: int, expires_after: int | None) -> bytes:
    data = msgpack.packb(action)
    data += nonce.to_bytes(8, "big")
    if vault is None:
        data += b"\x00"
    else:
        data += b"\x01" + bytes.fromhex(vault.removeprefix("0x"))
    if expires_after is not None:
        data += b"\x00" + expires_after.to_bytes(8, "big")
    return keccak(data)


def _l1_payload(action, nonce: int, mainnet: bool, vault, expires_after) -> dict:
    agent = {"source": "a" if mainnet else "b", "connectionId": action_hash(action, vault, nonce, expires_after)}
    return {"domain": {"chainId": 1337, "name": "Exchange", "verifyingContract": ZERO_ADDRESS, "version": "1"},
            "types": {"Agent": [{"name": "source", "type": "string"}, {"name": "connectionId", "type": "bytes32"}],
                      "EIP712Domain": EIP712_DOMAIN},
            "primaryType": "Agent", "message": agent}


def _user_payload(action: dict) -> dict:
    primary, types = USER_TYPES[action["type"]]
    return {"domain": {"name": "HyperliquidSignTransaction", "version": "1",
                       "chainId": int(action["signatureChainId"], 16), "verifyingContract": ZERO_ADDRESS},
            "types": {primary: types, "EIP712Domain": EIP712_DOMAIN}, "primaryType": primary, "message": action}


def _sign(key: bytes, payload: dict) -> dict:
    signed = Account.sign_message(encode_typed_data(full_message=payload), private_key=key)
    return {"r": to_hex(signed.r), "s": to_hex(signed.s), "v": signed.v}


def _recover(payload: dict, signature: dict) -> str:
    return Account.recover_message(encode_typed_data(full_message=payload),
                                   vrs=(signature["v"], int(signature["r"], 16), int(signature["s"], 16)))


def sign_l1(key: bytes, action, nonce: int, mainnet: bool, vault: str | None = None,
            expires_after: int | None = None) -> dict:
    return _sign(key, _l1_payload(action, nonce, mainnet, vault, expires_after))


def recover_l1(action, signature: dict, nonce: int, mainnet: bool, vault: str | None = None,
               expires_after: int | None = None) -> str:
    return _recover(_l1_payload(action, nonce, mainnet, vault, expires_after), signature)


def user_action(action: dict, mainnet: bool) -> dict:
    """The action as it is signed and sent: a copy with the signature chain and the network added."""
    if action.get("type") not in USER_TYPES:
        raise SignError(f"{action.get('type')!r} is not a user-signed action here")
    return {**action, "signatureChainId": SIGNATURE_CHAIN_ID, "hyperliquidChain": "Mainnet" if mainnet else "Testnet"}


def sign_user(key: bytes, action: dict) -> dict:
    """Signs an action from ``user_action`` (its network is already in it)."""
    return _sign(key, _user_payload(action))


def recover_user(action: dict, signature: dict) -> str:
    return _recover(_user_payload(action), signature)


def envelope(action, nonce: int, signature: dict, vault: str | None = None, expires_after: int | None = None) -> dict:
    """The body POSTed to /exchange."""
    return {"action": action, "nonce": nonce, "signature": signature, "vaultAddress": vault,
            "expiresAfter": expires_after}
