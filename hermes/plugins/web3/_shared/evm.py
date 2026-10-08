"""EVM reads of the ``evm`` tool, run in the engine venv (docs/web3.md "Reads").

Every action takes the engine context (``ctx.rpc``, ``ctx.decoder``, ``ctx.prices``, ``ctx.chain``)
and the caller's arguments, and returns plain JSON. Text read from the chain (token names and
symbols, revert strings, decoded strings) is wrapped as ``{"untrusted": …}``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import re

from eth_abi import decode as abi_decode, encode as abi_encode
from eth_utils import keccak, to_checksum_address

import abi
import chains
from prices import usd
from rpc import ChainError

LOG_RANGE = 5000            # blocks per eth_getLogs request
SCAN_BLOCKS = 10_000        # activity without a provider key: recent blocks scanned
ALLOWANCE_BLOCKS = 50_000   # allowances: recent blocks scanned by default
MAX_SCAN_BLOCKS = 200_000
MAX_LOGS = 100
MAX_LOG_REQUESTS = 24      # eth_getLogs calls one logs action may spend splitting a refused range
MAX_TOKENS = 40
MAX_PORTFOLIO_CHAINS = 6
MAX_TRACE_CALLS = 150
TOP = 5
UNLIMITED = 2 ** 255

TX_TYPES = {0: "legacy", 1: "access-list", 2: "eip-1559", 3: "blob", 4: "set-code (EIP-7702)"}
EIP1967_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_BEACON = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
EIP1967_ADMIN = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
# OpenZeppelin's pre-EIP-1967 (zos) proxies, still behind long-lived tokens such as USDC.
ZOS_IMPL = "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"
ZOS_ADMIN = "0x10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b"
ENS_REGISTRY = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"
SEL = {"name": "06fdde03", "symbol": "95d89b41", "decimals": "313ce567", "totalSupply": "18160ddd",
       "balanceOf": "70a08231", "allowance": "dd62ed3e", "isApprovedForAll": "e985e9c5",
       "supportsInterface": "01ffc9a7", "resolver": "0178b8bf", "addr": "3b3b57de", "ens_name": "691f3431",
       "implementation": "5c60da1b"}
INTERFACES = {"ERC-721": "80ac58cd", "ERC-1155": "d9b67a26"}
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


# --- small helpers ------------------------------------------------------------------------------

def h2i(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(value, 16) if str(value).startswith("0x") else int(value)


def units(value: int, decimals: int) -> str:
    """A base-unit amount in whole units, exact, without exponent."""
    text = format(Decimal(value) / (Decimal(10) ** decimals), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def as_float(value: int, decimals: int) -> float:
    return float(Decimal(value) / (Decimal(10) ** decimals))


def gwei(value: int) -> float:
    return round(value / 1e9, 4)


def when(timestamp) -> str | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(h2i(timestamp), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def checksum(value: str | None) -> str | None:
    return to_checksum_address(value) if value else None


def require_hash(value, what: str = "hash") -> str:
    if not isinstance(value, str) or not _HASH.match(value):
        raise ChainError(f"{what} must be 0x followed by 64 hex digits")
    return value.lower()


def namehash(name: str) -> bytes:
    node = b"\x00" * 32
    for label in reversed(name.split(".")) if name else []:
        node = keccak(node + keccak(text=label))
    return node


def eth_call(ctx, to: str, data: str, block: str = "latest"):
    return ctx.rpc.call("eth_call", [{"to": to, "data": data}, block])


def resolve_address(ctx, value) -> tuple[str, str | None]:
    """(checksummed address, ENS name or None); ENS names resolve on Ethereum's own registry."""
    if not isinstance(value, str) or not value:
        raise ChainError("an address is required")
    value = value.strip()
    if _ADDRESS.match(value):
        return to_checksum_address(value), None
    if value.lower().endswith(".eth"):
        if not re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.eth$", value.lower()):
            raise ChainError("only plain ASCII ENS names are accepted")
        name = value.lower()
        rpc = ctx.rpc if ctx.chain == "ethereum" else ctx.rpc_for("ethereum")
        node = namehash(name)
        resolver = abi_decode(["address"], _bytes(rpc.call(
            "eth_call", [{"to": ENS_REGISTRY, "data": "0x" + SEL["resolver"] + node.hex()}, "latest"])))[0]
        if int(resolver, 16) == 0:
            raise ChainError(f"{name} has no ENS resolver")
        address = abi_decode(["address"], _bytes(rpc.call(
            "eth_call", [{"to": resolver, "data": "0x" + SEL["addr"] + node.hex()}, "latest"])))[0]
        if int(address, 16) == 0:
            raise ChainError(f"{name} does not resolve to an address")
        return to_checksum_address(address), name
    raise ChainError(f"not an address or ENS name: {value[:80]!r}")


def reverse_ens(ctx, address: str) -> str | None:
    """The primary ENS name of an address, only if it resolves back to the same address."""
    if ctx.chain != "ethereum":
        return None
    try:
        node = namehash(address.lower()[2:] + ".addr.reverse")
        resolver = abi_decode(["address"], _bytes(eth_call(ctx, ENS_REGISTRY, "0x" + SEL["resolver"] + node.hex())))[0]
        if int(resolver, 16) == 0:
            return None
        name = abi_decode(["string"], _bytes(eth_call(ctx, resolver, "0x" + SEL["ens_name"] + node.hex())))[0]
        if not name:
            return None
        forward, _ = resolve_address(ctx, name)
        return name if forward == to_checksum_address(address) else None
    except Exception:
        return None


def _bytes(result) -> bytes:
    return bytes.fromhex((result or "0x")[2:])


