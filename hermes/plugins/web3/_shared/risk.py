"""The ``risk`` read of the ``evm`` and ``solana`` tools: what a token's controllers can do to its
holders, run in the engine venv (docs/web3.md "Token risk").

No score. Each finding says what someone can do, how much it matters to a holder (``high``: take,
freeze, dilute or stop holders' tokens, or change the code; ``medium``: fees, limits, funds the
contract holds; ``low`` / ``info``: names, metadata, facts), the evidence it rests on and how sure it
is: a function's name is a lead, not proof of what its code does. ``controllers`` says who holds each
power — nobody, a single key, a multisig, a timelock or another contract — and ``unknowns`` names
what was not read. EVM reuses ``contract``'s reading at one block; Solana reads the mint, its
Token-2022 extensions, its Metaplex metadata and its largest token accounts.
"""

from __future__ import annotations

import base64
import re

from eth_abi import decode as abi_decode

import chains
import contracts
from evm import _bytes, checksum
from rpc import ChainError
import sol

SEVERITY = ("high", "medium", "low", "info")
MAX_CONTROLLERS = 8
CONTROL_NAME = re.compile(r"owner|admin|minter|pauser|blacklist|blocklist|rescuer|governor|governance|guardian|"
                          r"operator|manager|controller|authority", re.IGNORECASE)
POWER_RISK = {
    "mint": ("high", "can create more of the token, diluting every holder"),
    "pause": ("high", "can stop transfers for everyone"),
    "blocklist": ("high", "can freeze or block chosen holders"),
    "trading": ("high", "can switch trading on or off"),
    "upgrade": ("high", "can replace the contract's code, and with it every rule"),
    "fees": ("medium", "can set or change fees or taxes on transfers"),
    "limits": ("medium", "can cap how much one wallet may hold, buy or move"),
    "funds": ("medium", "can move tokens or coins the contract itself holds"),
    "control": ("info", "can hand control to someone else, grant roles or give them up"),
}
GET_THRESHOLD, GET_OWNERS, GET_MIN_DELAY = "e75235b8", "a0e67e2b", "f27a0c92"
NOTE = ("No score: each finding says what someone can do and to whom, with its evidence and how sure it is. "
        "Function names are leads, not proof; who holds a power (controllers) decides how much it matters.")


def _finding(severity: str, area: str, finding: str, evidence, confidence: str = "high") -> dict:
    return {"severity": severity, "area": area, "finding": finding, "evidence": evidence, "confidence": confidence}


def _sorted(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=lambda f: SEVERITY.index(f["severity"]))


def _duration(seconds: int) -> str:
    for unit, size in (("days", 86400), ("hours", 3600), ("minutes", 60)):
        if seconds >= size:
            return f"{seconds / size:g} {unit}"
    return f"{seconds} seconds"


# --- EVM --------------------------------------------------------------------------------------------

UNREAD = {"kind": "unread", "note": "not read (the RPC did not answer)"}


def _failed(error) -> bool:
    """A failure to read, not an answer (a revert says the function is not there)."""
    return error is not None and "revert" not in str(error).lower()


