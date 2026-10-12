# <Group>

<!-- Group context (org / client / category). Local, not tracked in dotconfig. -->

<one-line: what this group is>

## Layout
- `github/<repo>/` — repos (each has its own committed AGENTS.md; a symlink to a `~/ghq` clone).
- `docs/` — specs / design / prose knowledge (`docs/about/`). Not in the registry.
- `data/` — datasets (optional).
- `assets/` — local media (logos, screenshots, generated material). Kept here so it is
  never committed into the repos (optional; on demand).

Identity, repos, official links, **team memberships**, and tags live in the workspace
registry (`~/Workspaces/.registry/`; agents: the `workspace_registry` tool, shell: `wsreg`),
not in this dir: `wsreg project --id <Group>` · `wsreg members --project <Group>`.

## Notes
- <contacts, deploy targets, conventions shared across this group's repos>
- Members reference people by `person_id`; manage them with `member_set`. Wire repos with
  `repo_set` then `link_repo`.
