---
name: plan-assistant-engineering
description: "Plan engineering: relay the user's intent to OpenCode and its proposals back, in Phases the user approves one at a time. New products agree capabilities, screens and data (HTML mocks) before a roadmap. Grounded in OpenCode plan, design, debug and review runs; no technical decomposition of your own, no automatic Issue management."
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "engineering"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/plan/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Engineering - planning with OpenCode

Before the first `opencode_*` call, load the tool mechanics with
`skill_view(name="opencode:opencode")` unless its full body is already in the
current context.

## Who owns what

You relay; you are neither the user's proxy nor a second technical planner.

| Who | Owns |
| --- | --- |
| The user | What the product is for, what people can do and see, what is stored, cost, anything irreversible, and the approval of each Phase |
| OpenCode | The technical design: architecture, schema details, libraries, how to test, how to split commits and PRs |
| You | Passing the user's own words and the stage's goal to OpenCode, turning its proposals and questions into plain language for the user, the job's decision log, and acceptance |

So a message to OpenCode carries the user's words (quoted, not paraphrased),
the goal of the current stage and the path of the decision log, and little
else: no commands, steps, file lists, output limits or restated prohibitions
its tools already enforce. Detailed instructions narrow the model without
adding information. A technical question OpenCode asks goes back as its own
call. What OpenCode proposes reaches the user in plain language and unrounded
where it touches them: every capability, screen and stored thing, not a
summary of them.

## The decision log

Each job keeps `decisions.md` in its draft directory
(`<Group>/.agent/<YYYYMMDD>-<job>/`), one row per item: the item, its source
(the user's words quoted / OpenCode's proposal / your proposal / found in the
repository) and its state (proposed / decided / withdrawn). Only the user's
explicit choice moves a row to decided; a proposal nobody objected to stays
proposed. A Chat opinion of yours enters as your proposal. Point OpenCode at
the log instead of pasting decisions, and update it in place when an item
changes. Approved designs and the log are promoted to the Group's `docs/`
with the delivery.

## What goes to OpenCode

Whatever reads or changes a repository's code goes to OpenCode, even a small
question; you never read or edit target code yourself.

| Case | Run |
| --- | --- |
| How does X work, where is Y | `plan` (read-only) |
| Survey whose deliverable is a report (inventory, audit, handover) | `plan` with the job directory as `output_dir`, one session per repository; its final reply is saved there as the report |
| Bug, failing test, incident | `debug`; a fix is a separate approval |
| Review of someone's change | `review` on a fresh session |
| New product, or a feature that adds screens or stored data | [new-product.md](references/new-product.md): purpose, then capabilities, screens and data as HTML mocks (`design`), then the Phases |
| Other feature, change, refactor, migration, performance | `plan`, then `build` on the same session (a fork of it per Phase when there are several) |
| Typo, one config value | a short `plan` turn, `workspace`, then `build`; the user's one-line go is the approval |
| New repository | [bootstrap.md](references/bootstrap.md), then plan on the clone |
| Script or small automation | a repository job like any other; you register the cron job or other Hermes-side wiring afterwards |

Not OpenCode's: writing, creative work, research and Hermes operations (cron,
messaging, secrets) go to their own entries. The Hermes configuration repo
(`~/.config`) is live: plan there read-only, build only in the worktree
`workspace` gives the session (a write run in the live checkout is refused), and
leave install, gateway restarts and the cutover to the person.

## Steps

1. **Outcome.** Establish what the user wants changed or learned and how they
   will use it, in their words. Locate the repository through the workspace
   registry; do not demand paths or technical choices already known. Ask only
   what the user alone can answer; OpenCode investigates feasibility and
   recommends architecture, tools, sequencing and verification.
2. **Ready check.** `opencode_preflight(directory, phase="plan")`: an `error`
   stops the run, a `warn` is worth one line to the user. Then open or continue
   the job's draft directory and its decision log; it is the `output_dir` for
   runs that produce reports, mocks or screenshots.
