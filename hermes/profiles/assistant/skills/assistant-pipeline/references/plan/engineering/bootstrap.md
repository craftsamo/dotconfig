# Bootstrap — new-repo decisions (assistant-owned)

A human bootstraps a project by rhythm; you cannot. The repo does not
exist yet, so nothing can be grounded — not even the base plan
session — until bootstrap lands; it runs before any unit
decomposition. This leaf fixes the **decisions** in the Brief; the
execution recipe is a boundary operation and lives in
`../../execute/engineering/github-ops.md` (bootstrap is yours —
worktree-side establishment inside the clone is delegable only under
an explicit, user-sanctioned `B1`/`B2` grant; the GitHub/registry
side never).

This file is conventions only. **Concrete repo names, owners, and the
starter inventory are never written here** (this config repo is
public): discover them at runtime with the commands below; durable
findings live in private memory layers, never in tracked files.

## The starter family — conventions you decide against

Starters form a **derivation tree**, expressed in repo names:

- Root: `<name>-starter` — the platform-neutral base.
- Platform derivative: `<root>-with-<platform>` — the root plus one
  deployment/platform capability.
- Variant derivative: `<root>-with-<platform>-<variant>`.

Derivatives track their parent via an `upstream` git remote; a clone
without that wiring silently leaves the family (upstream-sync work
depends on it). Rebranding — README identity, package names,
container names — is NOT bootstrap: it is the first unit of the
first implement task on the new repo.

## Discovery — run, never recall

| Question | Command |
| --- | --- |
| Starters cloned locally? | `ghq list \| grep -i -- '-starter'` |
| Starters on the account (incl. uncloned)? | `gh repo list --limit 100 --json name,description,isTemplate \| grep -i starter` |
| Is one a template repo? | `gh repo view <owner>/<repo> --json isTemplate` |
| Lineage? | `git -C <path> remote -v` (`upstream` names the parent) |
| Maintained? | `gh repo view <owner>/<repo> --json pushedAt` |

An engineer assess turn (its bootstrap signal) can run this sweep
and report candidates with lineage and freshness; either way the
fit call below stays yours.

## Fit — shortlist by platform distance

1. Prefer the **nearest derivative** to the target need: a repo
   destined for platform X starts from `-with-<X>` when it exists,
   else the root; a new family variant starts from its nearest
   sibling, never the root.
2. Read the shortlist before choosing: README (what it claims to
   be), `AGENTS.md` (conventions a builder inherits), top-level
   layout, freshness.
3. Judge honestly — **a wrong starter costs more than scratch.**
   Present 2–3 candidates with a marked recommendation when the
   call is the user's to make.

## Decisions — fixed in the Brief, sanctioned by the plan approval

| Decision | How it is grounded |
| --- | --- |
| Group | `pj show --id <Group>`; missing → created during execution. |
| Repo name + owner | Owner comes from the runtime account context (`gh auth status`, existing ghq owners) — ask when more than one fits; the owner decides the ghq path. |
| Visibility | `--private` default; `--public` only on the user's say-so. |
| Starter or scratch | The discovery + fit sections above. |
| Deploy target | Usually implied by the chosen platform derivative; content sites need one, tools often none. |
| History posture | Plain clone keeps starter history; template instantiation starts squashed — state the choice in the plan, never default silently. |

Out of bootstrap's scope, always: wiring the deploy target (a normal
unit in the archetype leaf) and rebranding (see above).

Once the repo exists, create the **base plan session inside it** (see
`index.md`) — with a starter there is real code to ground the
decomposition in; the archetype leaf's prompt takes over from here.
