"""Repositories under ~/Workspaces for the Assistant: the workspace_repos tool and /repos.

The scanner is the stdlib module ``repos.py`` beside this file, so cron and the
``ws-repos`` launcher run the same code. This file only registers it; it
commits, fetches and pushes nothing.
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


repos = _load("hermes_workspace_repos", Path(__file__).resolve().parent / "repos.py")
PROFILES = {"assistant"}
ALIASES = {"prs": "prs", "pr": "prs", "pulls": "prs", "pullrequests": "prs", "pull-requests": "prs",
           "issues": "issues", "issue": "issues", "commits": "commits", "commit": "commits", "log": "commits"}
PERIOD_HINT = ["`/repos commits week`", "`/repos prs week`", "`/repos issues week`"]

DESCRIPTION = (
    "Repositories under ~/Workspaces (<Area>/<Group>/github/<repo>): local Git state and open GitHub work. "
    "Read-only: Git is read without fetching (behind = as of the last fetch) and nothing is committed, "
    "pulled or pushed; GitHub is read with one GraphQL query through gh. summary: every repo with its local "
    "flags (broken link, not-git, no-remote, remote-missing, shared-origin, dirty, unpushed, no-upstream, "
    "behind, detached, stash, worktrees, read-only upstream) and its open PR/issue/discussion counts; "
    "prs / issues: the open items of writable repos (review requested from you, CI state, assignees), or "
    "with days every one updated in the period, merged and closed included; commits: your commits "
    "(author = the repo's Git user.name or user.email) on local and remote-tracking branches in the last "
    "days local calendar days (default 1 = today; week = 7, month = 30), no network. Filter by group "
    "(Acme, a unique prefix or substring). github=false skips the network for summary. When GitHub "
    "is unreachable the local state is still returned with status partial.")

PROPERTIES = {
    "action": {"type": "string", "enum": list(repos.ACTIONS)},
    "group": {"type": "string", "description": "Group name (case-insensitive; a unique prefix or substring also matches)"},
    "github": {"type": "boolean", "description": "summary only: false = local Git state without network (default true)"},
    "days": {"type": "integer", "description": "commits, prs, issues: the last N local calendar days (1 = today, 7 = week, 30 = month)"},
}


def _inbound_peer():
    """An A2A turn (a peer agent's request) never reads this machine's repositories."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def workspace_repos(args, **kwargs):
    try:
        if _inbound_peer():
            raise ValueError("workspace_repos is not available to inbound A2A requests")
        return json.dumps(repos.run(args), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def parse(raw):
    """``/repos [prs|issues|commits] [today|week|month|N] [group]``, in any order →
    (action, days or None, group or None)."""
    action, days, rest = None, None, []
    for word in (raw or "").split():
        if action is None and word.lower() in ALIASES:
            action = ALIASES[word.lower()]
        elif days is None and repos.parse_period(word) is not None:
            days = repos.parse_period(word)
        else:
            rest.append(word)
    return action or "summary", days, " ".join(rest) or None


def repos_text(raw):
    """/repos [prs|issues|commits] [period] [<group>]: overview, open PRs / issues, or what
    changed in a period, optionally for one Group."""
    try:
        action, days, group = parse(raw)
    except ValueError as exc:
        return f"{exc}\n\n" + "\n".join(PERIOD_HINT)
    if action == "summary" and days is not None:
        return "A period goes with commits, prs or issues:\n\n" + "\n".join(PERIOD_HINT)
    args = {"action": action, **({"group": group} if group else {}), **({"days": days} if days else {})}
    try:
        result = repos.run(args)
        title = {"summary": "Repos", "prs": "Pull requests", "issues": "Issues", "commits": "Commits"}[action]
        if result.get("days") and action != "summary":
            title += " · " + repos.period_label(result["days"])
        if group:                   # name the Group(s) actually matched, not what was typed
            title += " · " + ", ".join(repos.label(g) for g in result["groups"])
        # Plain Markdown, not a code block: chats with rich messages render the
        # tables and fold each <details> section.
        return repos.render_rich(result, title=title)
    except repos.UnknownGroup as exc:
        prefix = "" if action == "summary" else f"{action} "
        return (f"No Group matches `{exc.needle}`. Try one of:\n\n"
                + "\n".join(f"`/repos {prefix}{repos.label(g)}`" for g in exc.groups))
    except Exception as exc:
        return f"repos unavailable: {exc}"


async def repos_command(raw):
    # Git and gh block on subprocesses; keep them off the gateway loop.
    return await asyncio.to_thread(repos_text, raw)


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    ctx.register_tool(name="workspace_repos", toolset="workspace_repos", handler=workspace_repos,
                      description=DESCRIPTION,
                      schema={"name": "workspace_repos", "description": DESCRIPTION, "parameters": {
                          "type": "object", "properties": PROPERTIES, "required": ["action"],
                          "additionalProperties": False}})
    ctx.register_command("repos", repos_command,
                         description="Repos under ~/Workspaces: overview, prs|issues|commits [period] [group], or <group>",
                         args_hint="[prs|issues|commits] [today|week|month|N] [<group>]")
