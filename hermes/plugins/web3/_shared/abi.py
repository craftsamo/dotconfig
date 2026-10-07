"""EVM calldata, event and revert decoding for the web3 engine (docs/web3.md "Reads").

An ABI is looked up in order: the contract's verified ABI on Sourcify, else on Etherscan when an
``ETHERSCAN_API_KEY`` is stored (either with a proxy's implementation), the built-in set below, then
4byte.directory signatures. Every decoded item says where its ABI came from (``verified``,
``known``, ``guessed``); 4byte signatures are guesses because selectors collide. String values are
text written by strangers and come back wrapped as ``{"untrusted": …}``.
"""

from __future__ import annotations

import json
import re
import urllib.parse

from eth_abi import decode as abi_decode
from eth_utils import keccak, to_checksum_address

from rpc import RPC_SCOPE, http_json, secret

# {base} is the service's own origin, or the engine tests' fake server.
SOURCIFY = "{base}/server/v2/contract/{chain}/{address}?fields={fields}"
ETHERSCAN = "{base}/v2/api?chainid={chain}&module=contract&action={action}&{query}&apikey={key}"
SIGNATURE_DB = "{base}/signature-database/v1/lookup?function={sigs}&filter=true"
FOURBYTE_FN = "{base}/api/v1/signatures/?hex_signature={sig}&ordering=created_at"
FOURBYTE_EV = "{base}/api/v1/event-signatures/?hex_signature={sig}&ordering=created_at"
BASES = {"sourcify": "https://sourcify.dev", "etherscan": "https://api.etherscan.io",
         "signatures": "https://api.4byte.sourcify.dev", "fourbyte": "https://www.4byte.directory"}
LEAN_FIELDS = "abi,proxyResolution,compilation"
RICH_FIELDS = "abi,proxyResolution,compilation,deployment,userdoc,storageLayout"
TEXT_CLIP = 300
BYTES_CLIP = 96         # bytes values longer than this are cut and sized
SOURCIFY_BUDGET = 6     # contract lookups per engine call
ETHERSCAN_BUDGET = 6    # likewise, within Etherscan's 3 calls a second
FOURBYTE_BUDGET = 12    # signature lookups per engine call
CANDIDATES = 3          # 4byte signatures tried per selector
SELECTOR_BATCH = 120    # selectors guessed in one signature-database lookup
_SIGNATURE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}\([A-Za-z0-9_,()\[\]]{0,400}\)$")

KNOWN_FUNCTIONS = [
    "transfer(address to, uint256 amount)",
    "transferFrom(address from, address to, uint256 amount)",
    "approve(address spender, uint256 amount)",
    "increaseAllowance(address spender, uint256 addedValue)",
    "decreaseAllowance(address spender, uint256 subtractedValue)",
    "safeTransferFrom(address from, address to, uint256 tokenId)",
    "safeTransferFrom(address from, address to, uint256 tokenId, bytes data)",
    "safeTransferFrom(address from, address to, uint256 id, uint256 amount, bytes data)",
    "safeBatchTransferFrom(address from, address to, uint256[] ids, uint256[] amounts, bytes data)",
    "setApprovalForAll(address operator, bool approved)",
    "permit(address owner, address spender, uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s)",
    "deposit()",
    "withdraw(uint256 amount)",
    "multicall(bytes[] data)",
    "multicall(uint256 deadline, bytes[] data)",
    "aggregate3((address target, bool allowFailure, bytes callData)[] calls)",
    "balanceOf(address owner)",
    "allowance(address owner, address spender)",
    "upgradeTo(address implementation)",
    "upgradeToAndCall(address implementation, bytes data)",
    "transferOwnership(address newOwner)",
]

