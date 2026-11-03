"""cloudflare-access: zone mandates — the user's standing approval for a bounded kind of zone change.

A mandate is made only on its own approval card and names: one account (its label and id), one to
three of that account's zones (by id), the classes of change it covers (``dns``: proxied A, AAAA and
CNAME records added or updated; ``settings``: settings that neither weaken protection nor turn it
off; ``purge``: URLs, hosts or prefixes), how many covered changes an hour it allows (each record,
setting, URL, host or prefix of a call counts one), a purpose, and an end at most MAX_DAYS out. A
change runs without its card only when it fits one mandate: its class is covered, its account and
zone are the mandate's, and it is none of what is never covered, whatever the terms say: a delete,
any other record type, an unproxied record, a name starting with ``_``, a record that is or becomes
a tunnel's CNAME, a setting that weakens protection or turns a protective one off, a purge of
everything, a tunnel route, an e-mail rule, a rollback, storage, any change whose card is 🚨, and a
call with more changes than the mandate allows an hour.

State, in the profile home (never the repository; the plugin's guard blocks file and terminal
access), kept by the shared store and ledger (``plugins/_shared/mandate_store.py``,
``plugins/_shared/mandate_ledger.py``):

  <HERMES_HOME>/cloudflare-access/mandates/<id>.json   the terms, MAC'd
  <HERMES_HOME>/cloudflare-access/head.json            the ids in force, MAC'd: only the head decides
  <HERMES_HOME>/cloudflare-access/uses.jsonl           one MAC'd opening row per mandate, then one per
                                                       counted change
  <HERMES_HOME>/cloudflare-access/mandates.jsonl       made / revoked history, for the record only

The MAC key is a random key in the Keychain (``CLOUDFLARE_MANDATE_KEY_<PROFILE>``, project hermes,
scope cloudflare-access, a scope no profile receives), made with the first mandate. Without a
readable key no mandate is in force and every change asks on its card. ``use`` is the write-time
check and the count in one step, under the store's lock: a change is counted before it is sent,
whatever becomes of it. Contract: docs/decisions/cloudflare-mandates.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import threading
import time
from pathlib import Path


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


_SHARED = Path(__file__).resolve().parents[1] / "_shared"
cards = _load("hermes_card", _SHARED / "card.py")
mandate_store = _load("hermes_mandate_store", _SHARED / "mandate_store.py")
mandate_ledger = _load("hermes_mandate_ledger", _SHARED / "mandate_ledger.py")

STATE = "cloudflare-access"
MAX_DAYS = 7
MAX_ZONES = 3
MAX_PER_HOUR = 20
HOUR = 3600
DAY = mandate_store.DAY
PURPOSE_LIMIT = 200
CARD_TTL = 900          # how long a mandate card's record stays valid
HEAD_FILE = "head.json"   # the store's (plugins/_shared/mandate_store.py)
LEDGER_KIND = "cloudflare-use"
TUNNEL_SUFFIX = ".cfargotunnel.com"
NAME_CLIPS = ((80, 120), (40, 60), (20, 30))   # (zone name, purpose): shortened before a bound is left out

CLASSES = ("dns", "settings", "purge")
ACTION_CLASS = {"dns_change": "dns", "zone_setting": "settings", "cache_purge": "purge"}
CLASS_WORDS = {"dns": "DNS: proxied A, AAAA, CNAME (add, update)", "settings": "settings (none weakened)",
               "purge": "purges (not everything)"}
DNS_TYPES = ("A", "AAAA", "CNAME")
# Settings whose value turns a protection that visitors or addresses rely on off, whatever the setting was
# before: the card's own level only judges a move down a scale (cfa.STRENGTH), so a mandate adds these.
PROTECTIVE_OFF = {"ssl": ("off",), "always_use_https": ("off",), "automatic_https_rewrites": ("off",),
                  "tls_1_3": ("off",), "security_level": ("off", "essentially_off"), "email_obfuscation": ("off",)}
# What each class sends: the method, the request path under the zone (a pattern) and the body keys it
# may carry.
CLASS_ROUTES = {"dns": ("POST", r"dns_records/batch", {"patches", "posts"}),
                "settings": ("PATCH", r"settings/[a-z0-9_]+", {"value"}),
                "purge": ("POST", r"purge_cache", {"files", "hosts", "prefixes"})}

EFFECT = (cards.DANGER, "Covered changes to these zones skip the card")
NEVER = ("deletes, MX/TXT/NS and unproxied records, weaker protection, purging everything, tunnels, e-mail "
         "rules, rollbacks, storage")
NO_KEY = "no mandate key is readable: nothing is in force"
LEDGER_USED_UP = "its change count cannot be read (the ledger is missing or was changed); it counts as used up"
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class MandateError(ValueError):
    """The terms are not acceptable, or the mandate could not be kept."""


STORE = mandate_store.Store(state=STATE, key_prefix="CLOUDFLARE_MANDATE_KEY_", scope="cloudflare-access",
                            mac_kind="cloudflare-mandate", key_note="cloudflare-access mandate MAC key",
                            error=MandateError, max_days=MAX_DAYS)

# The hour's count of a ledger that cannot be vouched for: it equals MAX_PER_HOUR, so every mandate
# reads as used up, and ``_hourly`` can still tell it from a real count that reached the same number.
USED_UP = mandate_ledger.UsedUp(MAX_PER_HOUR)


# --- terms ----------------------------------------------------------------------------------------

def _whole(value, name: str, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise MandateError(f"{name} is a whole number from {low} to {high}")
    return value


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MandateError(f"{what} (a non-empty string)")
    return value.strip()


def _zone(zone) -> dict:
    if not isinstance(zone, dict):
        raise MandateError("each zone is {id, name}")
    zone_id = _text(zone.get("id"), "each zone has an id")
    if not ID_PATTERN.fullmatch(zone_id):
        raise MandateError("each zone is named by its id (32 hexadecimal characters)")
    return {"id": zone_id, "name": " ".join(_text(zone.get("name"), "each zone has a name").split())}


def terms(account: str, account_id: str, zones: list, classes: list, per_hour: int, days: int, purpose: str,
          now: float | None = None) -> dict:
    """The terms of a new mandate, checked. ``zones`` are the account's zones as Cloudflare resolved them
    ({id, name}). The end is fixed now, when the card is drawn, so what is stored ends when the card said."""
    account = _text(account, "account is the label of a stored token")
    account_id = _text(account_id, "account_id is the Cloudflare account's id")
    if not ID_PATTERN.fullmatch(account_id):
        raise MandateError("account_id is a Cloudflare account id (32 hexadecimal characters)")
    if not isinstance(zones, (list, tuple)) or not 1 <= len(zones) <= MAX_ZONES:
        raise MandateError(f"zones is a list of one to {MAX_ZONES} zones")
    named = [_zone(zone) for zone in zones]
    if len({zone["id"] for zone in named}) != len(named):
        raise MandateError("each zone is named once")
    if (not isinstance(classes, (list, tuple)) or not classes
            or any(not isinstance(c, str) or c not in CLASSES for c in classes)):
        raise MandateError(f"classes is a list of: {', '.join(CLASSES)}")
    per_hour = _whole(per_hour, "per_hour", 1, MAX_PER_HOUR)
    days = _whole(days, "days", 1, MAX_DAYS)
    purpose = " ".join(str(purpose or "").split())
    if not purpose:
        raise MandateError("purpose says what the mandate is for (one line)")
    if len(purpose) > PURPOSE_LIMIT:
        raise MandateError(f"purpose is at most {PURPOSE_LIMIT} characters")
    now = time.time() if now is None else now
    return {"account": account, "account_id": account_id, "zones": named,
            "classes": [c for c in CLASSES if c in classes], "per_hour": per_hour, "days": days,
            "expires": int(now) + days * DAY, "purpose": purpose}


def same_terms(a: dict, b: dict) -> bool:
    """Whether two readings of a create call agree on everything but the end (fixed at the card)."""
    return {k: v for k, v in a.items() if k != "expires"} == {k: v for k, v in b.items() if k != "expires"}


def card(t: dict) -> str:
    """The shared card shape (plugins/_shared/card.py) with every bound of the mandate on it: the rules
    every mandate shares go last and are dropped first, the zone names and the purpose shrink until it fits,
    and a mandate whose card still does not fit is refused."""
    end = time.strftime("%Y-%m-%d %H:%M", time.localtime(t["expires"]))
    for name_clip, purpose_clip in NAME_CLIPS:
        facts = [("Account", f"{cards.line(t['account'], 40)} ({t['account_id']})")]
        facts += [("Zone", f"{cards.line(z['name'], name_clip)} ({z['id']})") for z in t["zones"]]
        facts += [("Covers", ", ".join(CLASS_WORDS[c] for c in t["classes"])),
                  ("Up to", f"{t['per_hour']} changes an hour"),
                  ("Until", f"{end} ({t['days']} day{'s' if t['days'] != 1 else ''})"),
                  ("Purpose", cards.line(t["purpose"], purpose_clip))]
        try:
            return cards.compose("Cloudflare", "Zone mandate", EFFECT, facts, context=[("Never covered", NEVER)])
        except cards.CardError:
            continue
    raise MandateError("the mandate's card cannot show all its bounds; name fewer zones or classes (a Discord "
                       "chat shows a shorter card than Telegram)")


# --- the card a create call was shown -------------------------------------------------------------
# The hook records the terms its card showed, per exact call; the handler takes that record once. A
# create call whose card was never shown (or shown too long ago) makes nothing.

_SHOWN: dict[str, tuple[float, dict]] = {}
_SHOWN_LOCK = threading.Lock()


def _call_key(args: dict, call_id: str) -> str:
    return hashlib.sha256(json.dumps([call_id or "", args], sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def note_card(args: dict, call_id: str, t: dict) -> None:
    now = time.monotonic()
    with _SHOWN_LOCK:
        for old in [k for k, (at, _) in _SHOWN.items() if now - at > CARD_TTL]:
            del _SHOWN[old]
        _SHOWN[_call_key(args, call_id)] = (now, t)


def take_card(args: dict, call_id: str) -> dict | None:
    """The terms the card of this very call showed, consumed; None without one."""
    with _SHOWN_LOCK:
        found = _SHOWN.pop(_call_key(args, call_id), None)
    if not found or time.monotonic() - found[0] > CARD_TTL:
        return None
    return found[1]


# --- what is in force -----------------------------------------------------------------------------

def active(home, now: float | None = None) -> list[dict]:
    """The mandates in force: in the authenticated head, authenticated themselves, not ended. Until a first
    mandate has been made there is no head, and the Keychain is not asked."""
    if not (mandate_store.state_dir(STORE, home) / HEAD_FILE).is_file():
        return []
    return mandate_store.active(STORE, home, now)


def create(home, t: dict) -> dict:
    """Make the mandate the card showed; returns its ``summary``. Its opening row goes into the ledger right
    after: a mandate whose opening row is missing counts as used up, so one that cannot be anchored is
    revoked and nothing is made."""
    fields = {k: t[k] for k in ("account", "account_id", "zones", "classes", "per_hour", "purpose")}
    body = mandate_store.create(STORE, home, fields, t["expires"])
    try:
        with mandate_store.locked(STORE, home):
            secret = mandate_store.key(STORE, home)
            if secret is None:
                raise MandateError(NO_KEY)
            mandate_ledger.anchor(STORE, home, secret, LEDGER_KIND, body["id"], body["created"])
    except (OSError, MandateError) as exc:
        try:
            mandate_store.revoke(STORE, home, body["id"])
            ended = "it was revoked"
        except (OSError, MandateError) as revoke_exc:
            ended = f"it could not be revoked ({revoke_exc}); revoke {body['id']}"
        raise MandateError(f"the mandate could not be recorded in its ledger ({exc}); nothing was made, "
                           f"{ended}") from exc
    return summary(body)


def revoke(home, mandate_id: str) -> dict:
    """Take a mandate out of force at once; needs no card."""
    return mandate_store.revoke(STORE, home, mandate_id)


def summary(body: dict) -> dict:
    return {"id": body["id"], "until": time.strftime("%Y-%m-%d %H:%M", time.localtime(body["expires"])),
            "account": body["account"], "zones": [z["name"] for z in body["zones"]], "classes": body["classes"],
            "per_hour": body["per_hour"], "purpose": body["purpose"]}


# --- does a change fit ----------------------------------------------------------------------------

def _tunnel(content) -> bool:
    return isinstance(content, str) and content.strip().rstrip(".").lower().endswith(TUNNEL_SUFFIX)


def _shape(cls: str, plan: dict) -> str | None:
    """Why the plan's requests are not the ones its class sends (a delete, a purge of everything, another
    route), or None. The class is judged from what would be sent, not from what the card says."""
    method, tail, keys = CLASS_ROUTES[cls]
    route = re.compile(re.escape(f"/zones/{plan['zone_id']}/") + tail)
    steps = plan.get("steps") or []
    if not steps:
        return "it sends nothing"
    for step in steps:
        path, body = step.get("path"), step.get("body")
        if step.get("method") != method or not isinstance(path, str) or not route.fullmatch(path):
            return f"{plan['action']} sends a request outside the {cls} class"
        if not isinstance(body, dict) or not body or not set(body) <= keys:
            if isinstance(body, dict) and "deletes" in body:
                return "a delete always asks on a card"
            if isinstance(body, dict) and "purge_everything" in body:
                return "purging everything always asks on a card"
            return f"{plan['action']} sends more than the {cls} class covers"
    return None


def _hidden_name(name) -> bool:
    """Whether the record's first label starts with ``_``: a challenge, key or service record (``_acme-challenge``,
    ``_dmarc``), which proves or grants something instead of pointing a host."""
    return not isinstance(name, str) or name.strip().startswith("_")


def _dns_record(kind, proxied, names: list, contents: list) -> str | None:
    """Why a record, as it is now (``names`` and ``contents`` hold both its old and new value) and as it would
    be (``kind``, ``proxied``), is not one a mandate covers, or None."""
    if kind not in DNS_TYPES:
        return f"a {kind} record always asks on a card (a mandate covers A, AAAA and CNAME only)"
    if proxied is not True:
        return "a record that is not proxied always asks on a card"
    if any(_hidden_name(name) for name in names):
        return "a name starting with _ always asks on a card"
    if any(_tunnel(content) for content in contents):
        return "a record that points at a tunnel (*.cfargotunnel.com) always asks on a card"
    return None


def _dns_rules(plan: dict) -> str | None:
    """Why a DNS item is not an add or update of a proxied A, AAAA or CNAME record under an ordinary name, or
    None. An update is judged on the record as Cloudflare has it now (``replaced``) with the patch applied."""
    now = {r.get("id"): r for r in plan.get("replaced") or [] if isinstance(r, dict)}
    for step in plan.get("steps") or []:
        body = step.get("body") if isinstance(step.get("body"), dict) else {}
        for post in body.get("posts") or []:
            if not isinstance(post, dict):
                return "a DNS item always asks on a card unless it is a record to add or update"
            why = _dns_record(post.get("type"), post.get("proxied"), [post.get("name")], [post.get("content")])
            if why:
                return why
        for patch in body.get("patches") or []:
            record = now.get(patch.get("id")) if isinstance(patch, dict) else None
            if record is None:
                return "a DNS update of a record not read for the card always asks on a card"
            why = _dns_record(record.get("type"), patch.get("proxied", record.get("proxied")),
                              [record.get("name"), patch.get("name", record.get("name"))],
                              [record.get("content"), patch.get("content", record.get("content"))])
            if why:
                return why
    return None


def _setting_rules(plan: dict) -> str | None:
    """Why a setting would be turned to a value that switches a protection off, or None (what is sent is
    read: ``PATCH /zones/<id>/settings/<setting>`` with its value)."""
    for step in plan.get("steps") or []:
        setting = str(step.get("path")).rsplit("/", 1)[-1]
        value = str((step.get("body") or {}).get("value")).strip().lower()
        if value in PROTECTIVE_OFF.get(setting, ()):
            return f"turning {setting} {value} always asks on a card"
    return None


def weight(plan: dict) -> int:
    """How many changes the plan makes, which is what the hourly bound counts: a DNS record added or updated,
    a setting, a URL, host name or prefix purged; at least one."""
    cls = ACTION_CLASS.get(plan.get("action"))
    steps = [s for s in plan.get("steps") or [] if isinstance(s, dict)]
    if cls == "settings":
        return max(1, len(steps))
    return max(1, sum(len(items) for s in steps if isinstance(s.get("body"), dict)
                      for items in s["body"].values() if isinstance(items, list)))


def fits(m: dict, plan: dict) -> str | None:
    """Why the write plan (``cfa.write_plan``) does not fit mandate ``m``, or None when it does."""
    cls = ACTION_CLASS.get(plan.get("action"))
    if cls is None:
        return f"{plan.get('action')} always asks on a card"
    if cls not in m["classes"]:
        return f"{plan['action']} is a {cls} change; the mandate covers {', '.join(m['classes'])}"
    if plan.get("account") != m["account"] or plan.get("account_id") != m["account_id"]:
        return "the change is on another account than the mandate's"
    if plan.get("zone_id") not in {z["id"] for z in m["zones"]}:
        return f"{plan['facts'][0][1] if plan.get('facts') else 'the zone'} is outside the mandate"
    # Only a card known to be below 🚨, and not one that asks each time (a purge of everything), is covered.
    if plan.get("once") is not False or not plan.get("effect") or plan["effect"][0] == cards.DANGER:
        return "a delete, weaker protection, purging everything or any 🚨 change always asks on a card"
    why = _shape(cls, plan) or {"dns": _dns_rules, "settings": _setting_rules}.get(cls, lambda _plan: None)(plan)
    if why is None and weight(plan) > m["per_hour"]:
        return f"it makes {weight(plan)} changes; the mandate allows {m['per_hour']} an hour"
    return why


def _hourly(m: dict, used: int, changes: int) -> str | None:
    """Why ``changes`` more do not fit the hour that already holds ``used``, or None."""
    if isinstance(used, mandate_ledger.UsedUp):
        return LEDGER_USED_UP
    if used + changes > m["per_hour"]:
        return (f"{used} changes in the last hour and this makes {changes}; the mandate allows "
                f"{m['per_hour']} an hour")
    return None


def covering(home, plan: dict, now: float | None = None) -> tuple[str | None, list[str]]:
    """(the id of a mandate in force the plan fits and whose hour has room for all its changes, or None; why
    each mandate in force did not). Until a mandate has ever been made there is no head, and the Keychain is
    not asked."""
    now = time.time() if now is None else now
    if not (mandate_store.state_dir(STORE, home) / HEAD_FILE).is_file():
        return None, []
    secret = mandate_store.key(STORE, home)
    if secret is None:
        return None, []
    misses = []
    for m in mandate_store.active(STORE, home, now, key_of=lambda _home: secret):
        used = mandate_ledger.count(STORE, home, secret, LEDGER_KIND, m["id"], now, HOUR, USED_UP)
        why = fits(m, plan) or _hourly(m, used, weight(plan))
        if why is None:
            return m["id"], misses
        misses.append(f"{m['id']}: {why}")
    return None, misses


def use(home, mandate_id: str, plan: dict, now: float | None = None) -> str | None:
    """At the write: why the plan no longer fits ``mandate_id`` (nothing is counted), or None after its
    changes have been counted (one row each). The mandate is read again, the hour's count taken and the rows
    appended under the store's lock, which revoking and every other caller share: the last slots of an hour
    go to one."""
    now = time.time() if now is None else now
    changes = weight(plan)
    try:
        with mandate_store.locked(STORE, home):
            secret = mandate_store.key(STORE, home)
            if secret is None:
                return NO_KEY
            m = next((m for m in mandate_store.active(STORE, home, now, key_of=lambda _home: secret)
                      if m["id"] == mandate_id), None)
            if m is None:
                return f"mandate {mandate_id} is no longer in force"
            return mandate_ledger.take(STORE, home, secret, LEDGER_KIND, mandate_id, now, HOUR, USED_UP,
                                       lambda used: fits(m, plan) or _hourly(m, used, changes), weight=changes)
    except (OSError, MandateError) as exc:
        return f"the change could not be counted: {exc}"