def _text(result) -> str | None:
    """A string return value; bytes32 strings (older tokens) included."""
    raw = _bytes(result)
    if not raw:
        return None
    try:
        return abi_decode(["string"], raw)[0]
    except Exception:
        return raw[:32].rstrip(b"\x00").decode("utf-8", "replace") or None


def token_meta(ctx, tokens: list[str], with_name: bool = False) -> dict[str, dict]:
    """symbol / decimals (/ name) per token address, read in one batch."""
    fields = ["symbol", "decimals"] + (["name"] if with_name else [])
    calls = [("eth_call", [{"to": t, "data": "0x" + SEL[f]}, "latest"]) for t in tokens for f in fields]
    results = ctx.rpc.batch(calls)
    meta = {}
    for i, token in enumerate(tokens):
        row = dict(zip(fields, results[i * len(fields):(i + 1) * len(fields)]))
        decimals = None
        if row.get("decimals") and len(_bytes(row["decimals"])) >= 32:
            decimals = int.from_bytes(_bytes(row["decimals"])[:32], "big")
            decimals = decimals if decimals <= 36 else None
        symbol = _text(row.get("symbol"))
        meta[token.lower()] = {"symbol": abi.untrusted(symbol) if symbol else None, "decimals": decimals,
                               **({"name": abi.untrusted(_text(row["name"]))} if with_name and _text(row.get("name")) else {})}
    return meta


def block_param(value) -> str:
    if value is None or value == "":
        return "latest"
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return hex(int(value))
    if isinstance(value, str) and value in ("latest", "safe", "finalized", "earliest", "pending"):
        return value
    if isinstance(value, str) and re.match(r"^0x[0-9a-fA-F]{1,16}$", value):
        return value.lower()
    raise ChainError("block must be a number, a block hash, or latest / safe / finalized")


def pin(ctx, value) -> tuple[str, int | None]:
    """(block parameter, block number) for a read: a tag is resolved to the block it means now,
    so every read of one action sees the same block and the result can name it."""
    tag = block_param(value)
    if tag == "latest":
        number = h2i(ctx.rpc.call("eth_blockNumber"))
        return hex(number), number
    if tag in ("safe", "finalized", "earliest"):
        found = ctx.rpc.call("eth_getBlockByNumber", [tag, False]) or {}
        if found.get("number"):
            return found["number"], h2i(found["number"])
        return tag, None
    if tag == "pending":
        return tag, None
    return tag, h2i(tag)


def _native(ctx) -> dict:
    return chains.EVM[ctx.chain]


# --- block --------------------------------------------------------------------------------------

def block(ctx, args) -> dict:
    ref = args.get("block")
    if isinstance(ref, str) and _HASH.match(ref):
        data = ctx.rpc.call("eth_getBlockByHash", [ref, True])
    else:
        data = ctx.rpc.call("eth_getBlockByNumber", [block_param(ref), True])
    if not data:
        raise ChainError("block not found")
    native = _native(ctx)
    txs = data.get("transactions") or []
    number = h2i(data["number"])
    base_fee = h2i(data.get("baseFeePerGas"))
    gas_used, gas_limit = h2i(data.get("gasUsed")), h2i(data.get("gasLimit"))
    burned = base_fee * gas_used
    types = Counter(TX_TYPES.get(h2i(tx.get("type")), f"type {h2i(tx.get('type'))}") for tx in txs)
    targets = Counter(checksum(tx["to"]) for tx in txs if tx.get("to"))
    price = ctx.prices.native(ctx.chain)
    result = {
        "chain": ctx.chain, "number": number, "hash": data.get("hash"), "parent": data.get("parentHash"),
        "time": when(data.get("timestamp")), "fee_recipient": checksum(data.get("miner")),
        "transactions": len(txs), "by_type": dict(types),
        "contract_creations": sum(1 for tx in txs if not tx.get("to")),
        "gas_used": gas_used, "gas_limit": gas_limit,
        "gas_used_pct": round(100 * gas_used / gas_limit, 2) if gas_limit else None,
        "base_fee_gwei": gwei(base_fee) if data.get("baseFeePerGas") else None,
        "burned": units(burned, native["decimals"]), "burned_usd": usd(as_float(burned, native["decimals"]), price),
        "size_bytes": h2i(data.get("size")),
        "most_called": [{"address": a, "transactions": n} for a, n in targets.most_common(TOP)],
        "explorer": chains.explorer(ctx.chain, "block", str(number)),
    }
    if data.get("blobGasUsed") is not None:
        result["blob_gas_used"] = h2i(data["blobGasUsed"])
        result["excess_blob_gas"] = h2i(data.get("excessBlobGas"))
    if data.get("withdrawals") is not None:
        result["withdrawals"] = len(data["withdrawals"])
    if args.get("detail"):
        result.update(_block_detail(ctx, number, txs, base_fee, price))
        for entry in result["most_called"][:3]:
            _, name = ctx.decoder.contract(entry["address"])
            if name:
                entry["verified_name"] = abi.untrusted(name)
    return result


