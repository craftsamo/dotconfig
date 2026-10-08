"""EVM contract analysis of the ``evm`` tool, run in the engine venv (docs/web3.md "Reads").

``contract`` summarises a contract: proxy and implementation, who verified it and who deployed it,
its functions, events and errors, the current values of its argument-free getters, and the write
functions whose names suggest a power over users (minting, pausing, blocklists, fees, upgrades…).
Unverified code is read for its function selectors, which the signature database names as
guesses. ``call`` runs one function with ``eth_call`` — read or write, from any address, at any
block — and decodes its result or revert; nothing is signed or sent. ``storage`` reads raw slots,
named from Sourcify's storage layout where one is published.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re

from eth_abi import decode as abi_decode, encode as abi_encode

import abi
import chains
from evm import (EIP1967_ADMIN, EIP1967_BEACON, EIP1967_IMPL, ZOS_ADMIN, ZOS_IMPL, _bytes, _proxy, checksum, pin,
                 resolve_address)
from rpc import ChainError

MAX_FUNCTIONS = 80     # per list (read, write, events, errors, guessed selectors)
MAX_STATE = 25         # argument-free getters read
MAX_DOCS = 40
MAX_POWER_NAMES = 40
MAX_LAYOUT = 80
DOC_CLIP = 200
RAW_CLIP = 512         # hex digits of an undecoded return value
STATE_FIRST = ("owner", "getOwner", "admin", "pendingOwner", "paused", "implementation", "name", "symbol",
               "decimals", "totalSupply", "cap", "maxSupply")
# Write functions named like these let someone change the rules after deployment. A name is what a
# function is called, not what it does: a lead for reading the code, never proof either way.
POWERS = (
    ("mint", r"mint|issue"),
    ("pause", r"pause"),
    ("blocklist", r"blacklist|blocklist|denylist|freeze|ban(?!k)|bots?$|setbot|addbot"),
    ("fees", r"fee(?!d)|tax"),
    ("limits", r"maxtx|maxwallet|maxtransaction|maxbuy|maxsell|limit|cooldown"),
    ("trading", r"trading|opentrade|launch|swapenabled"),
    ("upgrade", r"upgrade|setimplementation|setlogic"),
    ("control", r"ownership|setowner|renounce|grantrole|revokerole|admin|minter|setoperator|governance|guardian"),
    ("funds", r"withdraw|rescue|sweep|recover|skim|emergency|drain|clawback"),
)
# Getters read from unverified code when its selectors include them.
KNOWN_GETTERS = {"8da5cb5b": ("owner", "address"), "893d20e8": ("getOwner", "address"),
                 "5c975abb": ("paused", "bool"), "06fdde03": ("name", "string"), "95d89b41": ("symbol", "string"),
                 "313ce567": ("decimals", "uint8"), "18160ddd": ("totalSupply", "uint256")}
NAMED_SLOTS = {"eip1967.implementation": EIP1967_IMPL, "eip1967.admin": EIP1967_ADMIN,
               "eip1967.beacon": EIP1967_BEACON, "zos.implementation": ZOS_IMPL, "zos.admin": ZOS_ADMIN}
_SIMPLE = re.compile(r"^(address|bool|string|bytes\d*|u?int\d*)$")
_CONSTANT = re.compile(r"^[A-Z0-9_]+$")  # PERMIT_TYPEHASH and the like never change


# --- contract -----------------------------------------------------------------------------------

def contract(ctx, args) -> dict:
    target, ens = resolve_address(ctx, args.get("address"))
    block, number = pin(ctx, None)
    raw = _bytes(ctx.rpc.call("eth_getCode", [target, block]))
    if raw.startswith(b"\xef\x01\x00") and len(raw) == 23:
        raise ChainError(f"{target} is an account delegating to {checksum('0x' + raw[3:].hex())} (EIP-7702); "
                         "analyse that contract")
    if not raw:
        raise ChainError(f"{target} has no contract code (an account, or a contract not deployed on {ctx.chain})")
    proxy = _proxy(ctx, target, raw, block) or {}
    own = ctx.decoder.record(target, rich=True)
    logic = proxy.get("implementation") or own["implementation"]  # the chain at this block first
    logic = checksum(logic) if logic and checksum(logic) != target else None
    impl = ctx.decoder.record(logic, rich=True) if logic else None
    result = {"chain": ctx.chain, "address": target, "ens": ens, "block": number, "code_size": len(raw),
              "explorer": chains.explorer(ctx.chain, "address", target)}
    if proxy or logic:
        result["proxy"] = {**proxy, **({"implementation": logic} if logic else {})}
    result["verified"] = {"contract": _verification(own), **({"implementation": _verification(impl)} if impl else {})}
    deployment = own.get("deployment") or ctx.decoder.creation(target)
    if deployment:
        result["deployment"] = deployment
    entries = own["entries"] + (impl["entries"] if impl else [])
    unread = impl is not None and not impl["entries"]  # what the proxy runs is unverified
    if entries:
        docs = {**(own.get("userdoc") or {}), **((impl or {}).get("userdoc") or {})}
        result.update(_interface(ctx, target, entries, docs, block))
    if not entries or unread:
        code = _bytes(ctx.rpc.call("eth_getCode", [logic, block])) if logic else raw
        guessed = _guessed_interface(ctx, target, code or raw, block)
        if not entries:
            result.update(guessed)
        else:
            result["functions"].update(guessed["functions"])
            for power, names in guessed["powers"].items():
                result["powers"][power] = list(dict.fromkeys(result["powers"].get(power, []) + names))
            result["state"] = {**guessed["state"], **result["state"]}
            unread = result.pop("state_unread", []) + guessed.get("state_unread", [])
            if unread:
                result["state_unread"] = sorted(set(unread))
    return result


def _verification(rec: dict) -> dict:
    if not rec["verified_by"]:
        return {"by": None}
    out = {"by": rec["verified_by"], "name": abi.untrusted(rec["name"]) if rec["name"] else None,
           "compiler": rec.get("compiler"), "match": rec.get("match")}
    return {k: v for k, v in out.items() if v is not None}


def _capped(items: list, key: str) -> dict:
    out = {key: items[:MAX_FUNCTIONS]}
    if len(items) > MAX_FUNCTIONS:
        out[f"{key}_omitted"] = len(items) - MAX_FUNCTIONS
    return out


def _interface(ctx, target: str, entries: list, docs: dict, block: str) -> dict:
    seen, reads, writes = set(), [], []
    for entry in entries:
        if entry.get("type") != "function" or not entry.get("name"):
            continue
        sig = abi.canonical(abi.from_json(entry))
        if sig in seen:
            continue
        seen.add(sig)
        (reads if abi.mutability(entry) in ("view", "pure") else writes).append(entry)
    write_text = [abi.describe(e) + (" payable" if abi.mutability(e) == "payable" else "") for e in writes]

    def unique(kind):
        return list(dict.fromkeys(abi.describe(e) for e in entries if e.get("type") == kind))

    out = {"functions": {**_capped([abi.describe(e) for e in reads], "read"), **_capped(write_text, "write")},
           **_capped(unique("event"), "events"), **_capped(unique("error"), "errors"),
           "powers": _powers([e["name"] for e in writes]),
           **_state(ctx, target, [e for e in reads if not e.get("inputs") and e.get("outputs")], block)}
    notes = {}
    for sig, doc in docs.items():
        if isinstance(doc, dict) and isinstance(doc.get("notice"), str) and len(notes) < MAX_DOCS:
            notes[sig] = abi.untrusted(doc["notice"][:DOC_CLIP])
    if notes:
        out["notices"] = notes
    return out


def _powers(names: list[str]) -> dict:
    found: dict[str, list[str]] = {}
    for name in dict.fromkeys(names):
        flat = name.lower().replace("_", "")
        for power, pattern in POWERS:
            if re.search(pattern, flat):
                kept = found.setdefault(power, [])
                if len(kept) < MAX_POWER_NAMES:
                    kept.append(name)
                break
    return found


def _state(ctx, target: str, getters: list[dict], block: str) -> dict:
    """``state``: the getters' values; ``state_unread``: getters the RPC would not answer (a revert
    is an answer: such a getter is simply left out)."""
    order = {name: i for i, name in enumerate(STATE_FIRST)}
    getters = sorted(getters, key=lambda e: (order.get(e["name"], len(order)), e["name"]))
    getters = [e for e in getters if all(_SIMPLE.match(o["type"]) for o in abi.outputs(e))
               and not _CONSTANT.match(e["name"])][:MAX_STATE]
    results = ctx.rpc.batch_detailed([
        ("eth_call", [{"to": target, "data": "0x" + abi.selector(abi.from_json(e))}, block]) for e in getters])
    return _collect([(e["name"], abi.outputs(e)) for e in getters], results)


def _collect(getters: list[tuple[str, list]], results: list[tuple]) -> dict:
    state, unread = {}, []
    for (name, outs), (got, error) in zip(getters, results):
        value = _returns(outs, got)
        if value is not None:
            state[name] = value
        elif error and "revert" not in error.lower():
            unread.append(name)
    return {"state": state, **({"state_unread": unread} if unread else {})}


def _returns(outs: list[dict], data) -> object | None:
    """Return data decoded by output types: one value, or a dict of several; None if it does not decode."""
    raw = _bytes(data) if isinstance(data, str) else b""
    if not raw or not outs:
        return None
    try:
        values = abi_decode([o["type"] for o in outs], raw, strict=False)
    except Exception:
        return None
    plain = [abi.plain(v, o["type"]) for v, o in zip(values, outs)]
    if len(plain) == 1:
        return plain[0]
    return {o["name"] or f"out{i}": v for i, (o, v) in enumerate(zip(outs, plain))}


def selectors_in(code: bytes) -> list[str]:
    """Function selectors of a Solidity or Vyper dispatcher: PUSH4 values compared right after
    (EQ, or a DUP then EQ, or the GT / LT of a binary-search split). Push data is skipped."""
    found, i = [], 0
    while i < len(code):
        op = code[i]
        if op == 0x63 and i + 5 <= len(code):
            nxt = code[i + 5:i + 7]
            if nxt[:1] in (b"\x14", b"\x10", b"\x11") or (nxt[:1] in (b"\x80", b"\x81") and nxt[1:2] == b"\x14"):
                sig = code[i + 1:i + 5].hex()
                if sig not in ("00000000", "ffffffff"):
                    found.append(sig)
        if 0x60 <= op <= 0x7f:
            i += op - 0x5f
        i += 1
    return list(dict.fromkeys(found))


def _guessed_interface(ctx, target: str, code: bytes, block: str) -> dict:
    sigs = selectors_in(code)
    guesses = ctx.decoder.selectors(sigs)
    rows, names = [], []
    for sig in sigs:
        named = guesses.get(sig) or []
        known = abi.known_function(sig)
        if not named and known:
            named = [abi.canonical(known)]
        rows.append({"selector": "0x" + sig, "guesses": named})
        if named:
            names.append(named[0].split("(")[0])
    getters = [(sig, *KNOWN_GETTERS[sig]) for sig in sigs if sig in KNOWN_GETTERS]
    results = ctx.rpc.batch_detailed([("eth_call", [{"to": target, "data": "0x" + sig}, block])
                                      for sig, _, _ in getters])
    collected = _collect([(name, [{"type": kind, "name": ""}]) for _, name, kind in getters], results)
    return {"functions": _capped(rows, "guessed"), "powers": _powers(names), **collected}


# --- call ---------------------------------------------------------------------------------------

def call(ctx, args) -> dict:
    target, _ = resolve_address(ctx, args.get("address"))
    values = args.get("args") if args.get("args") is not None else []
    if not isinstance(values, list):
        raise ChainError("args must be a list, one value per parameter")
    block, number = pin(ctx, args.get("block"))
    entry, source = _function(ctx, target, args.get("function"), len(values), block)
    types = [i["type"] for i in entry["inputs"]]
    if len(values) != len(types):
        raise ChainError(f"{abi.canonical(entry)} takes {len(types)} argument(s); {len(values)} given")
    try:
        encoded = abi_encode(types, [_coerce(ctx, v, t) for v, t in zip(values, types)])
    except ChainError:
        raise
    except Exception as exc:
        raise ChainError(f"the arguments do not fit {abi.canonical(entry)}: {str(exc)[:200]}") from None
    request = {"to": target, "data": "0x" + abi.selector(entry) + encoded.hex()}
    result = {"chain": ctx.chain, "address": target, "function": abi.canonical(entry), "abi": source}
    if entry.get("mutability"):
        result["mutability"] = entry["mutability"]
    if args.get("from"):
        request["from"] = result["from"] = resolve_address(ctx, args["from"])[0]
    if args.get("amount") not in (None, ""):
        wei = _wei(ctx, args["amount"])
        if wei:
            request["value"], result["amount"] = hex(wei), str(args["amount"])
    result["block"] = number if number is not None else block
    reply = ctx.rpc.request("eth_call", [request, block])
    error = reply.get("error")
    if error:
        error = error if isinstance(error, dict) else {"message": str(error)}
        data = error.get("data")
        data = data.get("data") if isinstance(data, dict) else data
        decoded = ctx.decoder.revert(data if isinstance(data, str) else None, target)
        result.update(status="reverted", error=decoded or {"message": abi.untrusted(error.get("message", ""))})
        return result
    out = reply.get("result") or "0x"
    result["status"] = "success"
    value = _returns(entry.get("outputs") or [], out)
    if value is not None:
        result["returns"] = value
    elif out != "0x":
        result["returns_raw"] = out if len(out) <= RAW_CLIP + 2 else f"{out[:RAW_CLIP + 2]}… ({len(_bytes(out))} bytes)"
    return result


def _logic(ctx, target: str, block: str) -> str | None:
    """The implementation a proxy ran at ``block``, read from the chain at that block (EIP-1167 /
    EIP-1967 / OpenZeppelin's legacy slots); the verifier's resolution only as a last resort."""
    own = ctx.decoder.record(target)
    code = _bytes(ctx.rpc.call("eth_getCode", [target, block]))
    found = (_proxy(ctx, target, code, block) or {}).get("implementation") if code else None
    logic = found or own["implementation"]
    return logic if logic and checksum(logic) != target else None


def _function(ctx, target: str, text, count: int, block: str) -> tuple[dict, str]:
    """(entry with inputs / outputs / mutability, ``verified`` or ``given``) for a name in the
    verified ABI or a signature like 'balanceOf(address)' or 'balanceOf(address)(uint256)'."""
    if not isinstance(text, str) or not text.strip():
        raise ChainError("function is required: a name from the verified ABI, or a signature like "
                         "balanceOf(address) or balanceOf(address) returns (uint256)")
    text = text.strip().removeprefix("function ").strip()
    given = _signature(text) if "(" in text else None
    logic = _logic(ctx, target, block)
    entries = ctx.decoder.record(target)["entries"] + (ctx.decoder.record(logic)["entries"] if logic else [])
    functions = [e for e in entries if e.get("type") == "function"]
    found = _matches(functions, given, text, count)
    if len(found) == 1:
        e = found[0]
        return {**abi.from_json(e), "outputs": abi.outputs(e), "mutability": abi.mutability(e)}, "verified"
    if given:
        return given, "given"
    if found:
        raise ChainError(f"{text} is overloaded; give one signature: "
                         + "; ".join(abi.describe(e) for e in found[:6]))
    raise ChainError(f"no function {text!r} in a verified ABI of this contract; give a signature like {text}(address)")


def _matches(functions: list, given: dict | None, text: str, count: int) -> list:
    if given:
        sel = abi.selector(given)
        return [e for e in functions if abi.selector(abi.from_json(e)) == sel][:1]
    named = [e for e in functions if e.get("name") == text]
    unique = {abi.canonical(abi.from_json(e)): e for e in named}
    named = list(unique.values())
    return [e for e in named if len(e.get("inputs") or []) == count] if len(named) > 1 else named


def _signature(text: str) -> dict:
    start = text.index("(")
    depth = 0
    for end, char in enumerate(text):
        depth += char == "("
        depth -= char == ")"
        if depth == 0 and end > start:
            break
    else:
        raise ChainError("the signature's parentheses do not match")
    name = text[:start].strip()
    if not re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name):
        raise ChainError(f"not a function name: {name[:40]!r}")
    entry = abi.parse(text[:end + 1])
    rest = re.sub(r"\b(external|public|view|pure|payable|nonpayable)\b", "", text[end + 1:]).strip()
    rest = rest.removeprefix("returns").strip()
    entry["outputs"] = []
    if rest.startswith("(") and rest.endswith(")") and rest[1:-1].strip():
        entry["outputs"] = [abi._param(part) for part in abi.split_top(rest[1:-1])]
    elif rest:
        raise ChainError(f"cannot read {rest[:40]!r} after the parameters; write returns (type, …)")
    return entry


def _coerce(ctx, value, kind: str):
    """A JSON value (numbers, lists and tuples may come as text) as eth_abi takes it for ``kind``."""
    if kind.endswith("]") or kind.startswith("("):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                raise ChainError(f"a {kind} value must be a JSON list") from None
        if not isinstance(value, list):
            raise ChainError(f"a {kind} value must be a list")
        if kind.endswith("]"):
            inner, size = kind[:kind.rindex("[")], kind[kind.rindex("[") + 1:-1]
            if size and len(value) != int(size):
                raise ChainError(f"{kind} takes exactly {size} values")
            return [_coerce(ctx, v, inner) for v in value]
        parts = abi.split_top(kind[1:-1])
        if len(parts) != len(value):
            raise ChainError(f"{kind} takes {len(parts)} values")
        return tuple(_coerce(ctx, v, k) for v, k in zip(value, parts))
    if kind == "address":
        return resolve_address(ctx, value)[0]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "false", "1", "0"):
            return str(value).lower() in ("true", "1")
        raise ChainError("a bool must be true or false")
    if kind.startswith(("uint", "int")):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        text = str(value).strip()
        try:
            return int(text, 16) if text.lower().startswith(("0x", "-0x")) else int(text)
        except ValueError:
            raise ChainError(f"a {kind} must be a whole number in base units (no decimals): {text[:40]!r}") from None
    if kind == "string":
        return str(value)
    if kind.startswith("bytes"):
        text = str(value)
        if not re.match(r"^0x([0-9a-fA-F]{2})*$", text):
            raise ChainError(f"a {kind} value must be 0x hex")
        return bytes.fromhex(text[2:])
    raise ChainError(f"{kind} arguments are not supported")


def _wei(ctx, amount) -> int:
    decimals = chains.EVM[ctx.chain]["decimals"]
    try:
        value = Decimal(str(amount)) * (Decimal(10) ** decimals)
    except InvalidOperation:
        raise ChainError("amount must be a number of whole coins, like 0.05") from None
    if value < 0 or value != value.to_integral_value():
        raise ChainError(f"amount must be positive with at most {decimals} decimal places")
    return int(value)


# --- storage ------------------------------------------------------------------------------------

def storage(ctx, args) -> dict:
    target, _ = resolve_address(ctx, args.get("address"))
    wanted = args.get("slot")
    block, number = pin(ctx, args.get("block"))
    result = {"chain": ctx.chain, "address": target}
    if wanted in (None, ""):
        layout = _layout(ctx, target, block)
        if not layout:
            raise ChainError("slot is required: a number, 0x hex, eip1967.implementation / .admin / .beacon, "
                             "zos.implementation / .admin, or a variable name where Sourcify publishes the storage "
                             "layout")
        types = layout.get("types") or {}
        rows = [{"variable": v.get("label"), "slot": v.get("slot"), "offset": v.get("offset"),
                 "type": (types.get(v.get("type")) or {}).get("label", v.get("type"))}
                for v in layout.get("storage") or []]
        return {**result, **_capped(rows, "layout")}
    variable, kind = None, None
    if isinstance(wanted, int) and not isinstance(wanted, bool) and wanted >= 0:
        slot = wanted
    elif isinstance(wanted, str) and wanted.isdigit():
        slot = int(wanted)
    elif isinstance(wanted, str) and re.match(r"^0x[0-9a-fA-F]{1,64}$", wanted):
        slot = int(wanted, 16)
    elif isinstance(wanted, str) and wanted.lower() in NAMED_SLOTS:
        slot, kind = int(NAMED_SLOTS[wanted.lower()], 16), {"label": "address", "encoding": "inplace",
                                                           "numberOfBytes": "20"}
        variable = {"label": wanted.lower(), "offset": 0}
    elif isinstance(wanted, str):
        layout = _layout(ctx, target, block) or {}
        variable = next((v for v in layout.get("storage") or [] if v.get("label") == wanted), None)
        if not variable:
            raise ChainError(f"no storage variable {wanted[:60]!r} in a published storage layout of this contract")
        slot, kind = int(variable["slot"]), (layout.get("types") or {}).get(variable.get("type")) or {}
    else:
        raise ChainError("slot must be a number, 0x hex or a variable name")
    if slot >= 2 ** 256:
        raise ChainError("slot is out of range")
    word = _bytes(ctx.rpc.call("eth_getStorageAt", [target, hex(slot), block]))
    word = word.rjust(32, b"\x00")[-32:]
    result.update(slot=hex(slot), block=number if number is not None else block, raw="0x" + word.hex())
    if variable:
        result.update(variable=variable["label"], type=kind.get("label"),
                      **_slot_value(word, int(variable.get("offset") or 0), kind))
    return result


def _layout(ctx, target: str, block: str) -> dict | None:
    """Sourcify's storage layout — for a proxy, that of the implementation it ran at ``block``."""
    own = ctx.decoder.record(target, rich=True)
    logic = _logic(ctx, target, block)
    impl = ctx.decoder.record(logic, rich=True) if logic else None
    for rec in (impl, own):
        if rec and isinstance(rec.get("layout"), dict) and rec["layout"].get("storage"):
            return rec["layout"]
    return None


def _slot_value(word: bytes, offset: int, kind: dict) -> dict:
    label, encoding = str(kind.get("label") or ""), kind.get("encoding")
    size = int(kind.get("numberOfBytes") or 32)
    if encoding == "mapping":  # the slot itself holds nothing; entries live at hashed slots
        return {}
    if encoding == "dynamic_array":
        return {"length": int.from_bytes(word, "big")}
    if encoding == "bytes":
        if word[31] & 1:
            return {"length": (int.from_bytes(word, "big") - 1) // 2}
        data = word[:word[31] // 2]
        return {"value": abi.untrusted(data.decode("utf-8", "replace")) if label == "string" else "0x" + data.hex()}
    if encoding != "inplace" or size > 32 or offset + size > 32:
        return {}
    chunk = word[32 - offset - size:32 - offset]
    number = int.from_bytes(chunk, "big")
    if label == "bool":
        return {"value": bool(number)}
    if label.startswith(("address", "contract ")):
        return {"value": checksum("0x" + chunk[-20:].hex())}
    if label.startswith("int"):
        bits = size * 8
        return {"value": abi.number(number - (1 << bits) if number >> (bits - 1) else number)}
    if label.startswith(("uint", "enum ")):
        return {"value": abi.number(number)}
    return {"value": "0x" + chunk.hex()}


ACTIONS = {"contract": contract, "call": call, "storage": storage}
