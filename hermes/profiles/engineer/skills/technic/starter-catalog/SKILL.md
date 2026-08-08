---
name: starter-catalog
description: >-
  Engineer's observation kit for the local starter/boilerplate ecosystem —
  how starter repositories and their platform derivatives are named and
  discovered at runtime (ghq + gh, never from memory), so an assess job can
  ground the bootstrap signal's starter candidates, and how family remote
  wiring is verified from inside a worktree. The starter DECISION and the
  repo's establishment are the assistant's (its bootstrap plan leaf owns
  the fit rubric; its github-ops boundary owns creation and wiring) — this
  skill observes and reports, and executes nothing beyond a delegated
  worktree job's own scope. Generic by design: conventions and recipes
  only — concrete family names are discovered per task and persisted to
  MEMORY.md, never written into this skill.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [bootstrap, starter, boilerplate, scaffolding, ghq, discovery]
    category: technic
    related_skills: [engineer-pipeline, machine-env]
---

<Goal>

New repositories on this machine usually start from a maintained
starter/boilerplate family, not from `git init`. Knowing how that family
is structured and how to OBSERVE it (read-only discovery) turns an assess
bootstrap signal from a guess into a grounded candidate report. Choosing
a starter and introducing the repo are the assistant's; your output is
observations.

This skill is **conventions plus recipes, never an inventory**. The
family grows and this config repo is public — concrete repo names never
live here. Discover them at runtime; persist durable findings to
MEMORY.md.

</Goal>

<Scope>
<UseWhen>

- An assess (facts) job hits the bootstrap signal — no repo exists — and
  the report should include grounded `starter:` candidates.
- A feasibility verdict depends on whether a suitable starter exists here.
- Work inside a family worktree needs its lineage verified (upstream-sync
  jobs, or a delegated bootstrap job checking its ground).

</UseWhen>
<DoNotUseWhen>

- Choosing the starter or the path — clone vs starter vs greenfield is
  the assistant's decision (its bootstrap plan leaf carries the fit
  rubric); this skill informs it, never makes it.
- Creating repos, wiring remotes, template instantiation — the
  assistant's github-ops boundary operations, never yours.
- Generic public scaffolders (`create-next-app`, `cargo new`, `uv init`)
  — implement.md's <BootstrapBranch> covers running them directly.

</DoNotUseWhen>
</Scope>

<FamilyConvention>

Starters form a **derivation tree**, expressed in repo names:

- Root: `<name>-starter` — the platform-neutral base.
- Platform derivative: `<root>-with-<platform>` — the root plus one
  deployment/platform capability.
- Variant derivative: `<root>-with-<platform>-<variant>` — a derivative
  specialized further.

Operationally, a family member carries `origin` = its own repo and
`upstream` = its parent starter; a worktree missing that `upstream` has
silently left the family — report the drift (upstream-sync work depends
on the wiring), and repair it only when the job's grant names it.
Rebranding is not bootstrap: the identity surface (README, package
names, container names) changes as the first unit of the first
implement task, never in an establishment job.

</FamilyConvention>

<DiscoveryRecipes>

Run these instead of trusting memory — single commands, owner-free (ghq
scans all owners; `gh` resolves the authenticated account at runtime):

| Question | Command |
| --- | --- |
| Which starters exist locally? | `ghq list \| grep -i -- '-starter'` |
| Where are they on disk? | `ls -d ~/ghq/github.com/*/*starter*` |
| Which starters exist remotely (incl. not-yet-cloned)? | `gh repo list --limit 100 --json name,description,isTemplate \| grep -i starter` |
| Is one a GitHub template repo? | `gh repo view <owner>/<repo> --json isTemplate` |
| What is a repo's lineage? | `git -C <path> remote -v` (an `upstream` remote names the parent) |
| Is it maintained? | `git -C <path> log --oneline -3` (recency), `gh repo view <owner>/<repo> --json pushedAt` |

</DiscoveryRecipes>

<CandidateReport>

For an assess bootstrap signal, the observation deliverable is:

1. **Inventory** the family (<DiscoveryRecipes>), locally and remotely.
2. **Read the plausible candidates**: README (what it claims to be),
   `AGENTS.md`/`CLAUDE.md` (conventions a builder inherits), top-level
   layout, freshness (recipes above).
3. **Report 2-3 candidates** with one line each — lineage, platform fit,
   freshness — plus a marked recommendation and its reason. This slots
   into the assess bootstrap signal's `starter: <candidates>` option
   (`references/assess.md`). The fit call itself is the assistant's.

</CandidateReport>

<MemoryDiscipline>

After a real discovery, persist the durable facts to MEMORY.md — the
family's root name, the platform derivatives that exist, and which parent
a newly created repo tracks. That private, untracked layer holds the
concrete names; this skill stays generic. Never write an inventory into
this file, a report template, or any tracked config.

</MemoryDiscipline>

<Pitfalls>

- Asserting family membership, template status, or freshness from memory
  (or from this file's naming shapes) — run the recipes.
- Shopping: turning observation into a path decision. Candidates +
  recommendation go UP (assess report / `Q<n>`); the assistant decides.
- Executing establishment from here — repo creation, remote wiring, and
  template instantiation are the assistant's boundary operations; a
  delegated bootstrap job's own scope lives in implement.md
  <BootstrapBranch>, not in this skill.
- Repairing a missing `upstream` remote without a grant that names it —
  observe and report the drift.
- Writing discovered repo names into this skill or other tracked files —
  MEMORY.md is the private layer for them.

</Pitfalls>

<Verification>

- Every candidate named in a report came from a recipe run in THIS task,
  with lineage and freshness noted.
- No decision was made here: the report carries candidates and a marked
  recommendation, and stops.
- Nothing was created, cloned, rewired, or instantiated from this skill.
- No concrete family names were added to tracked files; durable findings
  went to MEMORY.md.

</Verification>