def _block_detail(ctx, number: int, txs: list[dict], base_fee: int, price) -> dict:
    receipts, error = ctx.rpc.try_call("eth_getBlockReceipts", [hex(number)])
    if not isinstance(receipts, list):
        return {"detail_unavailable": error or "the RPC did not return the block's receipts"}
    decimals = _native(ctx)["decimals"]
    by_hash = {tx["hash"]: tx for tx in txs}
    fees, priority, failed = [], 0, 0
    for receipt in receipts:
        used, paid = h2i(receipt.get("gasUsed")), h2i(receipt.get("effectiveGasPrice"))
        fee = used * paid
        priority += max(paid - base_fee, 0) * used
        failed += h2i(receipt.get("status")) == 0
        fees.append((fee, receipt))
    fees.sort(key=lambda item: item[0], reverse=True)
    top = []
    for fee, receipt in fees[:TOP]:
        tx = by_hash.get(receipt.get("transactionHash"), {})
        call = ctx.decoder.function(tx.get("input") or "0x", tx.get("to")) if tx.get("to") else None
        top.append({"hash": receipt.get("transactionHash"), "from": checksum(receipt.get("from")),
                    "to": checksum(receipt.get("to")), "fee": units(fee, decimals),
                    "fee_usd": usd(as_float(fee, decimals), price),
                    "call": (call or {}).get("function") or (call or {}).get("selector"),
                    "status": "success" if h2i(receipt.get("status")) == 1 else "failed"})
    total = sum(fee for fee, _ in fees)
    return {"fees_total": units(total, decimals), "fees_total_usd": usd(as_float(total, decimals), price),
            "priority_fees": units(priority, decimals), "failed_transactions": failed, "top_by_fee": top}


# --- transaction --------------------------------------------------------------------------------

def tx(ctx, args) -> dict:
    tx_hash = require_hash(args.get("hash"))
    found, receipt = ctx.rpc.batch([("eth_getTransactionByHash", [tx_hash]),
                                    ("eth_getTransactionReceipt", [tx_hash])])
    if not found:
        raise ChainError(f"transaction {tx_hash} not found on {ctx.chain}")
    native = _native(ctx)
    decimals = native["decimals"]
    price = ctx.prices.native(ctx.chain)
    value = h2i(found.get("value"))
    result = {
        "chain": ctx.chain, "hash": tx_hash, "type": TX_TYPES.get(h2i(found.get("type")), str(found.get("type"))),
        "from": checksum(found.get("from")), "to": checksum(found.get("to")), "nonce": h2i(found.get("nonce")),
        "value": units(value, decimals), "value_usd": usd(as_float(value, decimals), price),
        "symbol": native["symbol"], "explorer": chains.explorer(ctx.chain, "tx", tx_hash),
    }
    if not receipt:
        result.update(status="pending", gas_limit=h2i(found.get("gas")))
        result["call"] = ctx.decoder.function(found.get("input") or "0x", found.get("to"))
        return result
    number = h2i(receipt.get("blockNumber"))
    head = ctx.rpc.call("eth_getBlockByNumber", [hex(number), False]) or {}
    base_fee = h2i(head.get("baseFeePerGas"))
    used, paid = h2i(receipt.get("gasUsed")), h2i(receipt.get("effectiveGasPrice") or found.get("gasPrice"))
    fee = used * paid
    success = h2i(receipt.get("status")) == 1
    result.update({
        "status": "success" if success else "failed", "block": number, "time": when(head.get("timestamp")),
        "position": h2i(found.get("transactionIndex")),
        "gas": {"limit": h2i(found.get("gas")), "used": used,
                "price_gwei": gwei(paid), "base_fee_gwei": gwei(base_fee) if head.get("baseFeePerGas") else None},
        "fee": {"total": units(fee, decimals), "total_usd": usd(as_float(fee, decimals), price),
                "burned": units(base_fee * used, decimals),
                "priority": units(max(paid - base_fee, 0) * used, decimals)},
    })
    if receipt.get("l1Fee") is not None:
        result["fee"]["l1_data_fee"] = units(h2i(receipt["l1Fee"]), decimals)
    if receipt.get("contractAddress"):
        result["created_contract"] = checksum(receipt["contractAddress"])
    if found.get("authorizationList"):
        result["authorizations"] = [{"delegate_to": checksum(a.get("address")), "chain_id": h2i(a.get("chainId")),
                                     "nonce": h2i(a.get("nonce"))} for a in found["authorizationList"]]
    result["call"] = ctx.decoder.function(found.get("input") or "0x", found.get("to")) if found.get("to") else None
    if not success:
        result["revert"] = _revert(ctx, found, number)
    logs = receipt.get("logs") or []
    result["events"] = [ctx.decoder.event(log) for log in logs[:MAX_LOGS]]
    if len(logs) > MAX_LOGS:
        result["events_omitted"] = len(logs) - MAX_LOGS
    trace = _trace(ctx, tx_hash) if args.get("trace") else None
    if trace is not None:
        result["internal_calls"] = trace
    result.update(_balance_changes(ctx, found, logs, fee, success, trace))
    return result


def _revert(ctx, found: dict, number: int) -> dict:
    """The revert reason, by replaying the call on the state before the block (approximate: earlier
    transactions of the same block are not applied)."""
    call = {"from": found.get("from"), "to": found.get("to"), "data": found.get("input"),
            "value": found.get("value"), "gas": found.get("gas")}
    try:
        reply = ctx.rpc.request("eth_call", [call, hex(max(number - 1, 0))])
    except ChainError as exc:
        return {"unavailable": str(exc)}
    error = reply.get("error") if isinstance(reply.get("error"), dict) else None
    if not error:
        return {"note": "the replay did not revert; the failure depends on earlier transactions in its block "
                        "or ran out of gas"}
    data = error.get("data")
    if isinstance(data, dict):
        data = data.get("data")
    decoded = ctx.decoder.revert(data if isinstance(data, str) else None, found.get("to"))
    return {"replayed": True, **(decoded or {"message": abi.untrusted(error.get("message", ""))})}


