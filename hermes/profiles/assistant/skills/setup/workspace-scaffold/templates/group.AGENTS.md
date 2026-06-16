# <Group>

<!-- Group context (org / client / category). Local, not tracked in dotfiles. -->

<one-line: what this group is>

## Layout
- `github/<repo>/` — repos (each has its own committed AGENTS.md; usually a symlink to a `~/ghq` clone).
- `docs/` — specs / design / prose knowledge (`docs/about/`). Not in the registry DB.
- `data/` — datasets (optional).

Identity, repos, official links, **team memberships**, and tags live in the central projects
registry (`Projects/.registry/projects.db` via the `pj` CLI), not in this dir:
`pj show --id <Group>` · `pj members --project <Group>` · `pj repos|links`.

## Notes
- <contacts, deploy targets, conventions shared across this group's repos>
- Members reference People by `person_id`; manage with `pj member-set`. Wire repos with
  `pj repo-set` then `pj link-repo`.