def _evm_whos(ctx, addresses: list[str], block: str) -> dict[str, dict]:
    """Who each address is, as a holder of power: nobody, a key, a Safe multisig, a timelock, a contract
    or unread. Read in batches: every address's code, then the Safe and timelock probes of contracts."""
    found: dict[str, dict] = {}
    live = [a for a in addresses if int(a, 16)]
    for address in addresses:
        if not int(address, 16):
            found[address] = {"kind": "nobody", "note": "nobody (the zero address: unset or renounced)"}
    codes = ctx.rpc.batch_detailed([("eth_getCode", [a, block]) for a in live])
    contracts_ = []
    for address, (code, error) in zip(live, codes):
        if error:
            found[address] = UNREAD
            continue
        raw = _bytes(code)
        if not raw:
            found[address] = {"kind": "key", "note": "a single key (an EOA)"}
        elif raw.startswith(b"\xef\x01\x00") and len(raw) == 23:
            found[address] = {"kind": "key", "note": "a single key with delegated code (EIP-7702)"}
        else:
            contracts_.append(address)
    probes = ctx.rpc.batch_detailed([("eth_call", [{"to": a, "data": "0x" + sel}, block])
                                     for a in contracts_ for sel in (GET_THRESHOLD, GET_OWNERS, GET_MIN_DELAY)])
    for i, address in enumerate(contracts_):
        (threshold, e1), (owners, e2), (delay, e3) = probes[3 * i:3 * i + 3]
        try:
            if threshold and len(_bytes(threshold)) >= 32 and owners:
                count = len(abi_decode(["address[]"], _bytes(owners))[0])
                needed = int.from_bytes(_bytes(threshold)[:32], "big")
                if 0 < needed <= count:
                    found[address] = {"kind": "multisig", "threshold": needed, "owners": count,
                                      "note": f"a {needed}-of-{count} Safe multisig"}
                    continue
        except Exception:
            pass
        if delay and len(_bytes(delay)) >= 32:
            seconds = int.from_bytes(_bytes(delay)[:32], "big")
            found[address] = {"kind": "timelock", "delay_seconds": seconds,
                              "note": f"a timelock: a change waits {_duration(seconds)} before it can run"}
        elif any(_failed(e) for e in (e1, e2, e3)):
            found[address] = {"kind": "contract", "note": "a contract (whether it is a multisig or a timelock was "
                                                          "not read: the RPC did not answer)", "partial": True}
        else:
            found[address] = {"kind": "contract", "note": "a contract (what governs it was not read)"}
    return found


