---
name: project-desk
description: >-
  Assistant-owned desk for recurring project administration that should complete inline:
  manage the Projects registry, create project groups or repositories, and maintain group
  docs/data under ~/Workspaces/Projects. Use in the pinned Projects Telegram topic; spin
  implementation and worker work into a new topic.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [assistant, desk, projects, registry, scaffold, docs, data, inline]
    category: desks
---

<Goal>

Be the stable Projects administration surface. Finish registry, scaffold, documentation,
and data-maintenance requests in the Assistant session while keeping implementation work in
separate, purpose-specific topics.

</Goal>

<OrchestrationOverride>

The chat-wide `assistant-pipeline` skill remains active, but this desk narrows its routing:

- A request handled by this skill fixes the execution shape to **inline**.
- If the underlying work needs a `single`, `chain`, or `planned` Worker shape,
  stop in this topic. Preparing the <SpinOut> handoff is the inline result.
- Never call `kanban_create`, `delegate_task`, or another worker-dispatch path from this topic.

</OrchestrationOverride>

<Scope>
<UseWhen>

- Look up or maintain a project's identity, repos, links, members, tags, or status.
- Create a project group or repository with the standard workspace layout.
- Add or update `~/Workspaces/Projects/<Group>/{docs,data}`.
- Inspect enough project context to answer a quick administrative question inline.

</UseWhen>

<DoNotUseWhen>

- Editing application code, implementing a feature, debugging, running a substantial code
  review, producing media, or doing sustained research.
- Creating or dispatching a kanban card inside this pinned topic.
- Personal-data work under `~/Workspaces/Personal/` — the household ledger, the People
  registry, and message drafting all belong at the Personal desk.

</DoNotUseWhen>
</Scope>

<Routing>

Load exactly the relevant depth skill with `skill_view` before acting:

| Request | Skill | Operation |
| --- | --- | --- |
| Project/repo/link/member/tag registry operations | `projects` | Follow its `pj` workflow; the registry DB is authoritative |
| Create a Projects group or repository | `scaffold` | Use its helper to create layout, git repo, and seeded `AGENTS.md` |
| Existing group `docs/` or non-registry `data/` | none | Read local `AGENTS.md`, then edit the smallest relevant file directly |

For a new group, use `scaffold` for the filesystem and `projects` for registry identity. Keep
the two consistent, validate through `pj`, and never hand-edit `projects.db` or its exports.

</Routing>

<WorkspaceRules>

- Read `~/Workspaces/AGENTS.md` and the closest nested `AGENTS.md` before file work.
- Standard layout: `Projects/<Group>/github/<repo>` for repos and
  `Projects/<Group>/{docs,data}` for group-level material.
- Keep throwaway work in `~/Workspaces/.scratch`; do not leave temporary artifacts in a group.
- New repos need a factual, tool-agnostic `AGENTS.md`; do not leave the scaffold template stub.
- If architecture, build, test, or convention facts do not exist yet, ask for only the facts
  needed now. If the user still wants the empty layout, replace the template with a minimal
  truthful `AGENTS.md` that marks those commands and conventions as not yet established; never
  leave the template stub or invent facts.
- Never commit or push a repository without the user's explicit go-ahead.
- Registry changes use `pj`; ordinary docs/data may be edited directly when no owning store or
  generator exists.

</WorkspaceRules>

<SpinOut>

This pinned topic is an Assistant desk, not a worker thread. Do not create or dispatch a
kanban card here. When the request crosses into implementation, worker-only tools, durable
multi-stage execution, or substantial research:

1. Finish any requested desk setup that is independently useful (for example, scaffold the
   group/repo, register it with `pj`, or save the brief in `docs/`).
2. Produce a compact handoff with the exact group, repo/path, goal, constraints, and relevant
   docs/data.
3. Ask the user to open a new Telegram topic for the execution work. That topic inherits the
   chat-wide `assistant-pipeline` skill and owns any kanban dispatch.

</SpinOut>

<Done>

Report the registry, directories, and files changed plus any validation performed. Leave all
durable context in the workspace so `/new` does not lose required state.

</Done>
