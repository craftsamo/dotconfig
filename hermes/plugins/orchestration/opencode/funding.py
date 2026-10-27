"""Where a Claude (or other) request can be served from, and how much each stop holds:
the service's providers, and the usage windows and credit lanes OpenCode Quota exports.

Read-only. The export is Quota's own public file, rewritten while the Quota footer
refreshes in an open TUI, so it can be old; a reading is reported with its age and
whether it is fresh, never fetched. Connection ids in the export are never returned.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re

# Quota's five-minute cache plus export-refresh grace; the same rule the OpenCode
# preflight plugin applies (opencode/README.md "Subscription preflight").
FRESH_SECONDS = 360
EXPORT_LIMIT = 1 << 20
WINDOWS = ("5h", "Weekly")
# `[Claude Sub OAuth] (active) 5h`, `[OpenAI] (Plus) Weekly`: the label, whether this is
# the active login, the plan, then the window.
ENTRY_NAME = re.compile(r"\[(?P<label>[^\]]+)\]\s*(?P<active>\(active\))?\s*(?:\((?P<plan>[^)]+)\))?\s*(?P<rest>.*)\Z")


def export_path():
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "opencode" / "quota-export.json"


def read_export(path=None):
    """The export, or None with a reason."""
    path = Path(path) if path else export_path()
    try:
        if path.stat().st_size > EXPORT_LIMIT:
            return None, f"{path} is larger than {EXPORT_LIMIT} bytes"
        body = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"no Quota export at {path}; it is written while the Quota footer refreshes in an open TUI"
    except (OSError, ValueError) as exc:
        return None, f"{path} could not be read ({exc.__class__.__name__})"
    if not isinstance(body, dict) or not isinstance(body.get("providers"), dict):
        return None, f"{path} is not a Quota export"
    return body, None


def _when(stamp):
    if type(stamp) is not int or stamp <= 0:
        return None
    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat(timespec="seconds")


def _percent(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _window(entry, now):
    """One usage window: what remains, when it resets, and whether it is empty. A window
    at 0% whose reset lies ahead is empty at any age of the reading; one whose reset has
    passed says nothing about now."""
    remaining, reset = _percent(entry.get("percentRemaining")), entry.get("resetAt")
    out = {"remaining_percent": remaining}
    if _when(reset):
        out["resets"] = _when(reset)
    if type(reset) is int and reset <= now:
        out["past_reset"] = True
    elif remaining is not None and remaining <= 0:
        out["empty"] = True
    return out


def _fresh(fetched, now, empty):
    """Whether a reading can be acted on: an empty one holds until its reset; any other
    needs its provider's fetch within FRESH_SECONDS."""
    return bool(empty or (fetched and now - fetched <= FRESH_SECONDS))


def _accounts(provider, now):
    """The entries of one provider grouped by account (the bracketed label); Claude
    exports one group per saved login, the active one marked."""
    groups = {}
    for entry in provider.get("entries") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        match = ENTRY_NAME.match(entry["name"])
        if not match:
            continue
        label, rest = match.group("label"), match.group("rest").strip()
        group = groups.setdefault(label, {"label": label, "windows": {}})
        if match.group("active"):
            group["active"] = True
        if match.group("plan"):
            group["plan"] = match.group("plan")
        window = _window(entry, now)
        if rest in WINDOWS:
            group["windows"][rest] = window
        elif rest:
            group.setdefault("other", {})[rest] = window
    out = []
    for group in groups.values():
        if any(w.get("empty") for w in group["windows"].values()):
            group["empty"] = True
        out.append(group)
    return out


def _lanes(provider, now):
    """The credit lanes, one per source: the balance estimate (as the percent of the
    grants that still hold something), the nearest expiry, and the pace figures."""
    lanes = {}
    for entry in provider.get("entries") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("sourceId"), str):
            continue
        lane = lanes.setdefault(entry["sourceId"], {"provider": entry["sourceId"], "kind": "credit-lane"})
        name = str(entry.get("name") or "")
        if entry.get("resultType") == "budget":
            lane["balance"] = _window(entry, now)
            if lane["balance"].get("resets"):
                lane["balance"]["expires"] = lane["balance"].pop("resets")
            if lane["balance"].get("empty"):
                lane["empty"] = True
        elif entry.get("renderType") == "value" and isinstance(entry.get("value"), str):
            lane.setdefault("figures", {})[name.rsplit(" ", 1)[-1]] = entry["value"]
    return list(lanes.values())


def _now():
    return int(dt.datetime.now(dt.timezone.utc).timestamp())


def board(export, now=None):
    """The stops a request can be served from, as the export shows them: each provider
    with a reading, its accounts and windows, and the credit lanes; `fresh` says whether
    a non-empty reading is recent enough to act on."""
    now = int(now if now is not None else _now())
    exported = export.get("exportedAt") if type(export.get("exportedAt")) is int else None
    out = {"exported": _when(exported), "stops": []}
    if exported:
        out["export_age_seconds"] = max(0, now - exported)
    for name, provider in sorted(export["providers"].items()):
        # A partial reading still holds complete rows for the accounts it covers.
        if not isinstance(provider, dict) or provider.get("status") not in ("ok", "partial"):
            continue
        fetched = provider.get("fetchedAt") if type(provider.get("fetchedAt")) is int else None
        if name == "quota-providers":
            for lane in _lanes(provider, now):
                lane.update(fetched=_when(fetched), fresh=_fresh(fetched, now, lane.get("empty")))
                out["stops"].append(lane)
            continue
        accounts = _accounts(provider, now)
        if not accounts:
            continue
        for account in accounts:
            account["fresh"] = _fresh(fetched, now, account.get("empty"))
        out["stops"].append({"provider": name, "kind": "subscription", "fetched": _when(fetched),
                             "accounts": accounts})
    out["note"] = ("Quota's export, not a live reading: a window at 0% with its reset ahead holds at any age; "
                   "any other reading is fresh only within six minutes of its fetch, and one past its reset says "
                   "nothing. OpenCode moves a session between stops of the same model itself when one refuses; "
                   "pass model= only to choose a different model.")
    return out


def providers(body):
    """`/api/provider`: each provider's id, name, activation, and the provider it is a
    stop of (`canonical`) when it is one."""
    items = body.get("data") if isinstance(body, dict) else body
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        entry = {"id": item["id"]}
        for key in ("name", "activation", "canonical"):
            if isinstance(item.get(key), str):
                entry[key] = item[key]
        out.append(entry)
    return sorted(out, key=lambda p: p["id"])