def _is_address(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", value) is not None


def evm_risk(ctx, args) -> dict:
    target = args.get("token") or args.get("address")
    report = contracts.contract(ctx, {"address": target})
    block = hex(report["block"])
    findings, unknowns = [], []
    proxy = report.get("proxy") or {}
    verified = report.get("verified") or {}
    runs = verified.get("implementation") if "implementation" in verified else verified.get("contract")
    guessed = not (runs or {}).get("by")
    confidence = "low" if guessed else "medium"
    if guessed:
        findings.append(_finding("high", "code", "the code that runs is not verified: what it can do is guessed from "
                                                 "its function selectors, and anything else it does is unseen",
                                 {"verified": verified}))

    state = report.get("state") or {}
    roles = {name: value for name, value in state.items()
             if _is_address(value) and (CONTROL_NAME.search(name) or name in ("owner", "getOwner", "admin"))}
    if proxy.get("admin"):
        roles["proxy admin"] = proxy["admin"]
    looked = list(dict.fromkeys(checksum(v) for v in roles.values()))
    controllers = _evm_whos(ctx, looked[:MAX_CONTROLLERS], block)
    if len(looked) > MAX_CONTROLLERS:
        unknowns.append(f"who the role holders past the first {MAX_CONTROLLERS} are")
    unread = [a for a, who in controllers.items() if who["kind"] == "unread" or who.get("partial")]
    if unread:
        unknowns.append("what these role holders are (the RPC did not answer): " + ", ".join(unread))
    holders = {name: {"address": checksum(value), "is": controllers.get(checksum(value), {}).get("note")}
               for name, value in roles.items()}

    kind = proxy.get("type")
    if kind == "EIP-1167 minimal proxy":
        findings.append(_finding("info", "upgrade", "a minimal proxy (a clone): its code is fixed to its "
                                                    "implementation and cannot be upgraded", {"proxy": proxy}))
    elif kind == "EIP-1967 beacon":
        findings.append(_finding("high", "upgrade", "upgradeable through a beacon: whoever controls the beacon "
                                 + POWER_RISK["upgrade"][1], {"proxy": proxy}))
        unknowns.append("who controls the beacon (read the beacon contract's owner)")
    elif proxy:
        admin = proxy.get("admin")
        who = controllers.get(checksum(admin), {}).get("note") if admin else None
        findings.append(_finding(
            "high", "upgrade",
            f"upgradeable ({kind or 'a proxy its verifier names'}): "
            + (f"the proxy admin, {who}, " if who else "whoever the implementation lets upgrade ")
            + POWER_RISK["upgrade"][1], {"proxy": proxy}, "high" if kind else "medium"))
    powers = report.get("powers") or {}
    for power, names in powers.items():
        if power == "upgrade" and proxy:
            continue
        severity, what = POWER_RISK.get(power, ("info", "has a power of its own"))
        findings.append(_finding(severity, power, f"functions named like {power} exist: whoever may call them {what}",
                                 {"functions": names[:8]}, confidence))
    granted = any(re.search(r"grantrole|revokerole", n.lower()) for n in powers.get("control", []))
    reads = (report.get("functions") or {}).get("read", [])
    if granted or any(isinstance(f, str) and f.startswith("hasRole(") for f in reads):
        unknowns.append("who holds the roles granted with grantRole (AccessControl): read the RoleGranted and "
                        "RoleRevoked logs")
    elif any(f["severity"] == "high" and f["area"] in POWER_RISK for f in findings if f["area"] != "upgrade") \
            and not controllers:
        unknowns.append("who may call the powers above (no role getter names a holder)")
    owner = state.get("owner") or state.get("getOwner")
    if _is_address(owner) and int(owner, 16) == 0:
        findings.append(_finding("info", "control", "ownership is renounced: owner-only functions can no longer run"
                                 + (" (the proxy can still be upgraded by its admin)" if proxy.get("admin") else ""),
                                 {"owner": owner}))
    by_address: dict[str, list[str]] = {}
    for name, value in roles.items():
        by_address.setdefault(checksum(value), []).append(name)
    for address, names in by_address.items():
        who = controllers.get(address, {})
        if who.get("kind") == "key":
            findings.append(_finding("medium", "control", f"{'a role is' if len(names) == 1 else 'roles are'} held by "
                                                          f"{who['note']}: one key, no co-signers or delay",
                                     {"roles": names, "address": address}))
        elif who.get("kind") == "multisig" and who.get("threshold") == 1:
            findings.append(_finding("medium", "control", f"{'a role is' if len(names) == 1 else 'roles are'} held by "
                                                          f"{who['note']}: any one of its keys can act alone",
                                     {"roles": names, "address": address}))
    if state.get("paused") is True:
        findings.append(_finding("high", "pause", "the token reads as paused now: transfers are stopped",
                                 {"paused": True}, "medium"))
    if not {"totalSupply", "decimals"} & set(state):
        findings.append(_finding("info", "code", "no ERC-20 supply or decimals was read: this may not be a token",
                                 {"state": sorted(state)[:10]}, "medium"))

    if report.get("state_unread"):
        unknowns.append("getters the RPC would not answer: " + ", ".join(report["state_unread"]))
    unknowns.append("how concentrated the holders are (EVM holder lists need an indexer)")
    if not guessed:
        unknowns.append("what each function's code actually does beyond its name (read the verified source)")
    supply = {k: state[k] for k in ("totalSupply", "cap", "maxSupply", "decimals") if k in state}
    return {"chain": ctx.chain, "token": report["address"], "block": report["block"],
            "name": state.get("name"), "symbol": state.get("symbol"), "supply": supply or None,
            "verified": verified, "proxy": proxy or None, "findings": _sorted(findings),
            "controllers": holders, "unknowns": unknowns, "explorer": report.get("explorer"), "note": NOTE}


# --- Solana -----------------------------------------------------------------------------------------

METADATA_PROGRAM = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAMS = {"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}


def _sol_who(ctx, address: str | None) -> dict | None:
    """Who an authority is: a key (a wallet), an address only a program can sign for (a PDA: a program,
    a Squads vault or another multisig decides), an SPL multisig, a program, or unread."""
    if not address:
        return None
    from solders.pubkey import Pubkey
    try:
        off_curve = not Pubkey.from_string(address).is_on_curve()
    except Exception:
        off_curve = False
    try:
        got = ctx.rpc.call("getAccountInfo", [address, {"encoding": "jsonParsed"}])
    except ChainError:
        return UNREAD
    value = (got or {}).get("value")
    owner = (value or {}).get("owner")
    data = (value or {}).get("data")
    parsed = (data.get("parsed") or {}) if isinstance(data, dict) else {}
    if off_curve and (not value or owner == SYSTEM_PROGRAM):
        return {"kind": "program-derived", "note": "an address only a program can sign for (a PDA: a program or "
                                                   "a multisig such as Squads decides)"}
    if not value:
        return {"kind": "key", "note": "a single key (an account holding nothing yet)"}
    if owner == SYSTEM_PROGRAM:
        return {"kind": "key", "note": "a single key (a wallet)"}
    if owner in TOKEN_PROGRAMS and parsed.get("type") == "multisig":
        info = parsed.get("info") or {}
        needed, count = info.get("numRequiredSigners"), info.get("numValidSigners")
        return {"kind": "multisig", "threshold": needed, "owners": count,
                "note": f"an SPL Token {needed}-of-{count} multisig"}
    if value.get("executable"):
        return {"kind": "program", "note": "a program"}
    return {"kind": "program-owned", "note": f"an account owned by program {owner} (a PDA or a governance account)"}


def _metaplex(ctx, mint: str) -> dict | None:
    """The update authority and mutability of a mint's Metaplex metadata, or None when it has none."""
    from solders.pubkey import Pubkey
    program = Pubkey.from_string(METADATA_PROGRAM)
    pda, _ = Pubkey.find_program_address([b"metadata", bytes(program), bytes(Pubkey.from_string(mint))], program)
    got = ctx.rpc.call("getAccountInfo", [str(pda), {"encoding": "base64"}])
    value = (got or {}).get("value")
    if not value or value.get("owner") != METADATA_PROGRAM:
        return None
    raw = base64.b64decode(value["data"][0])
    authority = str(Pubkey.from_bytes(raw[1:33]))
    at = 65
    for _ in range(3):  # name, symbol, uri: borsh strings
        at += 4 + int.from_bytes(raw[at:at + 4], "little")
    at += 2  # seller fee basis points
    if raw[at]:  # creators
        at += 1 + 4 + int.from_bytes(raw[at + 1:at + 5], "little") * 34
    else:
        at += 1
    at += 1  # primary sale happened
    return {"update_authority": authority, "mutable": bool(raw[at]), "metadata": str(pda)}


EXTENSION_ROLES = {"transferFeeConfigAuthority": "transfer fee authority", "delegate": "permanent delegate",
                   "closeAuthority": "mint close authority", "updateAuthority": "token metadata update authority",
                   "rateAuthority": "interest rate authority"}


def _extension_findings(name: str, state: dict, holder) -> list[dict]:
    """Findings for one Token-2022 extension; ``holder(role, address)`` records who holds its power."""
    def who(key):
        address = state.get(key)
        role = EXTENSION_ROLES.get(key) or f"{name} {key}"
        found = holder(role, address) if address else None
        return (address, found["note"] if found else None)

    if name == "transferFeeConfig":
        newer = (state.get("newerTransferFee") or {}).get("transferFeeBasisPoints")
        fee = newer if newer is not None else (state.get("olderTransferFee") or {}).get("transferFeeBasisPoints") or 0
        address, note = who("transferFeeConfigAuthority")
        severity = "high" if fee else "medium"
        return [_finding(severity, "fees", f"every transfer pays a fee of {fee / 100:g}% to the mint"
                         + (f"; {note} can change it" if note else "; nobody can change it"),
                         {"transfer_fee_bps": fee, "authority": address})]
    if name == "permanentDelegate":
        address, note = who("delegate")
        if address:
            return [_finding("high", "control", f"a permanent delegate, {note}, can move or burn tokens from any "
                                                "holder at any time", {"permanent_delegate": address})]
        return []
    if name == "transferHook":
        program = state.get("programId")
        address, note = who("authority")
        if program:
            return [_finding("high", "trading", "a program runs on every transfer and can refuse it"
                             + (f"; {note} can change that program" if note else ""),
                             {"transfer_hook_program": program, "authority": address})]
        return []
    if name == "defaultAccountState" and state.get("accountState") == "frozen":
        return [_finding("high", "blocklist", "every new holder's account starts frozen until the freeze authority "
                                              "thaws it", {"default_state": "frozen"})]
    if name == "nonTransferable":
        return [_finding("high", "trading", "the token cannot be transferred at all", {"extension": name})]
    if name in ("pausableConfig", "pausable"):
        address, note = who("authority")
        return [_finding("high", "pause", "transfers can be paused" + (f" by {note}" if note else "")
                         + (" and are paused now" if state.get("paused") else ""),
                         {"authority": address, "paused": state.get("paused")})]
    if name == "mintCloseAuthority":
        address, note = who("closeAuthority")
        return [_finding("medium", "control", "the mint can be closed" + (f" by {note}" if note else ""),
                         {"close_authority": address})] if address else []
    if name in ("interestBearingConfig", "scaledUiAmountConfig"):
        address, note = who("rateAuthority" if name == "interestBearingConfig" else "authority")
        return [_finding("medium", "fees", "the displayed balance is scaled by a rate or multiplier"
                         + (f" that {note} can change" if note else ""), {"extension": name, "authority": address})]
    if name == "confidentialTransferMint":
        return [_finding("low", "code", "confidential transfers are on: some balances and amounts can be hidden",
                         {"extension": name})]
    if name == "tokenMetadata":
        address, note = who("updateAuthority")
        return [_finding("low", "metadata", "the token's name, symbol and links can be changed"
                         + (f" by {note}" if note else ""), {"update_authority": address})] if address else []
    return [_finding("info", "code", f"Token-2022 extension {name} is on", {"extension": name})]


def sol_risk(ctx, args) -> dict:
    mint = sol.require_address(args.get("token") or args.get("address"))
    got = ctx.rpc.call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    value = (got or {}).get("value") or {}
    data = value.get("data")
    parsed = (data.get("parsed") or {}) if isinstance(data, dict) else {}
    if parsed.get("type") != "mint":
        raise ChainError("that address is not a token mint")
    details = parsed.get("info") or {}
    findings, unknowns, controllers = [], [], {}

    def holder(role: str, address: str | None):
        found = _sol_who(ctx, address)
        if found:
            controllers[role] = {"address": address, "is": found["note"]}
            if found["kind"] == "unread":
                unknowns.append(f"what the {role} {address} is (the RPC did not answer)")
        return found

    minter = holder("mint authority", details.get("mintAuthority"))
    if minter:
        findings.append(_finding("high", "mint", f"the mint authority, {minter['note']}, can create more of the "
                                                 "token, diluting every holder",
                                 {"mint_authority": details["mintAuthority"]}))
    else:
        findings.append(_finding("info", "mint", "the supply is fixed: there is no mint authority",
                                 {"mint_authority": None}))
    freezer = holder("freeze authority", details.get("freezeAuthority"))
    if freezer:
        findings.append(_finding("high", "blocklist", f"the freeze authority, {freezer['note']}, can freeze any "
                                                      "holder's tokens", {"freeze_authority": details["freezeAuthority"]}))
    for extension in details.get("extensions") or []:
        findings += _extension_findings(extension.get("extension"), extension.get("state") or {}, holder)

    try:
        meta = _metaplex(ctx, mint)
    except Exception:  # an RPC refusal or malformed metadata alike
        meta = None
        unknowns.append("the Metaplex metadata could not be read")
    if meta:
        who = holder("metadata update authority", meta["update_authority"])
        if meta["mutable"]:
            findings.append(_finding("low", "metadata", f"the name, symbol and image link can be changed by "
                                                        f"{who['note'] if who else 'its update authority'}",
                                     {"update_authority": meta["update_authority"], "mutable": True}))
        else:
            findings.append(_finding("info", "metadata", "the Metaplex metadata is immutable", {"mutable": False}))

    decimals = details.get("decimals") or 0
    supply = int(details.get("supply") or 0)
    largest, error = ctx.rpc.try_call("getTokenLargestAccounts", [mint, {"commitment": "confirmed"}])
    rows = (largest or {}).get("value") if isinstance(largest, dict) else None
    if error or not isinstance(rows, list):
        unknowns.append("how concentrated the holders are (the RPC would not list the largest token accounts)")
    elif supply:
        amounts = sorted((int(r.get("amount") or 0) for r in rows), reverse=True)
        top1, top10 = amounts[0] / supply if amounts else 0, sum(amounts[:10]) / supply
        # a lead, not a power: the largest account is often a pool or an exchange, so never above medium
        severity = "medium" if top1 >= 0.5 or top10 >= 0.8 else "info"
        findings.append(_finding(severity, "holders", f"the largest token account holds {top1:.1%} of the supply and "
                                                      f"the largest ten {top10:.1%}",
                                 {"top1_share": round(top1, 4), "top10_share": round(top10, 4)}, "medium"))
        unknowns.append("who owns the largest token accounts (pools, exchanges and locks hold for many people)")
    return {"chain": ctx.chain, "token": mint, "slot": ((got or {}).get("context") or {}).get("slot"),
            "program": sol.program_name(value.get("owner")), "decimals": decimals,
            "supply": str(supply), "findings": _sorted(findings), "controllers": controllers,
            "unknowns": unknowns, "explorer": chains.explorer(ctx.chain, "token", mint), "note": NOTE}


EVM_ACTIONS = {"risk": evm_risk}
SOL_ACTIONS = {"risk": sol_risk}
