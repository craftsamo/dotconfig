---
name: starter-catalog
description: >-
  Engineer's map of the local starter/boilerplate ecosystem — how starter
  repositories and their platform derivatives are named, discovered at
  runtime (ghq + gh, never from memory), evaluated for fit, and introduced
  when bootstrapping a new repository (implement.md's B1/B2 bootstrap
  branch). Load it when an assess job reports a bootstrap signal and needs
  grounded starter candidates, or when a bootstrap job's chosen path names
  a starter from the local family. Generic by design: this file carries
  conventions and recipes only — concrete family names are discovered per
  task and persisted to MEMORY.md, never written into this skill.
version: 1.0.0
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
starter/boilerplate family, not from `git init`. Knowing how that family is
structured, how to OBSERVE it (discovery + fit evaluation, read-only), and
how to INTRODUCE it (clone + remote wiring under the B grant) turns "no
repo yet" from a guess into a grounded report and a mechanical bootstrap.

This skill is **conventions plus recipes, never an inventory**. The family
grows and this config repo is public — concrete repo names never live
here. Discover them at runtime; persist durable findings to MEMORY.md.

</Goal>

<Scope>
<UseWhen>

- An assess (facts) job hits the bootstrap signal — no repo exists — and
  the report should include grounded `starter:` candidates.
- A bootstrap job (implement.md <BootstrapBranch>) whose chosen path names
  a starter from the local family, and you need the introduction mechanics
  (clone source, remote wiring).
- A feasibility verdict depends on whether a suitable starter exists here.

</UseWhen>
<DoNotUseWhen>

- Choosing the path — clone vs starter vs greenfield is the orchestrator's
  decision; this skill informs it and executes it, never makes it.
- Generic public scaffolders (`create-next-app`, `cargo new`, `uv init`) —
  implement.md's bootstrap branch covers them directly.
- Work inside an existing repo.

</DoNotUseWhen>
</Scope>

<FamilyConvention>

Starters form a **derivation tree**, expressed in repo names:

- Root: `<name>-starter` — the platform-neutral base.
- Platform derivative: `<root>-with-<platform>` — the root plus one
  deployment/platform capability.
- Variant derivative: `<root>-with-<platform>-<variant>` — a derivative
  specialized further.

Illustrative shape (names are fictional — discover the real family with
<DiscoveryRecipes>, never assert from this file):

```
acme-starter                        ← root
├─ acme-starter-with-paas           ← platform derivative
└─ acme-starter-with-k8s
   └─ acme-starter-with-k8s-bot     ← variant derivative
```

Two conventions travel with the tree:

- **Derivatives track their parent** via an `upstream` git remote (`origin`
  = the derivative's own repo, `upstream` = the parent starter). Periodic
  upstream-sync work depends on this wiring — a derivative cloned without
  it is cut off from its family.
- **Rebranding is not bootstrap.** Changing the identity surface (README
  title/intro/clone URLs, package names, container names) to the new
  repo's own is the first unit of the FIRST implement task on the new
  repo — the bootstrap job only establishes the clone, the remotes, and
  the initial commit state.

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

<FitEvaluation>

Read-only, assess altitude — the output is candidates for the decider,
never a decision:

1. **Inventory** the family (<DiscoveryRecipes>), locally and remotely.
2. **Shortlist by platform distance** — prefer the nearest derivative to
   the target need (a repo destined for platform X starts from
   `-with-<X>` if it exists, else the root; a new variant starts from its
   nearest sibling, not the root).
3. **Read the shortlisted candidates**: README (what it claims to be),
   `AGENTS.md`/`CLAUDE.md` (conventions a builder inherits), top-level
   layout (workspaces/apps/packages), and freshness (recipes above).
4. **Report 2-3 candidates** with one line each — lineage, platform fit,
   freshness — plus a marked recommendation and its reason. This slots
   into the assess bootstrap signal's `starter: <candidates>` option
   (`references/assess.md`).

</FitEvaluation>

<IntroductionPaths>

Executed only on a bootstrap job, under its B grant
(implement.md <BootstrapBranch> owns the full contract — guard, initial
commit, report):

| Chosen path | Mechanics | Grant |
| --- | --- | --- |
| New project from a starter | clone the starter to the target ghq path → point `origin` at the NEW repo (`gh repo create --source … --push` does both) → add `upstream` = the starter | remote creation/push = B2; local-only stops before the remote step (B1) |
| New family derivative | same as above; the clone source is the **nearest sibling** (per <FitEvaluation>), `upstream` = that sibling | B1/B2 as above |
| Template-repo instantiation | `gh repo create --template <starter>` — remote-first, so **B2 only**; clone the result to the ghq path; template copies carry no upstream remote — add one if family sync is wanted | B2 |

- Rebranding stays out (see <FamilyConvention>) — report it as the
  expected first unit of the follow-up implement task instead.
- Preserving upstream history vs a squashed start is a **path decision the
  brief must state** (plain clone keeps history; `--template` or
  `degit`-style copies do not) — absent, block rather than pick.

</IntroductionPaths>

<MemoryDiscipline>

After a real discovery, persist the durable facts to MEMORY.md — the
family's root name, the platform derivatives that exist, and which parent
a newly created repo tracks. That private, untracked layer holds the
concrete names; this skill stays generic. Never write an inventory into
this file, a report template, or any tracked config.

</MemoryDiscipline>

<Pitfalls>

- Asserting family membership, template status, or freshness from memory
  (or from this file's fictional examples) — run the recipes.
- Shopping: turning fit evaluation into a path decision. Candidates +
  recommendation go UP (assess report / `Q<n>`); the orchestrator decides.
- Cloning a derivative without wiring the `upstream` remote — it silently
  leaves the family.
- Rebranding, feature work, or unit planning inside the bootstrap job.
- Instantiating a template repo on a B1 grant — template creation is
  remote-first, therefore B2.
- Writing discovered repo names into this skill or other tracked files —
  MEMORY.md is the private layer for them.

</Pitfalls>

<Verification>

- Every candidate named in a report came from a recipe run in THIS task,
  with lineage and freshness noted.
- The path decision was made by the orchestrator's brief or answer,
  not by this skill's user; fit evaluation stayed read-only.
- An introduced derivative has `origin` pointing at its own repo and
  `upstream` at its parent; remote actions occurred only under B2.
- No concrete family names were added to tracked files; durable findings
  went to MEMORY.md.

</Verification>
