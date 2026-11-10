"""send_mandate: the service-independent half of a send mandate for Telegram and WhatsApp.

A send mandate is the user's standing approval for plain text sends to a few chats, made on a card of
its own. It belongs to one service and one signed-in account and names: one to five chats (each by its
id, with the name, kind and identity the card showed; never a bot or a broadcast channel), how many sends an hour
it allows (at most the service's own ceiling; where that is below MAX_PER_HOUR, WhatsApp's, it bounds the
account's total across its mandates in force), the longest text, a purpose in one line, and an end
at most MAX_DAYS out. A send fits only
when it is plain text to one of those chats from that account, within the length, with no file, no
quoted message and no reply, and the hour's count is not used up.

Here: the terms, the card, whether a send fits, the hourly count and making or ending a mandate
through the shared store (``plugins/_shared/mandate_store.py``) and ledger
(``plugins/_shared/mandate_ledger.py``). The hooks and tools of the plugins that use it are theirs.
State, in the profile home (never the repository; the plugin's guard blocks file and terminal access):

  <HERMES_HOME>/<state>/mandates/<id>.json   the terms, MAC'd (the store's)
  <HERMES_HOME>/<state>/head.json            the ids in force, MAC'd: only the head decides (the store's)
  <HERMES_HOME>/<state>/uses.jsonl           one MAC'd opening row per mandate, then one per counted send
                                             (the ledger's, MAC'd as ``<service>-send-use``)

``use`` is the write-time check and the count in one step, under the store's lock: a send is counted
before it goes out, whatever becomes of it. Without a readable MAC key no mandate is in force and
nothing is counted. The ledger fails closed: a mandate whose opening row is missing, and any ledger
that is not a plain file of this user (opened without following links), count as used up.

Shared by telegram-access and whatsapp-access (each loads this file by path as
``hermes_send_mandate``; it is not a plugin and has no manifest). Contract: docs/decisions/send-mandates.md.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


_PLUGINS_SHARED = Path(__file__).resolve().parents[2] / "_shared"
cards = _load("hermes_card", _PLUGINS_SHARED / "card.py")
mandate_store = _load("hermes_mandate_store", _PLUGINS_SHARED / "mandate_store.py")
mandate_ledger = _load("hermes_mandate_ledger", _PLUGINS_SHARED / "mandate_ledger.py")

MAX_CHATS = 5
MAX_PER_HOUR = 30   # the highest ceiling of any service, and what a ledger that cannot be vouched for counts as
MAX_CHARS = 1000
MAX_DAYS = 30
DAY = 86400
HOUR = 3600
PURPOSE_LIMIT = 200
IDENTITY_LIMIT = 80
ACCOUNT_LABEL_LIMIT = 120
HEAD_FILE = "head.json"   # the store's (plugins/_shared/mandate_store.py)

SERVICES = {
    "telegram": {"label": "Telegram", "state": "telegram-access", "scope": "telegram-access",
                 "key_prefix": "TELEGRAM_MANDATE_KEY_", "kinds": ("self", "user", "group", "supergroup"),
                 "max_per_hour": MAX_PER_HOUR},
    # An unofficial client: more automated sends raise the risk of the account being limited.
    "whatsapp": {"label": "WhatsApp", "state": "whatsapp-access", "scope": "whatsapp-access",
                 "key_prefix": "WHATSAPP_MANDATE_KEY_", "kinds": ("user", "group"), "max_per_hour": 5},
}
# A bot answers with someone else's logic and a channel reaches an audience the card cannot list.
REFUSED_KINDS = ("bot", "channel", "broadcast")

NAME_CLIPS = ((80, 120), (40, 60), (20, 30))   # (chat name, purpose): shortened before a bound is left out
EFFECT = (cards.DANGER, "Plain text sends to these chats skip the card")
NO_KEY = "no mandate key is readable: nothing is in force"
LEDGER_USED_UP = "its send count cannot be read (the ledger is missing or was changed); it counts as used up"


# The hour's count of a ledger that cannot be vouched for: it equals MAX_PER_HOUR, so every mandate reads as
# used up, and ``fits`` can still tell it from a real count that reached the same number.
_UsedUp = mandate_ledger.UsedUp
USED_UP = _UsedUp(MAX_PER_HOUR)


class MandateError(ValueError):
    """The terms are not acceptable, or the mandate could not be kept."""


def _service(service) -> dict:
    if not isinstance(service, str) or service not in SERVICES:
        raise MandateError(f"service is one of: {', '.join(SERVICES)}")
    return SERVICES[service]


def store(service: str):
    """The ``mandate_store.Store`` of the service's send mandates."""
    spec = _service(service)
    return mandate_store.Store(state=spec["state"], key_prefix=spec["key_prefix"], scope=spec["scope"],
                               mac_kind=f"{service}-send-mandate", key_note=f"{spec['state']} send mandate MAC key",
                               error=MandateError, max_days=MAX_DAYS)


