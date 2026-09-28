"""List the drafts under ~/Workspaces: every job directory below an ``.agent/``.

    ws-drafts                       per-Group summary (counts, size, flags)
    ws-drafts list                  every draft, most idle first
    ws-drafts list --group Acme --stale
    ws-drafts list --legacy         only the earlier layout still to clean up
    ... --json                      the raw result instead of the table

The layout rule lives in ~/Workspaces/AGENTS.md "Drafts": a job is one
directory ``.agent/<YYYYMMDD>-<job>/`` in its owning Group, or in the root
``~/Workspaces/.agent/`` when no single Group owns it. A draft that remains is
work not yet promoted, so this list is also the list of open work.

Read-only and metadata-only: names, sizes, file counts and modification times.
It never opens a file, never follows a symlink and never moves or deletes
anything. Stdlib only, so cron, the ``ws-drafts`` launcher and the Hermes tool
run the same code.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import stat
import sys


ACTIONS = ("summary", "list")
LAYOUTS = ("current", "legacy", "all")
FLAGS = ("stale", "misnamed", "legacy")
SORTS = ("idle", "size", "name", "started")
AREAS = ("Projects", "Personal")
LEGACY_ROOT = (".scratch", ".deliverables", ".notes")
LEGACY_GROUP = ("scratch", "deliverables", "notes")
IGNORED = {"AGENTS.md", ".DS_Store"}
NAME = re.compile(r"(\d{8})-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
UNASSIGNED = "(unassigned)"
DEFAULT_STALE_DAYS = 14
MAX_LIMIT = 1000


def default_root():
    return Path(os.environ.get("WORKSPACES_ROOT") or Path.home() / "Workspaces")


def started_on(name):
    """The job's start date from its name, or None when the name breaks the rule."""
    match = NAME.fullmatch(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Scanning


def _measure(path, diagnostics):
    """(bytes, files, newest mtime) of one job, never following a symlink."""
    try:
        info = path.lstat()
    except OSError as exc:
        diagnostics.append({"code": "unreadable", "path": str(path), "detail": exc.strerror, "partial": True})
        return 0, 0, None
    if not stat.S_ISDIR(info.st_mode):
        return info.st_size, 1, info.st_mtime
    # Idle time follows file changes; a directory's own mtime counts only when it
    # holds no file at all (an empty job is as old as its last entry change).
    size, files, newest, own = 0, 0, None, info.st_mtime
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            diagnostics.append({"code": "unreadable", "path": str(current), "detail": exc.strerror,
                                "partial": True})
            continue
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISDIR(info.st_mode):
                stack.append(Path(entry.path))
            else:
                size += info.st_size
                files += 1
                newest = info.st_mtime if newest is None else max(newest, info.st_mtime)
    return size, files, own if newest is None else newest


def _jobs(parent):
    """Immediate entries of a draft area, minus the area's own guide files."""
    try:
        return sorted((p for p in parent.iterdir() if p.name not in IGNORED), key=lambda p: p.name)
    except FileNotFoundError:
        return []


def _areas(root):
    """Yield (group, layout, area path) for every place a draft may sit."""
    yield UNASSIGNED, "current", root / ".agent"
    for name in LEGACY_ROOT:
        yield UNASSIGNED, "legacy", root / name
    for area in AREAS:
        for group in sorted(p for p in _jobs(root / area)
                            if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")):
            yield f"{area}/{group.name}", "current", group / ".agent"


def scan(root=None, *, today=None, stale_days=DEFAULT_STALE_DAYS):
    """Every draft as a dict, plus diagnostics. Nothing is read beyond metadata."""
    root = Path(root) if root is not None else default_root()
    today = today or date.today()
    drafts, diagnostics = [], []
    if not root.is_dir():
        raise FileNotFoundError(f"no Workspaces root at {root}")
    for group, layout, area in _areas(root):
        for path in _jobs(area):
            kind = layout
            if layout == "current" and path.name in LEGACY_GROUP and path.is_dir() and not path.is_symlink():
                for job in _jobs(path):     # earlier in-Group layout: .agent/{scratch,deliverables,notes}/
                    drafts.append(_draft(root, group, "legacy", path.name, job, today, stale_days, diagnostics))
                continue
            drafts.append(_draft(root, group, kind, area.name if kind == "legacy" else None, path,
                                 today, stale_days, diagnostics))
    return drafts, diagnostics


def _draft(root, group, layout, legacy_area, path, today, stale_days, diagnostics):
    size, files, newest = _measure(path, diagnostics)
    started = started_on(path.name) if layout == "current" else None
    modified = datetime.fromtimestamp(newest).date() if newest is not None else None
    flags = []
    if layout == "legacy":
        flags.append("legacy")
    elif started is None:
        flags.append("misnamed")
    idle = (today - modified).days if modified else None
    if idle is not None and idle >= stale_days:
        flags.append("stale")
    return {
        "group": group, "name": path.name, "path": str(path),
        "relative": str(path.relative_to(root)), "layout": layout, "legacy_area": legacy_area,
        "kind": "file" if path.is_file() or path.is_symlink() else "directory",
        "started": started.isoformat() if started else None,
        "age_days": (today - started).days if started else None,
        "last_modified": modified.isoformat() if modified else None, "idle_days": idle,
        "bytes": size, "files": files, "flags": flags,
    }


# --------------------------------------------------------------------------
# Requests


def _choice(args, key, allowed, default):
    value = args.get(key, default)
    if value not in allowed:
        raise ValueError(f"{key} must be one of " + ", ".join(allowed))
    return value


def _integer(args, key, default, low, high):
    value = args.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer in {low}..{high}")
    return value


def _flags(args):
    value = args.get("flags", [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(v not in FLAGS for v in value):
        raise ValueError("flags must be a list drawn from " + ", ".join(FLAGS))
    return value


class UnknownGroup(ValueError):
    """No Group matches; carries the names a caller can offer instead."""

    def __init__(self, needle, groups):
        self.needle, self.groups = needle, groups
        super().__init__(f"no Group matches {needle!r}; Groups: " + ", ".join(label(g) for g in groups))


def label(group):
    return "root" if group == UNASSIGNED else group.partition("/")[2]


def known_groups(root=None):
    """Every place a draft may sit, as Group keys: the root first, then each Group directory."""
    root = Path(root) if root is not None else default_root()
    return list(dict.fromkeys(g for g, _layout, _area in _areas(root)))


def resolve_group(needle, groups):
    """Group keys for a typed name, forgiving: exact name, then prefix, then substring,
    all case-insensitive. ``root`` (or ``(unassigned)``) is the Workspace root."""
    text = needle.strip().lower()
    if text in ("root", UNASSIGNED):
        return [UNASSIGNED]
    names = {g: (g.lower(), label(g).lower()) for g in groups if g != UNASSIGNED}
    for test in (lambda full, name: text in (full, name),
                 lambda full, name: name.startswith(text),
                 lambda full, name: text in name):
        found = [g for g, (full, name) in names.items() if test(full, name)]
        if found:
            return found
    raise UnknownGroup(needle, groups)


def run(args, *, root=None, today=None):
    """Tool/CLI entry: summary or list. Every result states source, status and diagnostics."""
    action = _choice(args, "action", ACTIONS, "summary")
    layout = _choice(args, "layout", LAYOUTS, "all")
    stale_days = _integer(args, "stale_days", DEFAULT_STALE_DAYS, 1, 3650)
    group = args.get("group")
    if group is not None and (not isinstance(group, str) or not group.strip()):
        raise ValueError("group must be a nonempty string")
    wanted = _flags(args)
    drafts, diagnostics = scan(root, today=today, stale_days=stale_days)
    if group:
        chosen = resolve_group(group, known_groups(root))
        drafts = [d for d in drafts if d["group"] in chosen]
    if layout != "all":
        drafts = [d for d in drafts if d["layout"] == layout]
    if wanted:
        drafts = [d for d in drafts if all(f in d["flags"] for f in wanted)]
    body = {"action": action, "root": str(Path(root) if root is not None else default_root()),
            "source": "filesystem", "stale_days": stale_days,
            "status": "partial" if any(d.get("partial") for d in diagnostics) else "complete",
            "diagnostics": diagnostics, "totals": _totals(drafts)}
    if action == "summary":
        body["groups"] = _groups(drafts)
        return body
    sort = _choice(args, "sort", SORTS, "idle")
    limit = _integer(args, "limit", 200, 1, MAX_LIMIT)
    keys = {"idle": lambda d: (-(d["idle_days"] or 0), d["relative"]),
            "size": lambda d: (-d["bytes"], d["relative"]),
            "name": lambda d: d["relative"],
            "started": lambda d: (d["started"] or "", d["relative"])}
    drafts.sort(key=keys[sort])
    body["truncated"] = len(drafts) > limit
    body["drafts"] = drafts[:limit]
    return body


def _totals(drafts):
    return {"drafts": len(drafts), "bytes": sum(d["bytes"] for d in drafts),
            **{f: sum(f in d["flags"] for d in drafts) for f in FLAGS}}


def _groups(drafts):
    out = {}
    for d in drafts:
        out.setdefault(d["group"], []).append(d)
    return [{"group": g, **_totals(items),
             "oldest_idle_days": max((d["idle_days"] or 0) for d in items)}
            for g, items in sorted(out.items(), key=lambda kv: (-sum(d["bytes"] for d in kv[1]), kv[0]))]


# --------------------------------------------------------------------------
# Text rendering


def human_size(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def _flag_text(flags):
    return ",".join(flags) if flags else "-"


def render(result, *, max_rows=None):
    lines = [f"Drafts under {_home(result['root'])}  [{result['status']}]  "
             f"stale = idle {result['stale_days']}d+"]
    t = result["totals"]
    lines.append(f"{t['drafts']} drafts, {human_size(t['bytes'])}; "
                 f"stale {t['stale']}, misnamed {t['misnamed']}, legacy layout {t['legacy']}")
    if result["action"] == "summary":
        rows = [("group", "drafts", "size", "stale", "misnamed", "legacy", "idle max")]
        rows += [(g["group"], str(g["drafts"]), human_size(g["bytes"]), str(g["stale"]), str(g["misnamed"]),
                  str(g["legacy"]), f"{g['oldest_idle_days']}d") for g in result["groups"]]
    else:
        rows = [("draft", "started", "idle", "size", "files", "flags")]
        rows += [(d["relative"], d["started"] or "-", f"{d['idle_days']}d" if d["idle_days"] is not None else "-",
                  human_size(d["bytes"]), str(d["files"]), _flag_text(d["flags"])) for d in result["drafts"]]
    shown = rows if max_rows is None else rows[:max_rows + 1]
    lines.append("")
    lines.extend(_table(shown))
    if len(rows) > len(shown):
        lines.append(f"… {len(rows) - len(shown)} more rows")
    if result.get("truncated"):
        lines.append("… list cut at the limit")
    for d in result["diagnostics"][:5]:
        lines.append(f"! {d['code']}: {_home(d['path'])}")
    return "\n".join(lines)


RICH_LIMIT = 30000          # Telegram rich messages cap at 32,768 characters
SECTION_ROWS = 25


def _group_label(group):
    return "(root)" if group == UNASSIGNED else group.partition("/")[2]


def _group_area(group):
    return "root" if group == UNASSIGNED else group.partition("/")[0]


def _section(draft):
    """Where a draft sits inside its Group: current, or the earlier scratch/deliverables/notes."""
    return (draft["legacy_area"] or "").lstrip(".") or "current"


def _cell(text):
    """A table cell as a code span: no Markdown inside names, and no pipe to break the row."""
    return "`" + text.replace("`", "'").replace("|", "/") + "`"


def _idle(draft):
    return f"{draft['idle_days']}d" if draft["idle_days"] is not None else "?"


def _details(title, rows, max_rows):
    out = [f"<details><summary>{title}</summary>", "", "| Draft | Idle | Size |",
           "| :--- | ---: | ---: |"]
    for d in rows[:max_rows]:
        name = d["name"] + (" (misnamed)" if "misnamed" in d["flags"] else "")
        out.append(f"| {_cell(name)} | {_idle(d)} | {human_size(d['bytes'])} |")
    if len(rows) > max_rows:
        out += ["", f"… {len(rows) - max_rows} more (`ws-drafts list`)"]
    return out + ["", "</details>"]


def render_rich(result, *, title="Drafts", max_rows=SECTION_ROWS):
    """Markdown for a chat that renders tables and <details> (Telegram rich messages):
    totals first, one table for the overview, and each section folded."""
    t = result["totals"]
    lines = [f"## {title}", "",
             f"**{t['drafts']}** drafts · **{human_size(t['bytes'])}** · stale {t['stale']} · "
             f"earlier layout {t['legacy']} · misnamed {t['misnamed']}", ""]
    if result["action"] == "summary":
        lines += ["| Group | Area | Drafts | Size | Stale |", "| :--- | :--- | ---: | ---: | ---: |"]
        lines += [f"| {_group_label(g['group'])} | {_group_area(g['group'])} | {g['drafts']} | "
                  f"{human_size(g['bytes'])} | {g['stale']} |" for g in result["groups"]]
        lines += ["", "<details><summary>How to read</summary>", "",
                  f"- stale: no file changed for {result['stale_days']}+ days",
                  "- earlier layout: scratch / deliverables / notes, still to be cleaned up",
                  "- misnamed: not `<YYYYMMDD>-<job>`",
                  "- a Group name may be shortened: `/drafts tech`",
                  "", "</details>", "",
                  "<details><summary>Open (tap to copy)</summary>", ""]
        lines += [f"`/drafts {label(g['group'])}`" for g in result["groups"]]
        lines += ["`/drafts stale`", "`/drafts legacy`", "`/drafts misnamed`", "", "</details>"]
    else:
        drafts = result["drafts"]
        one_group = len({d["group"] for d in drafts}) <= 1
        sections = {}
        for d in drafts:
            key = _section(d) if one_group else f"{_group_label(d['group'])} · {_section(d)}"
            sections.setdefault(key, []).append(d)
        order = sorted(sections.items(), key=lambda kv: (-sum(d["bytes"] for d in kv[1]), kv[0]))
        lines += ["| Where | Drafts | Size | Stale |", "| :--- | ---: | ---: | ---: |"]
        lines += [f"| {key} | {len(rows)} | {human_size(sum(d['bytes'] for d in rows))} | "
                  f"{sum('stale' in d['flags'] for d in rows)} |" for key, rows in order]
        for rows_cap in (max_rows, 10, 5):
            body = []
            for key, rows in order:
                size = human_size(sum(d["bytes"] for d in rows))
                body += [""] + _details(f"{key} · {len(rows)} · {size}", rows, rows_cap)
            if len("\n".join(lines + body)) <= RICH_LIMIT:
                break
        lines += body
        if result.get("truncated"):
            lines += ["", "… list cut at the limit (`ws-drafts list`)"]
    for d in result["diagnostics"][:3]:
        lines.append(f"\n! {d['code']}")
    return "\n".join(lines)


def _home(path):
    home = str(Path.home())
    return "~" + path[len(home):] if path.startswith(home + "/") or path == home else path


def _table(rows):
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    out = []
    for r in rows:
        cells = [r[0].ljust(widths[0])] + [c.rjust(w) if c[:1].isdigit() or c == "-" else c.ljust(w)
                                           for c, w in zip(r[1:], widths[1:])]
        out.append("  ".join(cells).rstrip())
    return out


# --------------------------------------------------------------------------
# CLI


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ws-drafts", description=__doc__.split("\n\n")[0])
    parser.add_argument("action", nargs="?", choices=ACTIONS, default="summary")
    parser.add_argument("--group", help="Group name (Acme) or Projects/Acme; (unassigned) for the root")
    parser.add_argument("--layout", choices=LAYOUTS, default="all")
    for flag in FLAGS:
        parser.add_argument(f"--{flag}", action="store_true", help=f"only drafts flagged {flag}")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--sort", choices=SORTS, default="idle")
    parser.add_argument("--limit", type=int, default=MAX_LIMIT)
    parser.add_argument("--root", help="Workspaces root (default $WORKSPACES_ROOT or ~/Workspaces)")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    args = {"action": ns.action, "layout": ns.layout, "stale_days": ns.stale_days,
            "flags": [f for f in FLAGS if getattr(ns, f)]}
    if ns.group:
        args["group"] = ns.group
    if ns.action == "list":
        args.update(sort=ns.sort, limit=ns.limit)
    try:
        result = run(args, root=ns.root)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ws-drafts: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if ns.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
