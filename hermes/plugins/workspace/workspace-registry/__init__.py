"""The workspace_registry tool for the Assistant: people, projects, memberships and
repos of ~/Workspaces, read and written without a terminal.

The engine is ``registry.py`` beside this file (the ``wsreg`` CLI runs the same
code); the data is the CSV files under ``~/Workspaces/.registry/`` and is never
part of the plugin source. An optional ignored peer_checks.py adds local checks.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
import sys

PROFILES = {"assistant"}
# Skill -> the profiles it is registered for. A skill is read-only to Hermes (not editable through
# skill_manage); a profile that cannot do what a skill describes is not given it.
SKILLS = {"workspace-registry": set(PROFILES)}
LIMIT = 60000
PLUGIN = "workspace-registry"
logger = logging.getLogger(__name__)


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


registry = _load("hermes_workspace_registry_engine", Path(__file__).resolve().parent / "registry.py")

DESCRIPTION = (
    "The registry of people, projects (the ~/Workspaces/Projects groups and their organizations), "
    "memberships (who works on which project, roles, areas, permissions) and repos. Use it instead of any "
    "terminal command. Read: whois (query = a name, alias or handle such as @user; resolve a message sender), "
    "person / project (id; everything about one), persons / projects / members / repos (lists; filters "
    "status, kind, organization, project, person), search (query), review (records still needs_review), "
    "validate. Write: group_create (a new Projects/<id> Group: id + project fields; makes github/, docs/, "
    "data/ and a seeded AGENTS.md, then registers it; keeps what exists — fill AGENTS.md afterwards), "
    "person_set / project_set (id + fields; creates when missing, partial update otherwise), "
    "member_set (project + person + fields; list fields replace the whole list), member_rm, repo_set / "
    "repo_rm (project + name), link_repo (symlink Projects/<P>/github/<name> to the ghq clone; never "
    "clones), add / remove (facet on a person: alias, contact, language, nationality, note; on a project: "
    "alias, link, tag), rename (person or project = current id, new_id). "
    "Rules for writes: never guess personal facts — leave a field empty when unknown and keep "
    "review_status needs_review until the user confirms; ids are stable (a person id is a bare lowercase "
    "slug, a project id is its Projects/<id> directory name); people and projects are never deleted, set "
    "status inactive or archived instead; organization_id must name a project of kind org. "
    "A write that would make the registry invalid is rejected with the reason.")

PROPERTIES = {
    "action": {"type": "string", "enum": list(registry.ACTIONS)},
    "id": {"type": "string", "description": "person / project / person_set / project_set / group_create: the id"},
    "person": {"type": "string", "description": "a person id: members filter, member_set/member_rm, add/remove/rename target"},
    "project": {"type": "string", "description": "a project id: persons/members/repos filter, member_*, repo_*, link_repo, add/remove/rename target"},
    "name": {"type": "string", "description": "repo_set / repo_rm / link_repo: the repo name"},
    "new_id": {"type": "string", "description": "rename: the new id"},
    "query": {"type": "string", "description": "whois / search"},
    "status": {"type": "string", "description": "persons / projects filter"},
    "kind": {"type": "string", "description": "persons / projects filter; add/remove facet=link: landing|x|github|docs|discord|other"},
    "organization": {"type": "string", "description": "projects filter: projects of this organization id"},
    "facet": {"type": "string", "enum": ["alias", "contact", "language", "nationality", "note", "link", "tag"]},
    "value": {"type": "string", "description": "add/remove: the alias, handle, language code (ja), country code (JP), note text, URL or tag value"},
    "channel": {"type": "string", "enum": list(registry.CHANNELS), "description": "facet=contact"},
    "proficiency": {"type": "string", "enum": list(registry.PROFICIENCY), "description": "facet=language"},
    "axis": {"type": "string", "description": "facet=tag: stage, priority, domain, engagement, platform, ..."},
    "label": {"type": "string", "description": "facet=link"},
    "primary": {"type": "boolean", "description": "add: make it the primary alias/contact/language/nationality"},
    "date": {"type": "string", "description": "facet=note: YYYY-MM-DD (default today)"},
    "fields": {"type": "object", "description": (
        "person_set: display_name, kind (self|individual), status (active|inactive), review_status "
        "(needs_review|confirmed|ignored), residence_country (JP), preferred_language (ja), "
        "preferred_contact_channel, timezone (Asia/Tokyo). project_set: canonical_name, slug, kind "
        "(org|client|category|personal|external), status (active|inactive|archived), organization_id, summary, "
        "review_status (group_create takes the same). member_set: status (active|inactive), "
        "working_relationship, can_merge, can_deploy, "
        "roles, responsibilities, areas, notes (lists). repo_set: owner, host, url, ghq_path, summary, status "
        "(declared|linked|missing|archived), review_status. An empty string clears a field.")},
}


def _inbound_peer():
    """An A2A turn (a peer agent's request) never reads or writes this registry."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    return "a2a" in (get_session_env("HERMES_SESSION_PLATFORM", ""), get_session_env("HERMES_SESSION_SOURCE", ""))


def workspace_registry(args, **kwargs):
    try:
        if _inbound_peer():
            raise ValueError("workspace_registry is not available to inbound A2A requests")
        text = json.dumps(registry.run(args), ensure_ascii=False)
        if len(text) > LIMIT:
            return json.dumps({"ok": False, "error": f"result is {len(text)} characters; narrow it with a "
                                                     "filter or one id"})
        return text
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


def register_skills(ctx, profile):
    """Register this profile's skills; a skill that cannot be read is logged and never costs the tool."""
    for name, profiles in SKILLS.items():
        if profile not in profiles:
            continue
        try:
            from agent.skill_utils import parse_frontmatter

            path = Path(__file__).resolve().parent / "skills" / name / "SKILL.md"
            meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            ctx.register_skill(name, path, description=meta["description"], frontmatter=meta)
        except Exception as exc:
            logger.warning("%s skill %s not registered: %s", PLUGIN, name, exc)


def register(ctx):
    if ctx.profile_name not in PROFILES:
        return
    ctx.register_tool(name="workspace_registry", toolset="workspace_registry", handler=workspace_registry,
                      description=DESCRIPTION,
                      schema={"name": "workspace_registry", "description": DESCRIPTION, "parameters": {
                          "type": "object", "properties": PROPERTIES, "required": ["action"],
                          "additionalProperties": False}})
    register_skills(ctx, ctx.profile_name)
