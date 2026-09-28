"""Shared contract for the session-history readers (OpenCode, Hermes).

Each reader owns its own sources and its own notion of what a session is. This
module owns only what must mean the same thing in both: request parsing
(half-open windows, timezones, opt-in fields), interval arithmetic for
activity, and the result envelope (source, complete/partial, diagnostics).

Stdlib only: readers run as CLIs from cron as well as inside Hermes.
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta, timezone
import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class Unavailable(Exception):
    """A source cannot answer; auto mode may fall back and must disclose it."""


# --------------------------------------------------------------------------
# Request parsing


def local_zone():
    """The system zone as an IANA zone when resolvable (DST-correct), else None."""
    candidates = [os.environ.get("TZ", "").lstrip(":")]
    try:
        target = os.path.realpath("/etc/localtime")
        if "/zoneinfo/" in target:
            candidates.append(target.split("/zoneinfo/", 1)[1])
    except OSError:
        pass
    for name in candidates:
        if name:
            try:
                return ZoneInfo(name), name
            except (ZoneInfoNotFoundError, ValueError):
                continue
    return None, "local"


def zone(name):
    """Return (tzinfo or None for the process's local rules, label)."""
    if name is None:
        return local_zone()
    if not isinstance(name, str):
        raise ValueError("timezone must be an IANA name such as Asia/Tokyo")
    try:
        return ZoneInfo(name), name
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone {name!r}") from None


def instant(value, tz, name):
    """YYYY-MM-DD (local midnight in tz) or ISO 8601 -> epoch milliseconds."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be YYYY-MM-DD or an ISO 8601 datetime")
    try:
        if DATE.fullmatch(value):
            moment = datetime.combine(date.fromisoformat(value), dtime())
        else:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            # tz None: naive astimezone() applies the local rules for that date.
            moment = moment.replace(tzinfo=tz) if tz is not None else moment.astimezone()
    except ValueError:
        raise ValueError(f"{name} must be YYYY-MM-DD or an ISO 8601 datetime") from None
    return int(moment.timestamp() * 1000)


def iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_day(ms, tz):
    moment = datetime.fromtimestamp(ms / 1000, tz) if tz is not None else datetime.fromtimestamp(ms / 1000)
    return moment.date().isoformat()


def flag(args, key, default=False):
    value = args.get(key, default)
    if type(value) is not bool:
        raise ValueError(f"{key} must be boolean")
    return value


def integer(args, key, default, low, high):
    value = args.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer in {low}..{high}")
    return value


def text(args, key):
    value = args.get(key)
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 512):
        raise ValueError(f"{key} must be a nonempty string")
    return value


def directory(args, key="directory"):
    value = text(args, key)
    if value is None:
        return None
    value = os.path.normpath(os.path.expanduser(value))
    if not os.path.isabs(value):
        raise ValueError(f"{key} must be an absolute path")
    return value


def under(path, prefix):
    if not isinstance(path, str):
        return False
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


MAX_DAYS = 366


def today(tz):
    now = datetime.now(tz) if tz is not None else datetime.now()
    return now.date()


def window(args, tz, *, required):
    """Return (from_ms, to_ms) for a half-open [from, to) window.

    ``days`` is the everyday shorthand: the last N local calendar days ending
    with today, i.e. [today-(N-1) 00:00, tomorrow 00:00)."""
    if args.get("days") is not None:
        if args.get("from") is not None or args.get("to") is not None:
            raise ValueError("days cannot be combined with from/to")
        days = integer(args, "days", 1, 1, MAX_DAYS)
        end = today(tz) + timedelta(days=1)
        start = end - timedelta(days=days)
        return instant(start.isoformat(), tz, "from"), instant(end.isoformat(), tz, "to")
    lo = instant(args["from"], tz, "from") if args.get("from") is not None else None
    hi = instant(args["to"], tz, "to") if args.get("to") is not None else None
    if required and (lo is None or hi is None):
        raise ValueError(f"{required} requires days, or both from and to")
    if lo is not None and hi is not None and lo >= hi:
        raise ValueError("from must be earlier than to")
    return lo, hi


def group_by(args, groups, default):
    value = args.get("group_by", default)
    if (not isinstance(value, list) or not value or len(set(value)) != len(value)
            or any(g not in groups for g in value)):
        raise ValueError("group_by must be a nonempty list drawn from " + ", ".join(groups))
    return value


# --------------------------------------------------------------------------
# Activity intervals (milliseconds)


def union_ms(intervals):
    """Length of the union of [start, stop) intervals."""
    total, end = 0, None
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += stop - start
            end = stop
        elif stop > end:
            total += stop - end
            end = stop
    return total


def subtract(interval, waits):
    """Split one interval around sorted waits inside it; return (pieces, waited_ms)."""
    begin, stop = interval
    pieces, waited, cursor = [], 0, begin
    for w_begin, w_end in waits:
        if w_end <= cursor or w_begin >= stop:
            continue
        cut_begin, cut_end = max(w_begin, cursor), min(w_end, stop)
        if cut_begin > cursor:
            pieces.append((cursor, cut_begin))
        waited += cut_end - cut_begin
        cursor = cut_end
    if cursor < stop:
        pieces.append((cursor, stop))
    return pieces, waited


def merged(intervals):
    """Sorted, non-overlapping intervals; the compact form handed to a cross-tool union."""
    out = []
    for start, stop in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], stop)
        else:
            out.append([start, stop])
    return out


def clip(begin, stop, lo, hi):
    """The part of [begin, stop) inside [lo, hi), or None."""
    begin, stop = max(begin, lo), min(stop, hi)
    return (begin, stop) if stop > begin else None


# --------------------------------------------------------------------------
# Result envelope


def window_view(lo, hi, label):
    if lo is None and hi is None:
        return None
    return {"from": iso(lo), "to": iso(hi), "timezone": label}


def envelope(action, window_body, source, diagnostics, body, **identity):
    """Every answer states where it came from and whether it is complete.

    A diagnostic marked ``partial`` means a figure is missing or undercounted;
    one without it only explains how the answer was produced."""
    partial = any(d.get("partial") for d in diagnostics)
    return {"action": action, "window": window_body, "source": source, **identity,
            "status": "partial" if partial else "complete", "diagnostics": diagnostics, **body}