def _trace(ctx, tx_hash: str) -> list | dict:
    traced, error = ctx.rpc.try_call("debug_traceTransaction", [tx_hash, {"tracer": "callTracer"}])
    if not isinstance(traced, dict):
        return {"unavailable": error or "the RPC does not trace transactions; a provider key may"}
    calls: list[dict] = []

    def walk(frame, depth):
        if len(calls) >= MAX_TRACE_CALLS:
            return
        entry = {"depth": depth, "type": frame.get("type"), "from": checksum(frame.get("from")),
                 "to": checksum(frame.get("to")), "value": units(h2i(frame.get("value")), _native(ctx)["decimals"])}
        if frame.get("input") and len(frame["input"]) >= 10 and frame.get("to"):
            entry["call"] = ctx.decoder.function(frame["input"], frame["to"]) if depth <= 2 else \
                {"selector": frame["input"][:10]}
        if frame.get("error"):
            entry["error"] = abi.untrusted(frame["error"])
        calls.append(entry)
        for child in frame.get("calls") or []:
            walk(child, depth + 1)

    walk(traced, 0)
    return calls


def _balance_changes(ctx, found: dict, logs: list[dict], fee: int, success: bool, trace) -> dict:
    deltas: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    nfts = []
    sender = checksum(found.get("from"))
    deltas[sender]["native"] -= fee
    if success:
        value = h2i(found.get("value"))
        if value and found.get("to"):
            deltas[sender]["native"] -= value
            deltas[checksum(found["to"])]["native"] += value
        for frame in trace if isinstance(trace, list) else []:
            amount = Decimal(frame["value"]) * (Decimal(10) ** _native(ctx)["decimals"])
            if frame["depth"] > 0 and amount and frame["type"] in ("CALL", "CREATE", "CREATE2") and frame["to"]:
                deltas[frame["from"]]["native"] -= int(amount)
                deltas[frame["to"]]["native"] += int(amount)
    for log in logs:
        topics = log.get("topics") or []
        if not topics or topics[0].lower() != abi.TRANSFER_TOPIC:
            continue
        token = log["address"].lower()
        if len(topics) == 3 and len(_bytes(log.get("data"))) == 32:
            amount = int.from_bytes(_bytes(log["data"]), "big")
            deltas[checksum("0x" + topics[1][-40:])][token] -= amount
            deltas[checksum("0x" + topics[2][-40:])][token] += amount
        elif len(topics) == 4:
            nfts.append({"contract": checksum(token), "token_id": abi.number(int(topics[3], 16)),
                         "from": checksum("0x" + topics[1][-40:]), "to": checksum("0x" + topics[2][-40:])})
    tokens = sorted({asset for assets in deltas.values() for asset in assets if asset != "native"})
    meta = token_meta(ctx, tokens[:15]) if tokens else {}
    native = _native(ctx)
    changes = []
    for address, assets in deltas.items():
        rows = []
        for asset, amount in assets.items():
            if amount == 0:
                continue
            if asset == "native":
                rows.append({"asset": native["symbol"], "change": units(amount, native["decimals"])})
            else:
                info = meta.get(asset, {})
                decimals = info.get("decimals")
                rows.append({"token": checksum(asset), "symbol": info.get("symbol"),
                             "change": units(amount, decimals) if decimals is not None else str(amount),
                             **({} if decimals is not None else {"note": "raw units; decimals unknown"})})
        if rows:
            changes.append({"address": address, "changes": rows})
    out = {"balance_changes": changes}
    if nfts:
        out["nft_transfers"] = nfts[:50]
    if not isinstance(trace, list):
        out["balance_changes_note"] = ("native value moved by internal calls is not included; trace=true "
                                       "adds it where the RPC supports tracing")
    return out


# --- address ------------------------------------------------------------------------------------

def address(ctx, args) -> dict:
    target, ens = resolve_address(ctx, args.get("address"))
    block, number = pin(ctx, None)
    balance, nonce, code = ctx.rpc.batch([("eth_getBalance", [target, block]),
                                          ("eth_getTransactionCount", [target, block]),
                                          ("eth_getCode", [target, block])])
    native = _native(ctx)
    price = ctx.prices.native(ctx.chain)
    code = code or "0x"
    raw = _bytes(code)
    result = {"chain": ctx.chain, "address": target, "ens": ens or reverse_ens(ctx, target),
              "balance": units(h2i(balance), native["decimals"]), "symbol": native["symbol"],
              "balance_usd": usd(as_float(h2i(balance), native["decimals"]), price), "nonce": h2i(nonce),
              "block": number, "explorer": chains.explorer(ctx.chain, "address", target)}
    if raw.startswith(b"\xef\x01\x00") and len(raw) == 23:
        result.update(kind="EOA with delegated code (EIP-7702)", delegate_to=checksum("0x" + raw[3:].hex()))
        return result
    if not raw:
        result["kind"] = "EOA (no code)"
        return result
    result.update(kind="contract", code_size=len(raw))
    proxy = _proxy(ctx, target, raw, block)
    if proxy:
        result["proxy"] = proxy
    result["standards"] = _standards(ctx, target, block)
    entries, name = ctx.decoder.contract(target, (proxy or {}).get("implementation"))
    result["verified"] = bool(entries)
    if name:
        result["verified_name"] = abi.untrusted(name)
    return result