# --- terms ----------------------------------------------------------------------------------------

def _whole(value, name: str, low: int, high: int, note: str = "") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise MandateError(f"{name} is a whole number from {low} to {high}{note}")
    return value


def _one_line(value, what: str, limit: int) -> str:
    """``value`` as one line of at most ``limit`` characters; refused when it is not a non-empty string
    or too long (never clipped: a handle that is cut no longer names the chat)."""
    if not isinstance(value, str) or not value.strip():
        raise MandateError(f"{what} (a non-empty string)")
    text = " ".join(value.split())
    if len(text) > limit:
        raise MandateError(f"{what} (at most {limit} characters)")
    return text


def _chat(service: str, chat) -> dict:
    kinds = SERVICES[service]["kinds"]
    if not isinstance(chat, dict):
        raise MandateError("each chat is {id, name, kind, identity}")
    chat_id, kind = chat.get("id"), chat.get("kind")
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise MandateError("each chat has an id (a non-empty string)")
    chat_id = chat_id.strip()
    name = " ".join(str(chat.get("name") or "").split()) or chat_id
    if kind in REFUSED_KINDS:
        raise MandateError(f"{name} is a {kind}: a mandate never covers bots or broadcast channels")
    if kind not in kinds:
        raise MandateError(f"the kind of {name} is one of: {', '.join(kinds)}")
    # The name is the other person's choice; the identity is the handle the plugin's send card shows.
    identity = _one_line(chat.get("identity"), "each chat has an identity, the handle its send card shows",
                         IDENTITY_LIMIT)
    return {"id": chat_id, "name": name, "kind": kind, "identity": identity}


def terms(service: str, account: str, chats: list, per_hour: int, max_chars: int, days: int, purpose: str,
          now: float | None = None, account_label: str | None = None) -> dict:
    """The terms of a new mandate, checked. The end is fixed now, when the card is drawn, so what is
    stored ends when the card said. ``account_label`` is the account as the plugin's send card names it
    (the card shows it in place of ``account``, the id the sends are matched on)."""
    spec = _service(service)
    if not isinstance(account, str) or not account.strip():
        raise MandateError("account names the signed-in account the mandate covers")
    if account_label is not None:
        account_label = _one_line(account_label, "account_label is the account as its send card names it",
                                  ACCOUNT_LABEL_LIMIT)
    if not isinstance(chats, (list, tuple)) or not 1 <= len(chats) <= MAX_CHATS:
        raise MandateError(f"chats is a list of one to {MAX_CHATS} chats")
    named = [_chat(service, chat) for chat in chats]
    if len({c["id"] for c in named}) != len(named):
        raise MandateError("each chat is named once")
    ceiling = spec["max_per_hour"]
    note = "" if ceiling == MAX_PER_HOUR else f" ({spec['label']} allows at most {ceiling} sends an hour)"
    per_hour = _whole(per_hour, "per_hour", 1, ceiling, note)
    max_chars = _whole(max_chars, "max_chars", 1, MAX_CHARS)
    days = _whole(days, "days", 1, MAX_DAYS)
    purpose = " ".join(str(purpose or "").split())
    if not purpose:
        raise MandateError("purpose says what the mandate is for (one line)")
    if len(purpose) > PURPOSE_LIMIT:
        raise MandateError(f"purpose is at most {PURPOSE_LIMIT} characters")
    now = time.time() if now is None else now
    return {"service": service, "account": account.strip(), "account_label": account_label, "chats": named,
            "per_hour": per_hour, "max_chars": max_chars, "days": days, "expires": int(now) + days * DAY,
            "purpose": purpose}


def same_terms(a: dict, b: dict) -> bool:
    """Whether two readings of a create call agree on everything but the end (fixed at the card)."""
    return {k: v for k, v in a.items() if k != "expires"} == {k: v for k, v in b.items() if k != "expires"}


