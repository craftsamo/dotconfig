"""Drafts and the inbox under ~/Workspaces for the Assistant: the workspace_drafts
tool and /drafts.

The lister is the stdlib module ``drafts.py`` beside this file, so cron and the
``ws-drafts`` launcher run the same code. This file only registers it; it
moves and deletes nothing.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


drafts = _load("hermes_workspace_drafts", Path(__file__).resolve().parent / "drafts.py")
PROFILES = {"assistant"}

DESCRIPTION = (
    "List drafts under ~/Workspaces (read-only; names, sizes, file counts and modification times only). "
    "A draft is any job directory below an .agent/: <Group>/.agent/<YYYYMMDD>-<job>/, or "
    "~/Workspaces/.agent/<YYYYMMDD>-<job>/ for unassigned work; everything there is non-canonical and a "
    "draft that remains is work not yet promoted. The earlier layout (root .scratch/.deliverables/.notes and "
    "<Group>/.agent/{scratch,deliverables,notes}/), retired and emptied on 2026-09-28, is still reported with "
    "layout legacy: a job finishing in place or a stray write. summary: counts and size "
    "per Group; list: one row per draft (sort idle|size|name|started). Flags: stale = no file changed for "
    "stale_days (default 14), misnamed = not <YYYYMMDD>-<kebab-slug>, legacy = earlier layout. Filter by "
    "group (Acme, Projects/Acme or (unassigned)), layout and flags (all must match). The inbox "
    "(~/Workspaces/.inbox: incoming material to triage, never a draft) is reported apart: summary adds its "
    "totals per source; inbox lists one row per item (an entry of .inbox/<source>/, or a loose entry in "
    ".inbox/), oldest first, with stale = its oldest file waited inbox_stale_days (default 7); only "
    "sort idle|size|name, limit and the stale flag apply. It never "
    "reads file contents and never moves or deletes; promotion and deletion follow ~/Workspaces/AGENTS.md "
    "\"Drafts\" and need the user's approval.")

PROPERTIES = {
    "action": {"type": "string", "enum": list(drafts.ACTIONS)},
    "group": {"type": "string", "description": "Group name (case-insensitive; a unique prefix or substring also matches), Area/Group, or root"},
    "layout": {"type": "string", "enum": list(drafts.LAYOUTS)},
    "flags": {"type": "array", "items": {"type": "string", "enum": list(drafts.FLAGS)}},
    "stale_days": {"type": "integer", "description": "Idle days that count a draft as stale (default 14)"},
    "inbox_stale_days": {"type": "integer",
                         "description": "Days an inbox item's oldest file may wait before it is stale (default 7)"},
    "sort": {"type": "string", "enum": list(drafts.SORTS),
             "description": "list and inbox; inbox takes idle|size|name, where idle = oldest file waiting longest"},
    "limit": {"type": "integer", "description": f"list and inbox: 1..{drafts.MAX_LIMIT}"},
}


def _inbound_peer():
    """An A2A turn (a peer agent's request) never reads this machine's workspace."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def workspace_drafts(args, **kwargs):
    try:
        if _inbound_peer():
            raise ValueError("workspace_drafts is not available to inbound A2A requests")
        return json.dumps(drafts.run(args), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def drafts_text(raw):
    """/drafts [inbox|stale|misnamed|legacy|<group>]: summary, the inbox, or a list narrowed
    by flag or Group. ``inbox`` wins over a Group of that name."""
    word = (raw or "").strip()
    if not word:
        args, title = {"action": "summary"}, "Drafts"
    elif word.lower() == "inbox":
        args, title = {"action": "inbox"}, "Inbox"
    elif word.lower() in drafts.FLAGS:
        args, title = {"action": "list", "flags": [word.lower()]}, f"Drafts · {word.lower()}"
    else:
        args, title = {"action": "list", "group": word}, None
    try:
        if title is None:           # name the Group(s) actually matched, not what was typed
            matched = drafts.resolve_group(word, drafts.known_groups())
            title = "Drafts · " + ", ".join(drafts.label(g) for g in matched)
        # Plain Markdown, not a code block: chats with rich messages render the
        # tables and fold each <details> section.
        return drafts.render_rich(drafts.run(args), title=title)
    except drafts.UnknownGroup as exc:
        return (f"No Group matches `{exc.needle}`. Try one of:\n\n"
                + "\n".join(f"`/drafts {drafts.label(g)}`" for g in exc.groups))
    except Exception as exc:
        return f"drafts unavailable: {exc}"


async def drafts_command(raw):
    # Walking a large workspace blocks on the filesystem; keep it off the gateway loop.
    return await asyncio.to_thread(drafts_text, raw)


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    ctx.register_tool(name="workspace_drafts", toolset="workspace_drafts", handler=workspace_drafts,
                      description=DESCRIPTION,
                      schema={"name": "workspace_drafts", "description": DESCRIPTION, "parameters": {
                          "type": "object", "properties": PROPERTIES, "required": ["action"],
                          "additionalProperties": False}})
    ctx.register_command("drafts", drafts_command,
                         description="Drafts under ~/Workspaces: summary, or inbox|stale|misnamed|legacy|<group>",
                         args_hint="[inbox|stale|misnamed|legacy|<group>]")