def _proxy(ctx, target: str, raw: bytes, block: str = "latest") -> dict | None:
    """A proxy read from the chain at a block: EIP-1167 code, the EIP-1967 implementation /
    beacon / admin slots, or OpenZeppelin's legacy (zos) implementation / admin slots."""
    m = re.match(rb"^\x36\x3d\x3d\x37\x3d\x3d\x3d\x36\x3d\x73(.{20})\x5a\xf4", raw, re.S)
    if m:
        return {"type": "EIP-1167 minimal proxy", "implementation": checksum("0x" + m.group(1).hex())}
    impl, beacon, admin, zos_impl, zos_admin = ctx.rpc.batch([
        ("eth_getStorageAt", [target, slot, block])
        for slot in (EIP1967_IMPL, EIP1967_BEACON, EIP1967_ADMIN, ZOS_IMPL, ZOS_ADMIN)])
    proxy = {}
    if impl and int(impl, 16):
        proxy = {"type": "EIP-1967", "implementation": checksum("0x" + impl[-40:])}
    elif zos_impl and int(zos_impl, 16):
        proxy = {"type": "OpenZeppelin legacy (zos)", "implementation": checksum("0x" + zos_impl[-40:])}
        admin = zos_admin
    elif beacon and int(beacon, 16):
        proxy = {"type": "EIP-1967 beacon", "beacon": checksum("0x" + beacon[-40:])}
        got = ctx.rpc.try_call("eth_call", [{"to": proxy["beacon"], "data": "0x" + SEL["implementation"]},
                                            block])[0]
        if got and len(_bytes(got)) >= 32:
            proxy["implementation"] = checksum("0x" + got[-40:])
    if proxy and admin and int(admin, 16):
        proxy["admin"] = checksum("0x" + admin[-40:])
    return proxy or None


def _standards(ctx, target: str, block: str = "latest") -> list[str]:
    calls = [("eth_call", [{"to": target, "data": "0x" + SEL["supportsInterface"] + iface.ljust(64, "0")},
                           block]) for iface in INTERFACES.values()]
    calls += [("eth_call", [{"to": target, "data": "0x" + SEL[f]}, block]) for f in ("decimals", "totalSupply")]
    results = ctx.rpc.batch(calls)
    found = [name for name, got in zip(INTERFACES, results) if got and len(_bytes(got)) >= 32 and _bytes(got)[31] == 1]
    if not found and all(r and len(_bytes(r)) >= 32 for r in results[len(INTERFACES):]):
        found.append("ERC-20")
    return found


# --- portfolio and activity ---------------------------------------------------------------------

def portfolio(ctx, args) -> dict:
    names = args.get("chains") or [ctx.chain]
    if not isinstance(names, list) or len(names) > MAX_PORTFOLIO_CHAINS:
        raise ChainError(f"chains must list at most {MAX_PORTFOLIO_CHAINS} chains")
    results, total = [], 0.0
    owner = None
    for name in names:
        if name not in chains.EVM:
            raise ChainError(f"{name!r} is not an EVM chain this tool knows")
        sub = ctx.child(name)
        try:
            owner, ens = resolve_address(sub, args.get("address"))
            part = _portfolio_one(sub, owner)
        except ChainError as exc:
            part = {"chain": name, "error": str(exc)}
        total += part.get("total_usd") or 0
        results.append(part)
    return {"address": owner, "chains": results, "total_usd": round(total, 2),
            "note": "token names and symbols are set by whoever deployed the token; unpriced tokens are "
                    "often spam"}


def _portfolio_one(ctx, owner: str) -> dict:
    native = _native(ctx)
    balance = h2i(ctx.rpc.call("eth_getBalance", [owner, "latest"]))
    price = ctx.prices.native(ctx.chain)
    holdings: dict[str, int] = {}
    source = "known tokens"
    if ctx.rpc.provider == "Alchemy":
        got, _ = ctx.rpc.try_call("alchemy_getTokenBalances", [owner, "erc20"])
        if isinstance(got, dict):
            source = "provider token index"
            for row in got.get("tokenBalances") or []:
                amount = h2i(row.get("tokenBalance"))
                if amount:
                    holdings[row["contractAddress"].lower()] = amount
    if source == "known tokens":
        known = [t.lower() for t in chains.KNOWN_TOKENS.get(ctx.chain, [])]
        calls = [("eth_call", [{"to": t, "data": "0x" + SEL["balanceOf"] + owner[2:].lower().rjust(64, "0")},
                               "latest"]) for t in known]
        for token, got in zip(known, ctx.rpc.batch(calls)):
            if got and h2i(got):
                holdings[token] = h2i(got)
    tokens = list(holdings)[:MAX_TOKENS * 2]
    meta = token_meta(ctx, tokens) if tokens else {}
    prices = ctx.prices.tokens_usd(ctx.chain, tokens) if tokens else {}
    rows = []
    for token in tokens:
        info = meta.get(token, {})
        decimals = info.get("decimals")
        amount = as_float(holdings[token], decimals) if decimals is not None else None
        rows.append({"token": checksum(token), "symbol": info.get("symbol"),
                     "balance": units(holdings[token], decimals) if decimals is not None else str(holdings[token]),
                     "usd": usd(amount, prices.get(token))})
    rows.sort(key=lambda r: r["usd"] or -1, reverse=True)
    native_usd = usd(as_float(balance, native["decimals"]), price)
    total = (native_usd or 0) + sum(r["usd"] or 0 for r in rows)
    return {"chain": ctx.chain, "native": {"symbol": native["symbol"], "balance": units(balance, native["decimals"]),
                                           "usd": native_usd},
            "tokens": rows[:MAX_TOKENS], "tokens_omitted": max(len(rows) - MAX_TOKENS, 0),
            "unpriced_tokens": sum(1 for r in rows if r["usd"] is None), "token_source": source,
            "total_usd": round(total, 2)}