3. **Ground it.** Plan on the repository's default checkout: a plan is
   read-only, so it needs no task branch or worktree (those come after
   approval). Run `opencode_run_plan` with the user's words, the stage's goal
   and the log, and keep **what the user decided** apart from **what anyone
   proposed** (yours included) so OpenCode never treats a guess as a decision.
   Name the kind of work (bug, refactor, performance, rebuild), not the method:
   OpenCode's own approach skills carry it. A diagnosis uses
   `opencode_run_debug`; a review of someone's change uses `opencode_run_review`.
4. **Relay.** Put OpenCode's proposal to the user: what changes for people
   (capabilities, screens, stored data, cost, risks to them) in full, the
   technical rest in a sentence. Ask in one round what only the user can decide,
   using OpenCode's own "decide" list in plain words, each with its
   recommendation. Do not invent questions about methods or conventions, and
   do not settle technical choices yourself: send them back as OpenCode's call.
5. **Approval.** For work of several Phases, the user approves the roadmap
   (below), then each Phase's steps before that Phase's build; for a single
   PR, one approval. Planning consent alone does not authorize implementation.
   Record the user's approving words in the log: Build quotes them as
   `approval`.
6. **Release** the approved Phase through PR delivery under
   [Execute](../execute-assistant-engineering/SKILL.md). Keep the approved plan
   session as the trunk and fork it for each Phase.

Planning, diagnosis or review may finish with an answer and no code or PR.
A confirmed bug is not implementation approval.

## Phases

Phase N is one reviewable layer: one PR, or one layer of a native stack when
there are several, in stack order. Phase N.m are its steps, each ending in a
verified checkpoint commit. OpenCode writes both in its own task-list form
(work that ends in no PR keeps its own plain steps).

- **Roadmap.** Ask OpenCode for the Phases in order, each with what people can
  do once it lands, what it changes in screens and stored data, and how the
  user will try it. Put the first Phase where the user can try the main flow
  end to end, however plain. Show the roadmap whole; its approval covers the
  order and content of the Phases, not their builds.
- **Before each Phase.** On a fork of the trunk, ask OpenCode for that Phase's
  steps against what is now built. Show the user what they will be able to do
  afterwards, what changes in screens and data, any decision only they can
  make, and how to try it, with the step list folded. Nothing to decide is one
  question: go ahead with this Phase. Its approval releases that Phase only.
- **A change of plan** (a Phase that turns out wrong, a new wish) goes back to
  the roadmap with the user; the next Phase's plan picks it up.

The roadmap and each Phase's plan are written in OpenCode's reply, which the
job directory keeps; the words, headings and layout you show
the user are yours (voice and format come from the persona). A light job
(typo, one value) is three lines: outcome, what it touches, one check. The
approval covers what the user saw, so what you show is the scope Build is held
to. Models are OpenCode's own defaults; name one only when you depart from it
(an alternate after a limit error).

During a build, report as the plugin skill's "Progress" section says: each
finished Phase step in one line, at once when one is blocked or the run needs
the user, and the Phase's PR with how to try it.

Issue management is explicit-only: Issue writes happen only when the user
requested tracking this job that way. A supplied Issue URL is a specification,
not permission to edit it. Duration, complexity or multiple PRs never create an
automatic Issue/epic/Projects requirement. Existing session ids can be handed
over as context, but old grants need reconciliation, not adoption.

## Client guides

| Archetype | Guide |
| --- | --- |
| A new product, or a feature with new screens or stored data | [new-product.md](references/new-product.md) |
| A repository needs to be established | [bootstrap.md](references/bootstrap.md) |
| Content-led site, landing page, blog or portfolio | [web-content.md](references/web-content.md) |
| Stateful Web application | [webapp.md](references/webapp.md) |
| Script, CLI or automation | [tool.md](references/tool.md) |
| Existing-repository change | [existing-change.md](references/existing-change.md) |
| A change that alters what a web page looks like | [web-ui.md](references/web-ui.md) |

These guides hold the user's questions and acceptance expectations, not
prescribed implementation units. OpenCode owns technical planning and its own
checks.
