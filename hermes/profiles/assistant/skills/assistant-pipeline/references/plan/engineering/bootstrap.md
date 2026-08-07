# Bootstrap — new-repo decisions (assistant-owned)

A human bootstraps a project by rhythm; you cannot. The repo does not
exist yet, so nothing can be grounded — not even the base plan
session — until bootstrap lands; it runs before any unit
decomposition. This leaf fixes the **decisions** in the Brief; the
execution recipe is a boundary operation and lives in
`../../execute/engineering/github-ops.md` (bootstrap is yours —
worktree-side establishment is delegable only under an explicit,
user-sanctioned `B1`/`B2` grant, the GitHub/registry side never).

This file is conventions only. **Concrete repo names, owners, and the
starter inventory are never written here** (this config repo is
public): discover them at runtime, exactly as the engineer's
`starter-catalog` technic prescribes — its discovery recipes, family
conventions (`<root>-starter` → `-with-<platform>` derivatives), and
fit evaluation apply to you unchanged.

## Decisions — fixed in the Brief, sanctioned by the plan approval

| Decision | How it is grounded |
| --- | --- |
| Group | `pj show --id <Group>`; missing → created during execution. |
| Repo name + owner | Owner comes from the runtime account context (`gh auth status`, existing ghq owners) — ask when more than one fits; the owner decides the ghq path. |
| Visibility | `--private` default; `--public` only on the user's say-so. |
| Starter or scratch | Run the starter-catalog discovery recipes (ghq + `gh repo list`), shortlist by platform distance, judge fit honestly — a wrong starter costs more than scratch. |
| Deploy target | Usually implied by the chosen platform derivative; content sites need one, tools often none. |
| History posture | Plain clone keeps starter history; template instantiation starts squashed — state the choice in the plan, never default silently. |

Out of bootstrap's scope, always: wiring the deploy target (a normal
unit in the archetype leaf) and rebranding (README identity, package
names — the first unit of implementation).

Once the repo exists, create the **base plan session inside it** (see
`index.md`) — with a starter there is real code to ground the
decomposition in; the archetype leaf's prompt takes over from here.