def activity(ctx, args) -> dict:
    owner, ens = resolve_address(ctx, args.get("address"))
    limit = _limit(args, 20, 50)
    if ctx.rpc.provider == "Alchemy":
        categories = ["external", "erc20", "erc721", "erc1155"]
        if ctx.chain in ("ethereum", "polygon"):
            categories.append("internal")
        rows = []
        for side in ("fromAddress", "toAddress"):
            got = ctx.rpc.call("alchemy_getAssetTransfers", [{
                "fromBlock": "0x0", "toBlock": "latest", side: owner, "category": categories,
                "maxCount": hex(limit), "order": "desc", "withMetadata": True, "excludeZeroValue": False}])
            rows += (got or {}).get("transfers") or []
        rows.sort(key=lambda r: h2i(r.get("blockNum")), reverse=True)
        seen, out = set(), []
        for row in rows:
            key = (row.get("uniqueId") or row.get("hash"), row.get("from"), row.get("to"))
            if key in seen:
                continue
            seen.add(key)
            out.append({"hash": row.get("hash"), "block": h2i(row.get("blockNum")),
                        "time": (row.get("metadata") or {}).get("blockTimestamp"), "category": row.get("category"),
                        "direction": "out" if (row.get("from") or "").lower() == owner.lower() else "in",
                        "from": checksum(row.get("from")), "to": checksum(row.get("to")),
                        "value": row.get("value"),
                        "asset": abi.untrusted(row["asset"]) if row.get("asset") else None,
                        "token": checksum((row.get("rawContract") or {}).get("address"))})
            if len(out) >= limit:
                break
        return {"chain": ctx.chain, "address": owner, "ens": ens, "transfers": out, "source": "provider index"}
    latest = h2i(ctx.rpc.call("eth_blockNumber"))
    padded = "0x" + owner[2:].lower().rjust(64, "0")
    logs, coverage = _scan(ctx, latest - SCAN_BLOCKS + 1, latest, [
        [abi.TRANSFER_TOPIC, padded], [abi.TRANSFER_TOPIC, None, padded]])
    logs.sort(key=lambda log: (h2i(log.get("blockNumber")), h2i(log.get("logIndex"))), reverse=True)
    tokens = sorted({log["address"].lower() for log in logs[:limit]})
    meta = token_meta(ctx, tokens) if tokens else {}
    out = []
    for log in logs[:limit]:
        decoded = ctx.decoder.event(log)
        args_ = decoded.get("args") or {}
        info = meta.get(log["address"].lower(), {})
        raw = args_.get("value")
        out.append({"hash": log.get("transactionHash"), "block": h2i(log.get("blockNumber")),
                    "token": checksum(log["address"]), "symbol": info.get("symbol"),
                    "direction": "out" if (args_.get("from") or "").lower() == owner.lower() else "in",
                    "from": args_.get("from"), "to": args_.get("to"),
                    "value": units(int(raw), info["decimals"]) if raw is not None and info.get("decimals") is not None
                    else (raw if raw is not None else {"token_id": args_.get("tokenId")})})
    return {"chain": ctx.chain, "address": owner, "ens": ens, "transfers": out, "coverage": coverage,
            "source": "token Transfer events only; native transfers need a provider key (ALCHEMY_API_KEY)"}


def _limit(args, default: int, maximum: int) -> int:
    value = args.get("limit") or default
    if not isinstance(value, int) or value < 1:
        raise ChainError("limit must be a positive integer")
    return min(value, maximum)


def _scan(ctx, start: int, end: int, topic_sets: list[list], address: str | None = None) -> tuple[list, dict]:
    """eth_getLogs over [start, end] in LOG_RANGE windows, newest first; stops at the first refusal."""
    start = max(start, 0)
    logs, scanned_from, error = [], end + 1, None
    hi = end
    while hi >= start:
        lo = max(hi - LOG_RANGE + 1, start)
        for topics in topic_sets:
            query = {"fromBlock": hex(lo), "toBlock": hex(hi), "topics": topics}
            if address:
                query["address"] = address
            got, error = ctx.rpc.try_call("eth_getLogs", [query])
            if got is None:
                break
            logs += got
        if error:
            break
        scanned_from = lo
        hi = lo - 1
    coverage = {"from_block": scanned_from, "to_block": end, "complete": scanned_from <= start}
    if error:
        coverage["stopped"] = error
    return logs, coverage


# --- logs, token, allowances --------------------------------------------------------------------

def logs(ctx, args) -> dict:
    contract, _ = resolve_address(ctx, args.get("address"))
    latest = h2i(ctx.rpc.call("eth_blockNumber"))
    end = h2i(args["to_block"]) if args.get("to_block") not in (None, "", "latest") else latest
    start = h2i(args["from_block"]) if args.get("from_block") not in (None, "") else end - 999
    if end < start:
        raise ChainError("to_block is before from_block")
    if end - start + 1 > LOG_RANGE:
        raise ChainError(f"at most {LOG_RANGE} blocks per call; narrow from_block / to_block")
    topics = []
    if args.get("event"):
        event = str(args["event"])
        topics = [event if _HASH.match(event) else abi.known_event_topic(event)]
    limit = _limit(args, MAX_LOGS, MAX_LOGS)
    found, unread = _get_logs(ctx, contract, start, end, topics, limit)
    events = []
    for log in found[:limit]:
        decoded = ctx.decoder.event(log)
        decoded.update(block=h2i(log.get("blockNumber")), tx=log.get("transactionHash"))
        events.append(decoded)
    return {"chain": ctx.chain, "contract": contract, "from_block": start, "to_block": end,
            "found": len(found), "events": events, "omitted": max(len(found) - limit, 0),
            **({"unread_ranges": unread} if unread else {})}


def _too_large(error: ChainError) -> bool:
    """An endpoint's way of saying "fewer blocks, please": HTTP 413, a result-size limit, or the
    HTTP 500 a public endpoint gives a query too heavy to answer (splitting is bounded anyway)."""
    text = str(error).lower()
    return "http 413" in text or "http 500" in text or any(word in text for word in (
        "too large", "exceed", "more than", "response size", "block range", "query timeout"))


