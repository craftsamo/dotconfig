"""Everyday entry point for AI session history: ``ai-history``.

    ai-history                      today's activity across OpenCode and Hermes
    ai-history --days 7             the last 7 local days (also: summary --days 7)
    ai-history opencode list --days 1
    ai-history hermes usage --days 7 --group-by profile,platform
    ai-history hermes get <session-id>
    ... --json                      the raw result instead of the table

Output is a short human table by default. The summary unions activity across
both tools, so an OpenCode run that Hermes was waiting on is counted once.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from datetime import datetime


HERE = Path(__file__).resolve().parent


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


common = _load("hermes_session_history_common", HERE / "common.py")
hermes = _load("hermes_session_history_hermes", HERE / "hermes.py")
opencode = _load("hermes_opencode_history", HERE.parent / "opencode" / "history.py")
READERS = {"opencode": opencode, "hermes": hermes}
NOTE = "Activity = time the agents were running (model output and tool execution), minus waits for a " \
       "person's answer. It is not human working time."


# --------------------------------------------------------------------------
# Summary across both tools


def summary(args, *, readers=None, runners=None):
    """Usage of both tools over one window, with cross-tool overlap removed."""
    readers = readers or READERS
    runners = runners or {}
    window = {k: args[k] for k in ("from", "to", "days", "timezone") if args.get(k) is not None}
    if not any(k in window for k in ("from", "to", "days")):
        window["days"] = 1
    groups = {"opencode": ["directory"], "hermes": ["profile"]}
    tz, label = common.zone(window.get("timezone"))
    lo_hi = common.window_view(*common.window(window, tz, required="summary"), label)   # validates first
    tools, intervals = {}, []
    for name, reader in readers.items():
        run = runners.get(name) or reader.run
        try:
            result = run({"action": "usage", **window, "group_by": groups[name]}, keep_intervals=True)
        except common.Unavailable as exc:  # one tool missing still leaves the other's answer
            tools[name] = {"error": str(exc)}
            continue
        intervals.extend(tuple(i) for i in result["totals"].pop("intervals_ms", []))
        tools[name] = result
    return {"action": "summary", "window": lo_hi, "status": "partial" if any(
                "error" in t or t.get("status") == "partial" for t in tools.values()) else "complete",
            "active_union_seconds": round(common.union_ms(intervals) / 1000, 1), "tools": tools}


# --------------------------------------------------------------------------
# Text rendering


def _dur(seconds):
    if not seconds:
        return "0m"
    minutes = seconds / 60
    return f"{minutes:.0f}m" if minutes < 60 else f"{minutes / 60:.1f}h"


def _count(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    return str(n)


def _local(iso_text, tz):
    if not iso_text:
        return "-"
    moment = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    moment = moment.astimezone(tz) if tz is not None else moment.astimezone()
    return moment.strftime("%m-%d %H:%M")


def _window_line(window):
    if not window:
        return "all time"
    tz, _ = common.zone(window["timezone"] if window["timezone"] != "local" else None)
    start = _local(window["from"], tz)[:5]
    end_ms = common.instant(window["to"], tz, "to") - 1
    end = _local(common.iso(end_ms), tz)[:5]
    span = start if start == end else f"{start} .. {end}"
    return f"{span} ({window['timezone']})"


def _short(value, width):
    value = "-" if value is None else str(value)
    return value if len(value) <= width else "…" + value[-(width - 1):]


def _key_text(key):
    parts = []
    for name, value in key.items():
        if name == "directory" and isinstance(value, str):
            value = value.replace(str(Path.home()), "~")
        parts.append("-" if value is None else str(value))
    return " / ".join(parts)


NUMERIC = re.compile(r"[\d.]+[mhkM]?\Z")


def _table(rows, headers):
    """Text columns left, numeric columns right."""
    widths = [max(len(str(r[i])) for r in [headers, *rows]) for i in range(len(headers))]
    numeric = [all(NUMERIC.match(str(r[i])) for r in rows) for i in range(len(headers))]
    def line(cells):
        return "  ".join(str(c).rjust(w) if n else str(c).ljust(w)
                         for c, w, n in zip(cells, widths, numeric)).rstrip()
    return [line(headers), *(line(r) for r in rows)]


def _diagnostics(result):
    lines = []
    for d in result.get("diagnostics", []):
        mark = "!" if d.get("partial") else "-"
        detail = d.get("detail") or d.get("effect", "")
        count = f" ×{d['count']}" if "count" in d else ""
        lines.append(f"  {mark} {d['code']}{count}: {detail}")
    return lines


def render_summary(result, top=5):
    lines = [f"AI activity {_window_line(result['window'])}  [{result['status']}]",
             f"Combined (overlap removed): {_dur(result['active_union_seconds'])}"]
    for name, tool in result["tools"].items():
        label = {"opencode": "OpenCode", "hermes": "Hermes"}[name]
        if "error" in tool:
            lines.append(f"{label}: unavailable ({tool['error']})")
            continue
        t = tool["totals"]
        waits = [f"question wait {_dur(t['question_wait_seconds'])}"] if t["question_wait_seconds"] else []
        if t.get("opencode_wait_seconds"):
            waits.append(f"waiting on OpenCode {_dur(t['opencode_wait_seconds'])}")
        lines.append(f"{label}: {_dur(t['active_union_seconds'])} active, {t['sessions']} sessions, "
                     f"{_count(t['tokens']['output'])} output tokens"
                     + (f" ({', '.join(waits)})" if waits else "") + f"  [{tool['status']}]")
        ranked = sorted(tool["groups"], key=lambda g: (-g["active_union_seconds"], -g["tokens"]["output"]))
        rows = [(_short(_key_text(g["key"]), 40), _dur(g["active_union_seconds"]), g["sessions"],
                 _count(g["tokens"]["output"])) for g in ranked[:top] if g["active_seconds"]
                or g["tokens"]["output"]]
        if rows:
            lines.extend("  " + line for line in _table(rows, ("", "active", "sess", "out")))
        lines.extend(_diagnostics(tool))
    lines.append(NOTE)
    return "\n".join(lines)


LABELS = {"opencode": "OpenCode", "hermes": "Hermes"}
GROUPED_BY = {"opencode": "Directory", "hermes": "Profile"}
PERIOD_COMMANDS = ("today", "week", "month")


def _cell(text):
    """A table cell as a code span: no Markdown inside names, and no pipe to break the row."""
    return "`" + str(text).replace("`", "'").replace("|", "/") + "`"


def _waits(t):
    parts = []
    if t.get("question_wait_seconds"):
        parts.append(f"waiting for your answer {_dur(t['question_wait_seconds'])}")
    if t.get("opencode_wait_seconds"):
        parts.append(f"waiting on OpenCode {_dur(t['opencode_wait_seconds'])}")
    if t.get("specialist_wait_seconds"):
        parts.append(f"waiting on another profile {_dur(t['specialist_wait_seconds'])}")
    return parts


def render_summary_rich(result, top=10):
    """Markdown for a chat that renders tables and <details> (Telegram rich messages):
    the combined figure, one table per tool, and each breakdown folded."""
    lines = [f"## AI activity · {_window_line(result['window'])}", "",
             f"**{_dur(result['active_union_seconds'])}** agents running, overlap removed"
             + ("" if result["status"] == "complete" else " · *partial*"), "",
             "| Tool | Active | Sessions | Output |", "| :--- | ---: | ---: | ---: |"]
    for name, tool in result["tools"].items():
        if "error" in tool:
            lines.append(f"| {LABELS[name]} | unavailable | | |")
            continue
        t = tool["totals"]
        lines.append(f"| {LABELS[name]} | {_dur(t['active_union_seconds'])} | {t['sessions']} | "
                     f"{_count(t['tokens']['output'])} |")
    notes = []
    for name, tool in result["tools"].items():
        if "error" in tool:
            notes.append(f"- {LABELS[name]} unavailable: {tool['error']}")
            continue
        ranked = sorted((g for g in tool["groups"] if g["active_seconds"] or g["tokens"]["output"]),
                        key=lambda g: (-g["active_union_seconds"], -g["tokens"]["output"]))
        if ranked:
            lines += ["", f"<details><summary>{LABELS[name]} by {GROUPED_BY[name].lower()}</summary>", "",
                      f"| {GROUPED_BY[name]} | Active | Sessions | Output |", "| :--- | ---: | ---: | ---: |"]
            lines += [f"| {_cell(_short(_key_text(g['key']), 40))} | {_dur(g['active_union_seconds'])} | "
                      f"{g['sessions']} | {_count(g['tokens']['output'])} |" for g in ranked[:top]]
            if len(ranked) > top:
                lines += ["", f"… {len(ranked) - top} more (`ai-history --days N`)"]
            waits = _waits(tool["totals"])
            if waits:
                lines += ["", "Not counted as active: " + ", ".join(waits)]
            lines += ["", "</details>"]
        for d in tool.get("diagnostics", []):
            count = f" ×{d['count']}" if "count" in d else ""
            notes.append(f"- {LABELS[name]}: `{d['code']}`{count}"
                         + (" (undercounts)" if d.get("partial") else ""))
    lines += ["", "<details><summary>How to read</summary>", "", f"- {NOTE}"]
    lines += notes
    lines += ["", "Other periods (tap to copy):", ""]
    lines += [f"`/activity {p}`" for p in PERIOD_COMMANDS] + ["`/activity 14`", "", "</details>"]
    return "\n".join(lines)


def render(tool, result, args):
    tz, _ = common.zone(args.get("timezone"))
    head = f"{tool} {result['action']}  source={result['source']}  [{result['status']}]"
    if result.get("window"):
        head += f"  {_window_line(result['window'])}"
    lines = [head]
    if result["action"] == "usage":
        t = result["totals"]
        lines.append(f"total: {_dur(t['active_union_seconds'])} active (sum {_dur(t['active_seconds'])}), "
                     f"question wait {_dur(t['question_wait_seconds'])}, {t['sessions']} sessions, "
                     f"{_count(t['tokens']['output'])} output tokens")
        rows = [(_short(_key_text(g["key"]), 48), _dur(g["active_union_seconds"]), g["sessions"],
                 _count(g["tokens"]["input"] + g["tokens"]["cache_read"]), _count(g["tokens"]["output"]))
                + ((f"{g['cost']:.2f}",) if "cost" in g else ())
                for g in sorted(result["groups"], key=lambda g: -g["active_union_seconds"])]
        headers = ("group", "active", "sess", "in+cache", "out") + (("cost",) if args.get("include_cost") else ())
        if rows:
            lines.extend(_table(rows, headers))
    else:
        sessions = [result["session"]] if "session" in result else result["sessions"]
        who = "profile" if tool == "hermes" else "agent"
        rows = []
        for s in sessions:
            when = _local(s.get("last_active") or s.get("updated"), tz)
            kind = s.get("platform") or ("child" if s.get("parent_id") else "root")
            row = [when, _short(s.get(who), 14), _short(kind, 9), _short((s.get("model") or "-").split("/")[-1], 18),
                   _short((s.get("directory") or "-").replace(str(Path.home()), "~"), 28),
                   _count(s["tokens"]["output"]), s["id"]]
            if "title" in s:
                row.append(_short(s["title"], 40))
            rows.append(row)
        headers = ["last", who, "kind", "model", "directory", "out", "id"] + (["title"] if args.get("include_title") else [])
        if rows:
            lines.extend(_table(rows, headers))
        if "total" in result:
            more = f", next --offset {result['next_offset']}" if result.get("next_offset") is not None else ""
            lines.append(f"{len(sessions)} of {result['total']}{more}")
        if result.get("session", {}).get("lineage"):
            lines.append("lineage: " + " → ".join(result["session"]["lineage"]))
    lines.extend(_diagnostics(result))
    if result["action"] == "usage":
        lines.append(NOTE)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line


def _window_args(parser):
    parser.add_argument("--days", type=int, help="last N local days ending today (default for summary: 1)")
    parser.add_argument("--today", action="store_true", help="same as --days 1")
    parser.add_argument("--from", dest="from_")
    parser.add_argument("--to")
    parser.add_argument("--timezone", help="IANA zone (default: system)")
    parser.add_argument("--json", action="store_true", help="print the raw JSON result")


def _parser():
    parser = argparse.ArgumentParser(prog="ai-history", description="AI session history (OpenCode, Hermes)",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = parser.add_subparsers(dest="tool")
    summary_parser = sub.add_parser("summary", help="activity of both tools (default)")
    _window_args(summary_parser)
    for tool in ("opencode", "hermes"):
        p = sub.add_parser(tool, help=f"{tool} sessions")
        p.add_argument("action", choices=READERS[tool].ACTIONS)
        p.add_argument("session_id", nargs="?")
        _window_args(p)
        for flag in ("directory", "kind", "model", "search", "source"):
            p.add_argument(f"--{flag}")
        if tool == "opencode":
            p.add_argument("--agent")
        else:
            p.add_argument("--profile", help="comma-separated profile names")
            p.add_argument("--platform", help="cli, telegram, cron, kanban, subagent, a2a, ...")
        p.add_argument("--group-by", help="comma-separated: " + ",".join(READERS[tool].GROUPS))
        p.add_argument("--limit", type=int)
        p.add_argument("--offset", type=int)
        for flag in ("archived", "include-title", "include-cost"):
            p.add_argument(f"--{flag}", action="store_true")
    return parser


def _request(ns):
    args = {}
    if getattr(ns, "action", None):
        args["action"] = ns.action
    if getattr(ns, "session_id", None):
        args["session_id"] = ns.session_id
    if ns.today:
        args["days"] = 1
    for key, attr in (("days", "days"), ("from", "from_"), ("to", "to"), ("timezone", "timezone")):
        if getattr(ns, attr, None) is not None:
            args[key] = getattr(ns, attr)
    for key in ("directory", "kind", "model", "search", "source", "agent", "platform", "limit", "offset"):
        if getattr(ns, key, None) is not None:
            args[key] = getattr(ns, key)
    if getattr(ns, "profile", None):
        names = [p.strip() for p in ns.profile.split(",") if p.strip()]
        args["profile"] = names[0] if len(names) == 1 else names
    if getattr(ns, "group_by", None):
        args["group_by"] = [g.strip() for g in ns.group_by.split(",") if g.strip()]
    for key in ("archived", "include_title", "include_cost"):
        if getattr(ns, key, False):
            args[key] = True
    return args


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv.insert(0, "summary")
    ns = _parser().parse_args(argv)
    args = _request(ns)
    try:
        if ns.tool == "summary":
            result = summary(args)
            text = render_summary(result)
        else:
            if args.get("action") == "usage" and not any(k in args for k in ("days", "from", "to")):
                args["days"] = 1
            result = READERS[ns.tool].run(args)
            text = render(ns.tool, result, args)
        code = 0
    except (ValueError, common.Unavailable) as exc:
        result, text, code = {"error": str(exc)}, f"error: {exc}", 1
    except Exception as exc:  # cron callers get a message, never a traceback
        result, text, code = ({"error": f"unexpected failure: {exc.__class__.__name__}"},
                              f"error: unexpected failure: {exc.__class__.__name__}", 1)
    if ns.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
