"""Session history for Engineer and Assistant: the hermes_history tool and /activity.

The readers are stdlib modules beside this file (``hermes.py``, ``common.py``,
``cli.py``) so cron and the ``ai-history`` launcher run the same code. This
file only registers them; it launches nothing and writes nothing.
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


HERE = Path(__file__).resolve().parent
cli = _load("hermes_session_history_cli", HERE / "cli.py")
reader = cli.hermes
PROFILES = {"engineer", "assistant"}
PERIODS = {"": 1, "today": 1, "week": 7, "month": 30}

DESCRIPTION = (
    "Read Hermes session history across every profile (read-only; metadata only). "
    "list: sessions overlapping [from, to) (started before to, last active at or after from), newest first, "
    "paged by limit/offset; kind defaults to root; filter by profile, platform (cli, telegram, cron, kanban, "
    "subagent, a2a, ...), directory, model. get: one session with its compression lineage; children: sessions "
    "it spawned or continued into. usage: tokens and activity over [from, to) grouped by group_by (default "
    "profile). active_seconds = time the agent loop was working (model output and tool execution, the gap "
    "before each model reply or tool result), minus clarify waits; active_union_seconds removes overlap "
    "between sessions and profiles; question_wait_seconds = clarify waits; opencode_wait_seconds and "
    "specialist_wait_seconds are the part of activity spent waiting on OpenCode or another profile, whose "
    "own sessions count that time too. None of these measure human working time. Tokens come from per-model "
    "usage records; a record spanning a window edge cannot be split and is excluded and disclosed "
    "(usage-crosses-window). usage includes archived sessions unless archived is false. Use days=N for the "
    "last N local days ending today, or from/to as YYYY-MM-DD (local midnight of timezone) or ISO 8601. "
    "Titles and costs only with include_title / include_cost; message content never. Every result states "
    "its source (api = Hermes' session store, db = direct read), status and diagnostics. For OpenCode's own "
    "sessions use opencode_history.")

PROPERTIES = {
    "action": {"type": "string", "enum": list(reader.ACTIONS)},
    "session_id": {"type": "string", "description": "get / children only"},
    "profile": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                "description": "Profile name(s); default all, including default"},
    "from": {"type": "string", "description": "YYYY-MM-DD or ISO 8601; usage needs from+to or days"},
    "to": {"type": "string", "description": "Exclusive end; YYYY-MM-DD or ISO 8601"},
    "days": {"type": "integer", "description": "Instead of from/to: the last N local days ending today (1 = today)"},
    "timezone": {"type": "string", "description": "IANA name for dates and day groups"},
    "directory": {"type": "string", "description": "Absolute path; matches it and everything below"},
    "kind": {"type": "string", "enum": list(reader.KINDS)},
    "platform": {"type": "string", "description": "Session source: cli, telegram, cron, kanban, subagent, a2a, ..."},
    "model": {"type": "string", "description": "provider/model or model"},
    "archived": {"type": "boolean", "description": "Include archived and hidden sessions"},
    "search": {"type": "string", "description": "list only: title substring"},
    "include_title": {"type": "boolean"}, "include_cost": {"type": "boolean"},
    "limit": {"type": "integer", "description": f"list only: 1..{reader.MAX_LIMIT}"},
    "offset": {"type": "integer", "description": "list only"},
    "group_by": {"type": "array", "items": {"type": "string", "enum": list(reader.GROUPS)},
                 "description": "usage only; task applies to tokens (activity is task main)"},
    "source": {"type": "string", "enum": list(reader.SOURCES),
               "description": "auto (session store, disclosed database fallback), api, or db"},
}


def _inbound_peer():
    """An A2A turn (a peer agent's request) never reads this machine's history."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def hermes_history(args, **kwargs):
    try:
        if _inbound_peer():
            raise ValueError("hermes_history is not available to inbound A2A requests")
        return json.dumps(reader.run(args), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def activity_text(raw):
    """/activity [today|week|month|N]: activity of OpenCode and Hermes as plain Markdown;
    chats with rich messages render its tables and folded breakdowns."""
    word = (raw or "").strip().lower()
    days = PERIODS.get(word)
    if days is None:
        if not word.isdigit() or not 1 <= int(word) <= cli.common.MAX_DAYS:
            return ("Usage: /activity [today|week|month|N days]\n\n"
                    + "\n".join(f"`/activity {p}`" for p in cli.PERIOD_COMMANDS))
        days = int(word)
    try:
        return cli.render_summary_rich(cli.summary({"days": days}))
    except Exception as exc:
        return f"activity unavailable: {exc}"


async def activity_command(raw):
    # The readers block on SQLite and a short `opencode db path` subprocess;
    # keep that off the gateway's event loop.
    return await asyncio.to_thread(activity_text, raw)


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    ctx.register_tool(name="hermes_history", toolset="session_history", handler=hermes_history,
                      description=DESCRIPTION,
                      schema={"name": "hermes_history", "description": DESCRIPTION, "parameters": {
                          "type": "object", "properties": PROPERTIES, "required": ["action"],
                          "additionalProperties": False}})
    ctx.register_command("activity", activity_command,
                         description="AI activity for OpenCode and Hermes (today, week, month or N days)",
                         args_hint="[today|week|month|N]")