def _get_logs(ctx, contract: str, start: int, end: int, topics: list, want: int) -> tuple[list, list]:
    """Logs newest first, and the ranges left unread. A range an endpoint refuses as too large is
    split in halves (newest half first), within MAX_LOG_REQUESTS; once ``want`` events are in hand
    the older ranges are left unread rather than fetched."""
    found, unread, requests, reads, first_error = [], [], 0, 0, None
    stack = [(start, end)]
    while stack:
        low, high = stack.pop()
        if len(found) >= want:
            unread.append({"from_block": low, "to_block": high, "reason": "event limit reached"})
            continue
        if requests >= MAX_LOG_REQUESTS:
            unread.append({"from_block": low, "to_block": high, "reason": "request cap reached"})
            continue
        requests += 1
        try:
            got = ctx.rpc.call("eth_getLogs", [{"address": contract, "fromBlock": hex(low), "toBlock": hex(high),
                                                **({"topics": topics} if topics else {})}]) or []
        except ChainError as exc:
            if _too_large(exc) and high > low:
                middle = (low + high) // 2
                stack += [(low, middle), (middle + 1, high)]  # the newer half is read first
                continue
            first_error = first_error or exc
            unread.append({"from_block": low, "to_block": high, "reason": str(exc)[:200]})
            continue
        reads += 1
        found += got[::-1]
    if not reads and first_error:
        raise first_error  # no range could be read at all: the plain error, as before
    unread.sort(key=lambda r: r["from_block"])
    return found, unread


def token(ctx, args) -> dict:
    target, _ = resolve_address(ctx, args.get("token") or args.get("address"))
    meta = token_meta(ctx, [target], with_name=True).get(target.lower(), {})
    supply = ctx.rpc.try_call("eth_call", [{"to": target, "data": "0x" + SEL["totalSupply"]}, "latest"])[0]
    decimals = meta.get("decimals")
    result = {"chain": ctx.chain, "token": target, "name": meta.get("name"), "symbol": meta.get("symbol"),
              "decimals": decimals, "standards": _standards(ctx, target),
              "explorer": chains.explorer(ctx.chain, "token", target)}
    if supply and len(_bytes(supply)) >= 32:
        raw = int.from_bytes(_bytes(supply)[:32], "big")
        result["total_supply"] = units(raw, decimals) if decimals is not None else str(raw)
    market = ctx.prices.token_market(ctx.chain, target)
    if market:
        result["market"] = market
    return result


def allowances(ctx, args) -> dict:
    owner, ens = resolve_address(ctx, args.get("address"))
    blocks = args.get("blocks") or ALLOWANCE_BLOCKS
    if not isinstance(blocks, int) or blocks < 1 or blocks > MAX_SCAN_BLOCKS:
        raise ChainError(f"blocks must be between 1 and {MAX_SCAN_BLOCKS}")
    latest = h2i(ctx.rpc.call("eth_blockNumber"))
    padded = "0x" + owner[2:].lower().rjust(64, "0")
    found, coverage = _scan(ctx, latest - blocks + 1, latest,
                            [[abi.APPROVAL_TOPIC, padded], [abi.APPROVAL_FOR_ALL_TOPIC, padded]])
    erc20, operators = set(), set()
    for log in found:
        topics = log.get("topics") or []
        if topics[0].lower() == abi.APPROVAL_TOPIC and len(topics) == 3:
            erc20.add((log["address"].lower(), "0x" + topics[2][-40:]))
        elif topics[0].lower() == abi.APPROVAL_FOR_ALL_TOPIC and len(topics) == 3:
            operators.add((log["address"].lower(), "0x" + topics[2][-40:]))
    pairs = sorted(erc20)[:60]
    ops = sorted(operators)[:30]
    calls = [("eth_call", [{"to": t, "data": "0x" + SEL["allowance"] + abi_encode(["address", "address"],
                                                                                   [owner, s]).hex()}, "latest"])
             for t, s in pairs]
    calls += [("eth_call", [{"to": t, "data": "0x" + SEL["isApprovedForAll"] + abi_encode(["address", "address"],
                                                                                          [owner, s]).hex()}, "latest"])
              for t, s in ops]
    results = ctx.rpc.batch(calls)
    meta = token_meta(ctx, sorted({t for t, _ in pairs})) if pairs else {}
    out = []
    for (token_addr, spender), got in zip(pairs, results[:len(pairs)]):
        amount = h2i(got) if got and got != "0x" else 0
        if not amount:
            continue
        info = meta.get(token_addr, {})
        decimals = info.get("decimals")
        out.append({"token": checksum(token_addr), "symbol": info.get("symbol"), "spender": checksum(spender),
                    "allowance": "unlimited" if amount >= UNLIMITED else
                    (units(amount, decimals) if decimals is not None else str(amount)),
                    "unlimited": amount >= UNLIMITED})
    nft = [{"collection": checksum(t), "operator": checksum(s), "approved_for_all": True}
           for (t, s), got in zip(ops, results[len(pairs):]) if got and h2i(got) == 1]
    for entry in (out + nft)[:8]:
        _, name = ctx.decoder.contract(entry.get("spender") or entry.get("operator"))
        if name:
            entry["spender_name"] = abi.untrusted(name)
    return {"chain": ctx.chain, "address": owner, "ens": ens, "token_approvals": out, "nft_operators": nft,
            "unlimited": sum(1 for e in out if e["unlimited"]), "coverage": coverage,
            "note": "approvals granted before the scanned blocks are not seen; widen with blocks"}


# --- decode, gas, price -------------------------------------------------------------------------