KNOWN_EVENTS = [
    "Transfer(address indexed from, address indexed to, uint256 value)",
    "Transfer(address indexed from, address indexed to, uint256 indexed tokenId)",
    "Approval(address indexed owner, address indexed spender, uint256 value)",
    "Approval(address indexed owner, address indexed approved, uint256 indexed tokenId)",
    "ApprovalForAll(address indexed owner, address indexed operator, bool approved)",
    "TransferSingle(address indexed operator, address indexed from, address indexed to, uint256 id, uint256 value)",
    "TransferBatch(address indexed operator, address indexed from, address indexed to, uint256[] ids, uint256[] values)",
    "Deposit(address indexed dst, uint256 wad)",
    "Withdrawal(address indexed src, uint256 wad)",
    "Swap(address indexed sender, uint256 amount0In, uint256 amount1In, uint256 amount0Out, uint256 amount1Out, address indexed to)",
    "Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)",
    "Sync(uint112 reserve0, uint112 reserve1)",
    "Upgraded(address indexed implementation)",
    "OwnershipTransferred(address indexed previousOwner, address indexed newOwner)",
]

PANICS = {0x00: "generic panic", 0x01: "assert failed", 0x11: "arithmetic overflow or underflow",
          0x12: "division by zero", 0x21: "invalid enum value", 0x22: "corrupt storage byte array",
          0x31: "pop on an empty array", 0x32: "array index out of bounds", 0x41: "out of memory",
          0x51: "call to an uninitialized function"}
ERROR_STRING, PANIC = "08c379a0", "4e487b71"


# --- signatures -----------------------------------------------------------------------------

def split_top(text: str) -> list[str]:
    """Split on commas outside parentheses."""
    parts, depth, current = [], 0, []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _param(text: str) -> dict:
    text = text.strip()
    if text.startswith("("):
        depth = 0
        for i, char in enumerate(text):
            depth += char == "("
            depth -= char == ")"
            if depth == 0:
                break
        inner, rest = text[1:i], text[i + 1:]
        suffix = rest.split()[0] if rest.strip() and rest.strip()[0] == "[" else ""
        words = rest[len(suffix):].split() if suffix else rest.split()
        components = [_param(part) for part in split_top(inner)]
        kind = "(" + ",".join(c["type"] for c in components) + ")" + suffix
        return {"type": kind, "indexed": "indexed" in words,
                "name": next((w for w in words if w != "indexed"), ""), "components": components}
    words = text.split()
    words[0] = re.sub(r"^(u?int)(?=$|\[)", r"\g<1>256", words[0])  # uint is uint256 in a selector
    return {"type": words[0], "indexed": "indexed" in words[1:],
            "name": next((w for w in words[1:] if w != "indexed"), "")}


def parse(signature: str) -> dict:
    """A human-readable signature ('Transfer(address indexed from, …)') as an ABI entry."""
    name, _, rest = signature.partition("(")
    inputs = [_param(part) for part in split_top(rest[:-1])] if rest[:-1].strip() else []
    return {"name": name.strip(), "inputs": inputs}


def _abi_type(item: dict) -> str:
    """The canonical type of a JSON ABI input (tuples spelled out)."""
    kind = item.get("type", "")
    if kind.startswith("tuple"):
        inner = ",".join(_abi_type(c) for c in item.get("components") or [])
        return f"({inner}){kind[len('tuple'):]}"
    return kind


def from_json(entry: dict) -> dict:
    return {"name": entry.get("name", ""), "inputs": [
        {"type": _abi_type(i), "name": i.get("name", ""), "indexed": bool(i.get("indexed"))}
        for i in entry.get("inputs") or []]}


def canonical(entry: dict) -> str:
    return f"{entry['name']}({','.join(i['type'] for i in entry['inputs'])})"


def outputs(entry: dict) -> list[dict]:
    """A JSON ABI function's outputs like ``from_json``'s inputs."""
    return [{"type": _abi_type(o), "name": o.get("name", "")} for o in entry.get("outputs") or []]


def mutability(entry: dict) -> str:
    """view / pure / nonpayable / payable, older ABIs' constant and payable flags included."""
    if entry.get("stateMutability"):
        return entry["stateMutability"]
    if entry.get("constant"):
        return "view"
    return "payable" if entry.get("payable") else "nonpayable"