def card(t: dict, say) -> str:
    """The shared card shape (plugins/_shared/card.py) with every bound of the mandate on it: the
    rules every mandate shares go first, then the names and the purpose shrink until it fits, and a
    mandate whose card still does not fit is refused. ``say(text, limit)`` clips someone's words. A chat
    is named by its identity as well, whole: the name is the other person's choice, so only it shrinks."""
    label = _service(t["service"])["label"]
    end = time.strftime("%Y-%m-%d %H:%M", time.localtime(t["expires"]))
    for name_clip, purpose_clip in NAME_CLIPS:
        facts = [("Chat", f"{say(c['name'], name_clip)} ({c['kind']}, {cards.line(c['identity'], IDENTITY_LIMIT)})")
                 for c in t["chats"]]
        facts += [("Account", t.get("account_label") or t["account"]),
                  ("Up to", f"{t['per_hour']} an hour, {t['max_chars']} characters each"),
                  ("Until", f"{end} ({t['days']} day{'s' if t['days'] != 1 else ''})"),
                  ("Purpose", say(t["purpose"], purpose_clip))]
        # The same for every mandate, so it gives way before any bound the user chose.
        never = [("Never covered", "files, quotes, replies, other chats or accounts, and channels")]
        try:
            return cards.compose(label, "Send mandate", EFFECT, facts, context=never)
        except cards.CardError:
            continue
    raise MandateError("the mandate's card cannot show all its bounds; name fewer chats (a Discord chat shows a "
                       "shorter card than Telegram)")


# --- what is in force -----------------------------------------------------------------------------

def active(home, service: str, now: float | None = None) -> list[dict]:
    """The mandates in force: in the authenticated head, authenticated themselves, not ended."""
    return mandate_store.active(store(service), home, now)


class AccountCeilingError(MandateError):
    """The terms would take their account past the service's hourly ceiling."""


def account_ceiling_refusal(t: dict, in_force: list[dict]) -> str | None:
    """Why ``t`` would take its account past the service's hourly ceiling given ``in_force`` (the mandates
    in force for the service), or None. A service whose ceiling is below MAX_PER_HOUR (WhatsApp) bounds the
    account, not each mandate: the ``per_hour`` of every mandate in force for the same account counts."""
    spec = _service(t["service"])
    ceiling = spec["max_per_hour"]
    if ceiling >= MAX_PER_HOUR:
        return None
    taken = sum(m["per_hour"] for m in in_force if m.get("account") == t["account"])
    if taken + t["per_hour"] > ceiling:
        return (f"{spec['label']} allows at most {ceiling} sends an hour per account; mandates in force for "
                f"{t['account']} already take {taken}")
    return None


def check_account_ceiling(home, t: dict) -> None:
    """Raise AccountCeilingError when ``t`` would exceed the service's per-account ceiling (a look before
    the card; the check in ``create``, under the store's lock, is the one that counts)."""
    why = account_ceiling_refusal(t, active(home, t["service"]))
    if why:
        raise AccountCeilingError(why)


def create(home, t: dict) -> dict:
    """Make the mandate the card showed; returns its ``summary``. Its opening row goes into the ledger
    right after, in the same locked step that holds the per-account ceiling (``account_ceiling_refusal``)
    against the other mandates in force: a mandate whose opening row is missing counts as used up, so one
    that cannot be anchored, or would break the ceiling, is revoked and nothing is made."""
    service = t["service"]
    kept = store(service)
    fields = {k: t[k] for k in ("service", "account", "account_label", "chats", "per_hour", "max_chars",
                                "purpose")}
    body = mandate_store.create(kept, home, fields, t["expires"])
    try:
        with mandate_store.locked(kept, home):
            secret = mandate_store.key(kept, home)
            if secret is None:
                raise MandateError(NO_KEY)
            others = [m for m in mandate_store.active(kept, home, key_of=lambda _home: secret)
                      if m["id"] != body["id"]]
            why = account_ceiling_refusal(t, others)
            if why:
                raise AccountCeilingError(why)
            mandate_ledger.anchor(kept, home, secret, _use_kind(service), body["id"], body["created"],
                                  write=lambda row: _append(home, service, row))
    except (OSError, MandateError) as exc:
        revoked = True
        try:
            mandate_store.revoke(kept, home, body["id"])
            ended = "it was revoked"
        except (OSError, MandateError) as revoke_exc:
            revoked = False
            ended = f"it could not be revoked ({revoke_exc}); revoke {body['id']}"
        if isinstance(exc, AccountCeilingError):
            raise MandateError(f"{exc}; nothing was made" + ("" if revoked else f", {ended}")) from exc
        raise MandateError(f"the mandate could not be recorded in its ledger ({exc}); nothing was made, "
                           f"{ended}") from exc
    return summary(body)