def decode(ctx, args) -> dict:
    data = args.get("data")
    if not isinstance(data, str) or not re.match(r"^(0x)?[0-9a-fA-F]*$", data) or len(data) % 2:
        raise ChainError("data must be hex")
    data = data if data.startswith("0x") else "0x" + data
    if args.get("topics"):
        log = {"address": args.get("address") or "0x" + "00" * 20, "topics": args["topics"], "data": data}
        return {"kind": "log", **ctx.decoder.event(log)}
    raw = _bytes(data)
    if raw and (raw[0] in (1, 2, 3, 4) or raw[0] >= 0xc0):
        decoded = _raw_transaction(ctx, raw)
        if decoded:
            return decoded
    to = resolve_address(ctx, args["to"])[0] if args.get("to") else None
    return {"kind": "calldata", **(ctx.decoder.function(data, to) or {"note": "empty calldata"})}


def _raw_transaction(ctx, raw: bytes) -> dict | None:
    import rlp
    typed = raw[0] < 0xc0
    try:
        fields = rlp.decode(raw[1:] if typed else raw)
    except Exception:
        return None
    kind = raw[0] if typed else 0
    layouts = {
        0: ["nonce", "gas_price", "gas", "to", "value", "data"],
        1: ["chain_id", "nonce", "gas_price", "gas", "to", "value", "data", "access_list"],
        2: ["chain_id", "nonce", "max_priority_fee", "max_fee", "gas", "to", "value", "data", "access_list"],
        3: ["chain_id", "nonce", "max_priority_fee", "max_fee", "gas", "to", "value", "data", "access_list",
            "max_fee_per_blob_gas", "blob_hashes"],
        4: ["chain_id", "nonce", "max_priority_fee", "max_fee", "gas", "to", "value", "data", "access_list",
            "authorizations"],
    }
    names = layouts[kind]
    if not isinstance(fields, list) or len(fields) < len(names):
        return None
    out = {"kind": "transaction", "type": TX_TYPES[kind]}
    values = dict(zip(names, fields))
    num = lambda b: int.from_bytes(b, "big") if b else 0  # noqa: E731
    native = _native(ctx)
    for key in ("chain_id", "nonce", "gas"):
        if key in values:
            out[key] = num(values[key])
    for key in ("gas_price", "max_priority_fee", "max_fee"):
        if key in values:
            out[key + "_gwei"] = gwei(num(values[key]))
    out["to"] = checksum("0x" + values["to"].hex()) if values["to"] else None
    out["value"] = units(num(values["value"]), native["decimals"])
    out["symbol"] = native["symbol"]
    signed = len(fields) > len(names) or (kind == 0 and len(fields) == 9 and num(fields[7]) != 0)
    out["signed"] = bool(signed)
    if kind == 0 and len(fields) == 9 and not num(fields[7]):
        out["chain_id"] = num(fields[6])
    if signed:
        try:
            from eth_account import Account
            out["from"] = Account.recover_transaction(raw)
        except Exception as exc:
            out["from"] = None
            out["signature_problem"] = type(exc).__name__
    if "chain_id" in out:
        out["chain"] = next((k for k, v in chains.EVM.items() if v["id"] == out["chain_id"]), None)
    if "authorizations" in values:
        out["authorizations"] = [{"chain_id": num(a[0]), "delegate_to": checksum("0x" + a[1].hex()),
                                  "nonce": num(a[2])} for a in values["authorizations"]]
        out["warning"] = ("this transaction sets code on the signing accounts: the delegate contract can then "
                          "act for them")
    out["call"] = ctx.decoder.function("0x" + values["data"].hex(), out["to"]) if out["to"] else \
        {"note": "contract creation", "init_code_size": len(values["data"])}
    return out


def gas(ctx, args) -> dict:
    native = _native(ctx)
    history = ctx.rpc.call("eth_feeHistory", [20, "latest", [10, 50, 90]]) or {}
    bases = [h2i(b) for b in history.get("baseFeePerGas") or []]
    rewards = history.get("reward") or []
    pct = {}
    for i, label in enumerate(("low", "medium", "high")):
        column = sorted(h2i(r[i]) for r in rewards if len(r) > i)
        pct[label] = column[len(column) // 2] if column else 0
    next_base = bases[-1] if bases else h2i(ctx.rpc.call("eth_gasPrice"))
    price = ctx.prices.native(ctx.chain)

    def cost(units_of_gas, tip):
        wei = units_of_gas * (next_base + tip)
        return {"native": units(wei, native["decimals"]), "usd": usd(as_float(wei, native["decimals"]), price)}

    return {"chain": ctx.chain, "next_base_fee_gwei": gwei(next_base),
            "priority_fee_gwei": {k: gwei(v) for k, v in pct.items()},
            "gas_price_gwei": gwei(h2i(ctx.rpc.call("eth_gasPrice"))),
            "native_transfer": cost(21_000, pct["medium"]), "token_transfer": cost(65_000, pct["medium"]),
            "symbol": native["symbol"]}


def price(ctx, args) -> dict:
    query = args.get("token") or args.get("symbol")
    if not query:
        raise ChainError("price needs symbol (e.g. ETH) or token (a contract address)")
    if isinstance(query, str) and _ADDRESS.match(query):
        market = ctx.prices.token_market(ctx.chain, query)
        return {"chain": ctx.chain, "token": to_checksum_address(query), "market": market,
                **({} if market else {"note": "no price found (testnets have none)"})}
    found = ctx.prices.lookup(str(query))
    return {"query": str(query), "market": found, **({} if found else {"note": "no matching coin found"})}


ACTIONS = {"block": block, "tx": tx, "address": address, "portfolio": portfolio, "activity": activity,
           "logs": logs, "token": token, "allowances": allowances, "decode": decode, "gas": gas, "price": price}
