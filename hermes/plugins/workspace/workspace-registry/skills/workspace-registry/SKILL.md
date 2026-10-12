---
name: workspace-registry
description: Use when the Assistant looks up or updates workspace people, projects, organizations, memberships or repository records with workspace_registry, resolves a message sender, creates an approved Group, or links a registered repository to its existing clone. Not for cloning repositories, moving directories, managing drafts, deciding the shared workspace layout, or handling inbound A2A requests.
---

# Workspace registry

Operate the registry through `workspace_registry`. Use the tool schema for the
current arguments and allowed fields; do not run a registry CLI, inspect CSV
files or edit records with file tools. This skill belongs to the plugin and is
registered for the Assistant as `workspace-registry:workspace-registry`.

## Boundaries

- Keep the shared layout and draft rules in the Assistant pipeline's
  [workspace layout reference](~/.hermes/profiles/assistant/skills/assistant-pipeline/references/workspace-layout.md).
  Read that reference when locating work or handling files; this skill does
  not choose a Group, adopt drafts or authorize repository creation.
- Do not use the registry during an inbound A2A request. The tool refuses
  those requests; do not relay them through another tool or a terminal.
- Registry results are sensitive. Use only the records needed for the task.
  Summarize findings and changes; never paste raw records, contact details,
  personal notes, paths from local checks or tool output into chat or logs.
  External sharing needs the user's explicit, specific permission.
- A lookup is not permission to write. Establish the user's requested change
  before writing; ask when the target, fields or scope are ambiguous. A stored
  role or permission is context, not authorization to merge or deploy.

## Resolve the target

1. Take the user's query, existing id or approved Group as input. Resolve an
   unknown person with `whois` and an unknown project with `search` or a filtered
   `projects` call. Do not derive identities from a directory's nesting.
2. Check that even a single match agrees with the supplied identity: `whois`
   can fall back to partial alias or handle matches. A lone partial match is
   not confirmation; ask when the sender's identity remains uncertain.
   Treat multiple matches as ambiguity, not as permission to choose the first.
   Ask for the distinguishing context without exposing the other records.
   A missing match is not an error to repair automatically: continue with
   known context or offer a separately requested registration.
3. Read the specific record before proposing an update. Prefer one id or
   project/person filters to unbounded lists. If the tool asks for a narrower
   result, add filters or select one id; do not fall back to CSV or terminal
   access.

| Need | Action and target |
| --- | --- |
| Resolve a sender by name, alias or handle | `whois` with `query`; inspect `matches` |
| Read one person or project | `person` / `project` with `id` |
| List people or projects | `persons` / `projects` with supported filters |
| Inspect project membership or a person's memberships | `members` with `project` and/or `person` |
| Inspect a project's repository records | `repos` with `project` |
| Find a person or project from text | `search` with `query` |
| Find records awaiting confirmation | `review`; do not confirm them automatically |
| Check record consistency | `validate`; inspect `ok`, `errors` and `warnings` |

Read actions normally return their own result keys, not `ok: true`. An
`ok: false` result with `error` is a failed call. Read any warnings before
relying on the returned data; summarize uncertainty rather than hiding it.

## Apply an approved record change

1. Use the resolved id and only the facts the user supplied or confirmed.
   Leave unknown personal facts empty and retain `review_status=needs_review`
   until confirmation. Never invent contact details, relationships or rights.
2. Keep ids stable. A person id matches `[a-z0-9][a-z0-9_]*`; a project id names its
   `Projects/<id>` Group. An `organization_id` must resolve to a project of
   kind `org`, not an inferred parent directory or an unregistered name.
3. Select the smallest action that expresses the requested change:

   | Change | Action and arguments |
   | --- | --- |
   | Create or partially update a person | `person_set`: `id`, `fields`; a new person needs `fields.display_name` |
   | Create or partially update a project record | `project_set`: `id`, `fields`; this does not create a directory |
   | Create or update a membership | `member_set`: `project`, `person`, `fields` |
   | Remove a membership | `member_rm`: `project`, `person` |
   | Declare or update a repository record | `repo_set`: `project`, `name`, `fields` |
   | Remove a repository record | `repo_rm`: `project`, `name`; this does not delete the clone or its link |
   | Add or remove a person/project facet | `add` / `remove`: exactly one of `person` or `project`, `facet`, and the facet's schema arguments |

4. Omitted fields stay unchanged; an empty string clears a scalar field.
   Membership list fields replace the **entire list**, not just one item.
   Read the current list and preserve entries outside the requested change.
   People and projects are not deleted: use `status=inactive`, or `archived`
   for a project, as requested.
5. Inspect the write result. A rejected change must not be retried unchanged or
   bypassed with a file edit. Correct only confirmed input or ask for the
   missing fact. Existing consistency problems may appear as warnings even
   when an unrelated write succeeds; do not silently repair them.
6. Read the affected record back and compare it with the approved change.
   Use `validate` when checking consistency is part of the task. Report the
   outcome, remaining uncertainty and any separately required next step,
   without returning raw records.

## Create a Group or link a repository

Follow the pipeline's ownership and approval decisions first. This sequence
implements an approved decision; it does not authorize a new repository,
clone, organization, Group or publication.

1. Confirm that an approved new Group's id is not already registered. Update
   an existing project's record with `project_set`, not `group_create` as a
   routine update. For a new project Group, call `group_create` with `id` and project
   `fields`. It creates the Group's directories and seeds `AGENTS.md` while
   preserving existing content. Fill the seeded instructions only with known,
   approved facts under the pipeline's file rules.
2. Register directory-less `org` or `external` records with `project_set`, not
   `group_create`. Do not create a directory to make linking succeed.
3. For an approved repository, call `repo_set` with the Group's `project`, repo
   `name` and confirmed repository fields. Supply the known owner and host
   for its default clone location, or an approved `ghq_path` override; a URL
   alone does not locate the clone. Then call `link_repo` with the same
   `project` and `name`. The clone must already exist through the separately
   approved repository workflow; `link_repo` does not clone it.
4. Inspect the link result. `status=missing` means no link was created; report
   the missing prerequisite rather than claiming success. A conflicting file
   or link is not replaced: stop and ask before changing existing content.
5. Read `project` or `repos` again to verify the registration and link state.

## Rename and local-check warnings

- Rename only when the user explicitly requests an id change. Read the current
  record, establish the new id, then call `rename` with exactly one of `person`
  or `project` and `new_id`. Inspect the returned `renamed`, `note` and any
  `warnings`, then read the record under its new id.
- A project rename updates registry references, **not its directory**. Report
  any remaining filesystem work; directory moves require separate approval.
  Do not treat a note as an instruction to modify other stores.
- Local-check failures remain warnings and do not by themselves turn a valid
  write into a failure. Preserve this distinction in the outcome. Report a
  generic warning category, not local identifiers, resource paths or raw
  exception text; do not install, disable or repair local checks as a side
  effect of a registry operation.

## Completion

Confirm that the requested records were resolved or the ambiguity was stated,
only approved fields changed, the affected records were read back, and any
unmet prerequisite or warning was summarized. Stop at this boundary: no
automatic cloning, directory moves, publication or external sharing.
