"""A rollup's fees beyond gas, read from its own oracles (docs/web3.md "Chains and RPC").

Shared by the signer (a quote's stated maximum) and the reader (``gas``'s estimate), so both count
the same thing. A chain's ``fee`` in ``chains.py`` names its model: ``op`` (the OP Stack
GasPriceOracle's L1 data fee and operator fee), ``op-token`` (the same, the L1 fee converted into the
native token by the oracle's ``tokenRatio``: Mantle) or ``scroll`` (Scroll's L1GasPriceOracle). The
L1 fee is quoted for a transaction's own signed bytes; the reader signs a fixed sample with a public
throwaway key for that, and nothing either signs here is ever broadcast.
"""

from __future__ import annotations

from rpc import ChainError

GAS_PRICE_ORACLE = "0x420000000000000000000000000000000000000F"
L1_ORACLES = {"op": GAS_PRICE_ORACLE, "op-token": GAS_PRICE_ORACLE,
              "scroll": "0x5300000000000000000000000000000000000002"}
# Known to everyone, holds nothing: it signs only the reader's sizing samples, which are never sent.
# Never fund its address and never list it as an account; it is not a wallet.
SAMPLE_KEY = bytes([0x11]) * 32


def _int(value) -> int:
    return int(value, 16) if isinstance(value, str) and value.startswith("0x") and len(value) > 2 else 0


def _selector(signature: str) -> str:
    from eth_utils import keccak
    return keccak(text=signature)[:4].hex()


def signed(tx: dict, key: bytes) -> bytes:
    """A type-2 transaction's signed bytes, to size its L1 fee."""
    from eth_account import Account
    return bytes(Account.sign_transaction({"type": 2, **tx}, key).raw_transaction)


def l1_fee(r, raw: bytes, model: str, block: str = "latest") -> int:
    """The L1 data fee of a transaction's bytes, in the native coin; raises when it cannot be read."""
    from eth_abi import encode as abi_encode
    data = "0x" + _selector("getL1Fee(bytes)") + abi_encode(["bytes"], [raw]).hex()
    got = r.call("eth_call", [{"to": L1_ORACLES[model], "data": data}, block])
    if not got or len(got) < 66:
        raise ChainError("the chain's L1 data fee could not be read; try again")
    fee = _int(got[:66])
    if model == "op-token":
        ratio = r.call("eth_call", [{"to": GAS_PRICE_ORACLE, "data": "0x" + _selector("tokenRatio()")}, block])
        if not ratio or len(ratio) < 66 or not _int(ratio[:66]):
            raise ChainError("the chain's L1 fee token ratio could not be read; try again")
        fee *= _int(ratio[:66])
    return fee


def operator_fee(r, gas: int, block: str = "latest", required: bool = False) -> int:
    """An OP Stack chain's operator fee for this much gas (Isthmus and later). Only an oracle without
    the function (a revert, or no answer data) means none, and only where it may be absent; a read
    that fails any other way raises, so a stated maximum is never short of it."""
    from eth_abi import encode as abi_encode
    data = "0x" + _selector("getOperatorFee(uint256)") + abi_encode(["uint256"], [gas]).hex()
    reply = r.request("eth_call", [{"to": GAS_PRICE_ORACLE, "data": data}, block])
    error = reply.get("error")
    if error:
        text = str(error.get("message") if isinstance(error, dict) else error).lower()
        code = error.get("code") if isinstance(error, dict) else None
        if (code == 3 or "revert" in text) and not required:
            return 0
        raise ChainError("the chain's operator fee could not be read; try again")
    got = reply.get("result")
    if isinstance(got, str) and len(got) >= 66:
        return _int(got[:66])
    if required:
        raise ChainError("the chain's operator fee could not be read; try again")
    return 0