def revoke(home, service: str, mandate_id: str) -> dict:
    """Take a mandate out of force at once; needs no card."""
    return mandate_store.revoke(store(service), home, mandate_id)


def summary(body: dict) -> dict:
    return {"id": body["id"], "until": time.strftime("%Y-%m-%d %H:%M", time.localtime(body["expires"])),
            "chats": [f"{c['name']} ({c['identity']})" if c.get("identity") else c["name"] for c in body["chats"]],
            "per_hour": body["per_hour"],
            "max_chars": body["max_chars"], "purpose": body["purpose"], "service": body["service"]}


# --- the hourly ledger ----------------------------------------------------------------------------

def _use_kind(service: str) -> str:
    """What the service's ledger rows are MAC'd as."""
    return f"{service}-send-use"


def _used(home, service: str, mandate_id: str, now: float, secret: bytes | None = None) -> int:
    """How many counted sends of the mandate lie in the hour before ``now``; everything that cannot be
    vouched for counts as used up (USED_UP, which equals MAX_PER_HOUR), as the ledger decides
    (``secret`` is read afresh when not given)."""
    kept = store(service)
    secret = mandate_store.key(kept, home) if secret is None else secret
    return mandate_ledger.count(kept, home, secret, _use_kind(service), mandate_id, now, HOUR, USED_UP)


def _append(home, service: str, row: dict) -> None:
    """One row at the end of the service's ledger (the ledger's ``append``)."""
    mandate_ledger.append(store(service), home, row)


# --- does a send fit ------------------------------------------------------------------------------

def fits(m: dict, view: dict, used: int = 0) -> str | None:
    """Why the send does not fit mandate ``m``, or None when it does. ``view`` is the send as the
    service sees it: {service, account, chat, text, files (a count or a list), reply (truthy when it
    quotes or replies)}; ``used`` is how many covered sends the last hour already holds."""
    if view.get("service") != m["service"]:
        return f"the mandate is for {m['service']}, not {view.get('service')}"
    account = view.get("account")
    if account is None or str(account) != m["account"]:
        return "the mandate is for another account"
    chat = view.get("chat")
    if chat is None or str(chat) not in {c["id"] for c in m["chats"]}:
        return "the chat is not one the mandate names"
    if view.get("files"):
        return "a file always asks on a card"
    if view.get("reply"):
        return "a quote or a reply always asks on a card"
    text = view.get("text")
    if not isinstance(text, str) or not text.strip():
        return "the text is empty"
    if len(text) > m["max_chars"]:
        return f"the text is {len(text)} characters; the mandate allows {m['max_chars']}"
    if used >= m["per_hour"]:
        if isinstance(used, _UsedUp):
            return LEDGER_USED_UP
        return f"{used} sends in the last hour; the mandate allows {m['per_hour']} an hour"
    return None


def covering(home, service: str, view: dict, now: float | None = None) -> tuple[str | None, list[str]]:
    """(the id of a mandate in force the send fits, or None; why each mandate in force did not). A
    service that never made a mandate has no head, and the Keychain is not asked."""
    now = time.time() if now is None else now
    if not (mandate_store.state_dir(store(service), home) / HEAD_FILE).is_file():
        return None, []
    secret = mandate_store.key(store(service), home)
    if secret is None:
        return None, []
    misses = []
    for m in mandate_store.active(store(service), home, now, key_of=lambda _home: secret):
        why = fits(m, view, used=_used(home, service, m["id"], now, secret))
        if why is None:
            return m["id"], misses
        misses.append(f"{m['id']}: {why}")
    return None, misses


def use(home, service: str, mandate_id: str, view: dict, now: float | None = None) -> str | None:
    """At the write: why the send no longer fits ``mandate_id`` (nothing is counted), or None after it
    has been counted. The mandate is read again, the hour's count taken and the row appended under the
    store's lock, which revoking and every other caller share: the last slot of an hour goes to one."""
    now = time.time() if now is None else now
    try:
        kept = store(service)
        with mandate_store.locked(kept, home):
            secret = mandate_store.key(kept, home)
            if secret is None:
                return NO_KEY
            m = next((m for m in mandate_store.active(kept, home, now, key_of=lambda _home: secret)
                      if m["id"] == mandate_id), None)
            if m is None:
                return f"mandate {mandate_id} is no longer in force"
            return mandate_ledger.take(kept, home, secret, _use_kind(service), mandate_id, now, HOUR, USED_UP,
                                       lambda used: fits(m, view, used=used),
                                       write=lambda row: _append(home, service, row))
    except (OSError, MandateError) as exc:
        return f"the send could not be counted: {exc}"