def describe(entry: dict) -> str:
    """A JSON ABI entry as readable text: 'transfer(address to, uint256 amount) returns (bool)'."""
    def params(items):
        return ", ".join(f"{_abi_type(i)}{' indexed' if i.get('indexed') else ''}"
                         f"{' ' + i['name'] if i.get('name') else ''}" for i in items or [])
    text = f"{entry.get('name', '')}({params(entry.get('inputs'))})"
    if entry.get("type") == "function" and entry.get("outputs"):
        text += f" returns ({params(entry['outputs'])})"
    return text


def selector(entry: dict) -> str:
    return keccak(text=canonical(entry))[:4].hex()


def topic(entry: dict) -> str:
    return keccak(text=canonical(entry)).hex()


_FUNCS: dict[str, dict] = {}
for _sig in KNOWN_FUNCTIONS:
    _entry = parse(_sig)
    _FUNCS.setdefault(selector(_entry), _entry)
_EVENTS: dict[tuple[str, int], dict] = {}
for _sig in KNOWN_EVENTS:
    _entry = parse(_sig)
    _EVENTS[(topic(_entry), sum(i["indexed"] for i in _entry["inputs"]))] = _entry


# --- values -------------------------------------------------------------------------------------

def untrusted(text) -> dict:
    text = str(text)
    return {"untrusted": text if len(text) <= TEXT_CLIP else text[:TEXT_CLIP] + f"… ({len(text)} chars)"}


def number(value: int):
    """An int JSON keeps exact in every reader: a string past 2**53."""
    return value if abs(value) < 2 ** 53 else str(value)


def plain(value, kind: str):
    """A decoded value as JSON, by its ABI type."""
    if kind.endswith("]"):
        inner = kind[:kind.rindex("[")]
        return [plain(v, inner) for v in value]
    if kind.startswith("("):
        parts = split_top(kind[1:-1])
        return [plain(v, k) for v, k in zip(value, parts)]
    if kind == "address":
        return to_checksum_address(value)
    if kind == "string":
        return untrusted(value)
    if kind.startswith("bytes"):
        raw = bytes(value)
        if len(raw) > BYTES_CLIP:
            return f"0x{raw[:BYTES_CLIP].hex()}… ({len(raw)} bytes)"
        return "0x" + raw.hex()
    if kind == "bool":
        return bool(value)
    if kind.startswith(("uint", "int")):
        return number(int(value))
    return str(value)


def _args(inputs: list[dict], values) -> dict:
    out = {}
    for i, (item, value) in enumerate(zip(inputs, values)):
        out[item["name"] or f"arg{i}"] = plain(value, item["type"])
    return out


# --- decoder ------------------------------------------------------------------------------------

