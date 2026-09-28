"""Repositories under ~/Workspaces for Engineer and Assistant: the workspace_repos tool and /repos.

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
PROFILES = {"engineer", "assistant"}
ALIASES = {"prs": "prs", "pr": "prs", "pulls": "prs", "pullrequests": "prs", "pull-requests": "prs",
           "issues": "issues", "issue": "issues"}

DESCRIPTION = (
    "Repositories under ~/Workspaces (<Area>/<Group>/github/<repo>): local Git state and open GitHub work. "
    "Read-only: Git is read without fetching (behind = as of the last fetch) and nothing is committed, "
    "pulled or pushed; GitHub is read with one GraphQL query through gh. summary: every repo with its local "
    "flags (broken link, not-git, no-remote, remote-missing, shared-origin, dirty, unpushed, no-upstream, "
    "behind, detached, stash, worktrees, read-only upstream) and its open PR/issue/discussion counts; "
    "prs / issues: the open items of writable repos (review requested from you, CI state, assignees). "
    "Filter by group (Acme, a unique prefix or substring). github=false skips the network for "
    "summary. When GitHub is unreachable the local state is still returned with status partial.")

PROPERTIES = {
    "action": {"type": "string", "enum": list(repos.ACTIONS)},
    "group": {"type": "string", "description": "Group name (case-insensitive; a unique prefix or substring also matches)"},
    "github": {"type": "boolean", "description": "summary only: false = local Git state without network (default true)"},
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
    """``/repos [prs|issues] [group]`` or ``/repos <group>`` → (action, group or None)."""
    words = (raw or "").split()
    action = "summary"
    if words and words[0].lower() in ALIASES:
        action = ALIASES[words.pop(0).lower()]
    return action, " ".join(words) or None


def repos_text(raw):
    """/repos [prs|issues] [<group>]: overview, or open PRs / issues, optionally for one Group."""
    action, group = parse(raw)
    args = {"action": action, **({"group": group} if group else {})}
    try:
        result = repos.run(args)
        title = {"summary": "Repos", "prs": "Pull requests", "issues": "Issues"}[action]
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
                         description="Repos under ~/Workspaces: overview, or prs|issues [group], or <group>",
                         args_hint="[prs|issues] [<group>]")
