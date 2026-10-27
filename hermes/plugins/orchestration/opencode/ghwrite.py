"""A build's own GitHub writes, answered inside the user's mandate.

An OpenCode write tool asserts a permission before it changes GitHub (the tool
id as the action, the targets as resources, what it will change as metadata).
For a run bound to an issue and to a mandate, two of those requests are the
run's own execution state and are answered here without a person: ticking its
issue's body, and moving its issue's board Status to In Progress. Everything
else (another issue, a close, a comment, a label, a final Status, a board the
mandate does not name) stays with the Assistant, who may only reject the
request and make the change through github-access.

The verdict is the github-access planner's and the mandate's, read fresh at
the write (`changes.plan` reads the targets, `mandate.still_fits` the mandate
in force), never this module's own reading of the request.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

RUN_GH_WRITES = ("gh_issue_update", "gh_project_item_set")
# Every GitHub write a run's tools can raise (the ruleset denies all but RUN_GH_WRITES
# under a mandate): the caller may reject one, never approve it.
GH_WRITES = RUN_GH_WRITES + (
    "gh_issue_create", "gh_issue_comment", "gh_issue_relate", "gh_issue_develop", "gh_project_create",
    "gh_project_link", "gh_project_field_ensure", "gh_project_view_ensure", "gh_project_item_add",
    "gh_project_item_promote")
# What a build may change on its own issue: the body (a tick, an appended step). The
# title, state, comments, labels, assignees, milestones and kind are the Assistant's.
ISSUE_EDIT_KEYS = {"body": "body", "appendBody": "append_body"}
# The one Status a build sets: its unit is being built. Done, Cancelled and Waiting
# are the Assistant's calls, made on acceptance or on a pause the user knows of.
STATUS_VALUES = ("in progress",)
GITHUB_ACCESS = Path(__file__).resolve().parents[2] / "github-access"


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def modules():
    """github-access's planner and mandate store, under the names they share state by."""
    return (_load("hermes_github_access_changes", GITHUB_ACCESS / "changes.py"),
            _load("hermes_github_access_mandate", GITHUB_ACCESS / "mandate.py"))


def ours(request) -> bool:
    """A request this module answers: one of the run's own state writes."""
    return isinstance(request, dict) and request.get("kind") == "permission" and request.get("action") in RUN_GH_WRITES


def github_write(request) -> bool:
    """A GitHub write of any kind: approved on a card or inside a mandate, never by the caller's `once`."""
    return isinstance(request, dict) and request.get("kind") == "permission" and request.get("action") in GH_WRITES


def same_ref(a, b) -> bool:
    """GitHub names are case-insensitive; the binding is spelled by the caller, the tool by GitHub."""
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()


def _ref(md):
    repo, number = md.get("repo"), md.get("number")
    return f"{repo}#{number}" if isinstance(repo, str) and isinstance(number, int) else None


def change_for(request, meta):
    """The github_change this request amounts to, or why it is not the run's own state to write."""
    md = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
    issue, action = meta.get("issue"), request.get("action")
    if not issue:
        return None, "the session is bound to no issue"
    if action == "gh_issue_update":
        if not same_ref(_ref(md), issue):
            return None, f"{_ref(md) or 'the request'} is not the run's issue {issue}"
        extra = sorted(k for k, v in md.items() if k not in ISSUE_EDIT_KEYS and k not in ("op", "repo", "number")
                       and v is not None)
        if extra:
            return None, f"a build changes only its issue's body, not {', '.join(extra)}"
        change = {"op": "issue_edit", "issue": issue,
                  **{ISSUE_EDIT_KEYS[k]: md[k] for k in ISSUE_EDIT_KEYS if md.get(k) is not None}}
        if len(change) == 2:
            return None, "the request changes nothing"
        return change, None
    if action == "gh_project_item_set":
        if not same_ref(md.get("content"), issue):
            return None, f"{md.get('content') or 'the item'} is not the run's issue {issue}"
        fields = md.get("fields") if isinstance(md.get("fields"), dict) else {}
        other = [k for k in ("clear", "title", "body", "append_body", "archived") if md.get(k) not in (None, [], False)]
        if other or {k.lower() for k in fields} != {"status"}:
            return None, "a build moves only its issue's Status on the board"
        value = next(iter(fields.values()))
        if not isinstance(value, str) or value.strip().lower() not in STATUS_VALUES:
            return None, f"a build sets its issue's Status to In Progress only, not {value!r}"
        if not isinstance(md.get("item"), str):
            return None, "the request names no board item"
        return {"op": "item_set", "item": md["item"], "fields": fields}, None
    return None, "not a write a build answers for itself"


def verdict(home, meta, request):
    """("once" | "reject", reason) for one of the run's own GitHub writes, or (None, reason)
    when the request is not one. A reject names why, so the caller can make the change
    through github-access instead."""
    if not ours(request):
        return None, "not a GitHub write of the run"
    change, why = change_for(request, meta)
    if change is None:
        return "reject", why
    mandate_id = meta.get("mandate")
    if not isinstance(mandate_id, str):
        return "reject", "the session is bound to no mandate; the Assistant writes the issue"
    try:
        changes, mandate = modules()
        planned = changes.plan({"changes": [change]})
        why = mandate.still_fits(home, mandate_id, planned)
    except Exception as exc:  # the planner's refusal is the verdict, never a crash of the wait
        return "reject", f"github-access refused the change: {exc}"
    if why:
        return "reject", why
    return "once", f"inside mandate {mandate_id}"