class Decoder:
    """Decodes calls, logs and reverts of one chain, with bounded lookups per engine call."""

    def __init__(self, chain_id: int, online: bool = True, base: str | None = None):
        """``base`` (the engine tests only) sends every Sourcify, Etherscan, signature-database and
        4byte lookup to one fake server, with a dummy Etherscan key."""
        self.chain_id, self.online = chain_id, online
        self.bases = {name: base for name in BASES} if base else dict(BASES)
        self.records: dict[str, dict] = {}
        self.fourbyte: dict[str, list[str]] = {}
        self.sourcify_left, self.etherscan_left = SOURCIFY_BUDGET, ETHERSCAN_BUDGET
        self.fourbyte_left = FOURBYTE_BUDGET
        self._key = "test" if base else None

    def etherscan_key(self) -> str | None:
        if self._key is None:
            self._key = secret("ETHERSCAN_API_KEY", RPC_SCOPE) or ""
        return self._key or None

    def record(self, address: str, rich: bool = False) -> dict:
        """What the verifiers know of one address itself (no implementation merged): ``entries``
        (its ABI), ``name``, ``verified_by`` (sourcify / etherscan / None) and ``implementation``
        when the verifier resolved it as a proxy; with ``rich``, also ``compiler``, ``match``,
        ``deployment``, ``userdoc`` and Sourcify's ``layout`` (storage layout) where known."""
        address = to_checksum_address(address)
        found = self.records.get(address)
        if found and (found["rich"] or not rich or not found["verified_by"]):
            return found  # a lean record of a verified contract is fetched again for the details
        rec = {"rich": rich, "entries": [], "name": None, "verified_by": None, "implementation": None}
        if self.online and self.sourcify_left > 0:
            self.sourcify_left -= 1
            data = http_json(SOURCIFY.format(base=self.bases["sourcify"], chain=self.chain_id, address=address,
                                             fields=RICH_FIELDS if rich else LEAN_FIELDS))
            if isinstance(data, dict) and isinstance(data.get("abi"), list):
                self._from_sourcify(rec, data)
        if not rec["verified_by"] and self.online and self.etherscan_left > 0 and self.etherscan_key():
            self.etherscan_left -= 1
            self._from_etherscan(rec, address, rich)
        self.records[address] = rec
        return rec

    def _from_sourcify(self, rec: dict, data: dict) -> None:
        rec.update(entries=list(data["abi"]), verified_by="sourcify")
        compilation = data.get("compilation") if isinstance(data.get("compilation"), dict) else {}
        rec["name"] = compilation.get("name")
        for impl in ((data.get("proxyResolution") or {}).get("implementations") or [])[:1]:
            if isinstance(impl, dict) and impl.get("address"):
                rec["implementation"] = to_checksum_address(impl["address"])
                rec["name"] = rec["name"] or impl.get("name")
        if not rec["rich"]:
            return
        rec["compiler"] = compilation.get("compilerVersion")
        rec["match"] = {"exact_match": "exact", "match": "partial"}.get(data.get("match"), data.get("match"))
        deployment = data.get("deployment") if isinstance(data.get("deployment"), dict) else {}
        if deployment.get("deployer") or deployment.get("transactionHash"):
            rec["deployment"] = {"deployer": deployment.get("deployer"), "tx": deployment.get("transactionHash"),
                                 "block": int(deployment["blockNumber"]) if str(
                                     deployment.get("blockNumber") or "").isdigit() else None}
        if isinstance(data.get("userdoc"), dict):
            rec["userdoc"] = data["userdoc"].get("methods") or {}
        if isinstance(data.get("storageLayout"), dict):
            rec["layout"] = data["storageLayout"]

    def _etherscan(self, action: str, query: dict):
        data = http_json(ETHERSCAN.format(base=self.bases["etherscan"], chain=self.chain_id, action=action,
                                          query=urllib.parse.urlencode(query), key=self.etherscan_key()))
        if isinstance(data, dict) and str(data.get("status")) == "1" and isinstance(data.get("result"), list):
            return data["result"]
        return None

    def _from_etherscan(self, rec: dict, address: str, rich: bool) -> None:
        rows = self._etherscan("getsourcecode", {"address": address})
        row = rows[0] if rows and isinstance(rows[0], dict) else {}
        try:
            entries = json.loads(row.get("ABI") or "")
        except ValueError:  # "Contract source code not verified"
            return
        if not isinstance(entries, list):
            return
        rec.update(entries=entries, verified_by="etherscan", name=row.get("ContractName") or None)
        if str(row.get("Proxy")) in ("1", "2") and str(row.get("Implementation", "")).startswith("0x"):
            rec["implementation"] = to_checksum_address(row["Implementation"])
        if rich:
            rec["compiler"] = row.get("CompilerVersion") or None

    def creation(self, address: str) -> dict | None:
        """Who deployed a contract, in which transaction — from Etherscan (unverified contracts
        too), so only with a key."""
        if not (self.online and self.etherscan_left > 0 and self.etherscan_key()):
            return None
        self.etherscan_left -= 1
        rows = self._etherscan("getcontractcreation", {"contractaddresses": to_checksum_address(address)})
        first = rows[0] if rows and isinstance(rows[0], dict) else {}
        if not (first.get("contractCreator") or first.get("txHash")):
            return None
        return {"deployer": first.get("contractCreator"), "tx": first.get("txHash"),
                "block": int(first["blockNumber"]) if str(first.get("blockNumber") or "").isdigit() else None,
                **({"factory": first["contractFactory"]} if first.get("contractFactory") else {})}

    def contract(self, address: str | None, implementation: str | None = None) -> tuple[list, str | None]:
        """(verified ABI entries, contract name) for an address, its implementation's merged in —
        the one its verifier resolved, else ``implementation`` (a proxy read from the chain)."""
        if not address:
            return [], None
        rec = self.record(address)
        entries, name = list(rec["entries"]), rec["name"]
        logic = rec["implementation"] or implementation
        if logic and to_checksum_address(logic) != to_checksum_address(address):
            impl = self.record(logic)
            entries += impl["entries"]
            name = impl["name"] or name
        return entries, name

    def selectors(self, sigs: list[str]) -> dict[str, list[str]]:
        """Signature-database guesses for function selectors (hex, no 0x), in one lookup: names that
        a verified contract uses first. Selectors collide, so every name here is a guess."""
        if not sigs or not self.online:
            return {}
        data = http_json(SIGNATURE_DB.format(base=self.bases["signatures"],
                                             sigs=",".join("0x" + s for s in sigs[:SELECTOR_BATCH])))
        found = ((data or {}).get("result") or {}).get("function") if isinstance(data, dict) else None
        out = {}
        for sig, rows in (found or {}).items():
            rows = [r for r in rows or [] if isinstance(r, dict) and isinstance(r.get("name"), str)
                    and _SIGNATURE.match(r["name"])]  # anyone can submit a name: keep only signatures
            rows.sort(key=lambda r: not r.get("hasVerifiedContract"))
            if rows:
                out[sig.lower().removeprefix("0x")] = [r["name"] for r in rows[:CANDIDATES]]
        return out

    def _lookup(self, url_template: str, sig: str) -> list[str]:
        if sig in self.fourbyte:
            return self.fourbyte[sig]
        found = []
        if self.online and self.fourbyte_left > 0:
            self.fourbyte_left -= 1
            data = http_json(url_template.format(base=self.bases["fourbyte"], sig="0x" + sig))
            if isinstance(data, dict):
                found = [r.get("text_signature") for r in data.get("results") or [] if r.get("text_signature")]
        self.fourbyte[sig] = found[:CANDIDATES]
        return self.fourbyte[sig]

    # calls

    def function(self, data: str, to: str | None = None) -> dict | None:
        """A decoded call, or a report of what could not be decoded; None for empty calldata."""
        raw = bytes.fromhex(data[2:] if data.startswith("0x") else data)
        if len(raw) == 0:
            return None
        if len(raw) < 4:
            return {"selector": None, "note": "calldata shorter than a selector", "size": len(raw)}
        sig, body = raw[:4].hex(), raw[4:]
        entries, _ = self.contract(to)
        candidates = [(from_json(e), "verified") for e in entries if e.get("type") == "function"]
        candidates = [(e, s) for e, s in candidates if selector(e) == sig]
        if sig in _FUNCS:
            candidates.append((_FUNCS[sig], "known"))
        tried = bool(candidates)
        for entry, source in candidates:
            decoded = self._decode_call(entry, body, source)
            if decoded:
                return decoded
        for text in self._lookup(FOURBYTE_FN, sig) if not tried else []:
            decoded = self._decode_call(parse(text), body, "guessed")
            if decoded:
                return decoded
        return {"selector": "0x" + sig, "source": "unknown", "size": len(raw)}

    def _decode_call(self, entry: dict, body: bytes, source: str) -> dict | None:
        types = [i["type"] for i in entry["inputs"]]
        try:
            values = abi_decode(types, body, strict=False) if types else ()
        except Exception:
            return None
        return {"function": entry["name"], "signature": canonical(entry), "source": source,
                "args": _args(entry["inputs"], values)}

    # events

    def event(self, log: dict) -> dict:
        topics = [t[2:] if t.startswith("0x") else t for t in log.get("topics") or []]
        data = bytes.fromhex((log.get("data") or "0x")[2:])
        base = {"contract": to_checksum_address(log["address"])}
        if not topics:
            return {**base, "event": None, "source": "anonymous", "data_size": len(data)}
        indexed_count = len(topics) - 1
        entries, _ = self.contract(log["address"])
        candidates = [(from_json(e), "verified") for e in entries if e.get("type") == "event"
                      and not e.get("anonymous")]
        candidates = [(e, s) for e, s in candidates if topic(e) == topics[0]]
        if (topics[0], indexed_count) in _EVENTS:
            candidates.append((_EVENTS[(topics[0], indexed_count)], "known"))
        for entry, source in candidates:
            decoded = self._decode_event(entry, topics, data, source)
            if decoded:
                return {**base, **decoded}
        if not candidates:
            for text in self._lookup(FOURBYTE_EV, topics[0]):
                entry = parse(text)
                for i, item in enumerate(entry["inputs"]):  # a guess: the first parameters are indexed
                    item["indexed"] = i < indexed_count
                decoded = self._decode_event(entry, topics, data, "guessed")
                if decoded:
                    return {**base, **decoded}
        return {**base, "event": None, "topic0": "0x" + topics[0], "source": "unknown",
                "topics": len(topics), "data_size": len(data)}

    def _decode_event(self, entry: dict, topics: list[str], data: bytes, source: str) -> dict | None:
        indexed = [i for i in entry["inputs"] if i["indexed"]]
        if len(indexed) != len(topics) - 1:
            return None
        plain_inputs = [i for i in entry["inputs"] if not i["indexed"]]
        try:
            values = abi_decode([i["type"] for i in plain_inputs], data, strict=False) if plain_inputs else ()
        except Exception:
            return None
        args, data_values, topic_values = {}, iter(values), iter(topics[1:])
        for n, item in enumerate(entry["inputs"]):
            name = item["name"] or f"arg{n}"
            if item["indexed"]:
                raw = bytes.fromhex(next(topic_values))
                dynamic = item["type"] in ("string", "bytes") or item["type"].endswith("]") \
                    or item["type"].startswith("(")
                if dynamic:
                    args[name] = {"hash": "0x" + raw.hex()}
                else:
                    try:
                        args[name] = plain(abi_decode([item["type"]], raw)[0], item["type"])
                    except Exception:
                        return None
            else:
                args[name] = plain(next(data_values), item["type"])
        return {"event": entry["name"], "signature": canonical(entry), "source": source, "args": args}

    # reverts

    def revert(self, data: str | None, to: str | None = None) -> dict | None:
        if not data or data in ("0x", ""):
            return None
        raw = bytes.fromhex(data[2:] if data.startswith("0x") else data)
        if len(raw) < 4:
            return {"raw": "0x" + raw.hex()}
        sig, body = raw[:4].hex(), raw[4:]
        try:
            if sig == ERROR_STRING:
                return {"error": "Error", "reason": untrusted(abi_decode(["string"], body)[0])}
            if sig == PANIC:
                code = abi_decode(["uint256"], body)[0]
                return {"error": "Panic", "code": hex(code), "meaning": PANICS.get(code, "unknown panic code")}
        except Exception:
            return {"raw": "0x" + raw.hex()[:200]}
        entries, _ = self.contract(to)
        for entry in (from_json(e) for e in entries if e.get("type") == "error"):
            if selector(entry) == sig:
                decoded = self._decode_call(entry, body, "verified")
                if decoded:
                    return {"error": decoded["function"], "signature": decoded["signature"],
                            "source": "verified", "args": decoded["args"]}
        for text in self._lookup(FOURBYTE_FN, sig):
            decoded = self._decode_call(parse(text), body, "guessed")
            if decoded:
                return {"error": decoded["function"], "signature": decoded["signature"],
                        "source": "guessed", "args": decoded["args"]}
        return {"selector": "0x" + sig, "source": "unknown"}


def known_function(sig: str) -> dict | None:
    """The built-in function for a selector (hex, no 0x), as ``parse`` returns it."""
    return _FUNCS.get(sig)


def known_event_topic(signature: str) -> str:
    """'0x…' topic0 of a signature written like 'Transfer(address,address,uint256)'."""
    return "0x" + topic(parse(signature))


TRANSFER_TOPIC = known_event_topic("Transfer(address,address,uint256)")
APPROVAL_TOPIC = known_event_topic("Approval(address,address,uint256)")
APPROVAL_FOR_ALL_TOPIC = known_event_topic("ApprovalForAll(address,address,bool)")
