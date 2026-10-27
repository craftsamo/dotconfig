---
name: plan-engineering
description: "Plan engineering: brief OpenCode on the user's intent and bring its proposals back, as execution units the user approves one at a time. New products agree capabilities, screens and data (HTML mocks) before a roadmap. Grounded in OpenCode plan, design, debug and review runs; no technical decomposition of your own; each unit is an issue on GitHub before its build unless the user excludes the job."
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: pipeline
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
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../../SKILL.md` and `${HERMES_SKILL_DIR}/../../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Engineering - planning with OpenCode

Before the first `opencode_*` call, load the tool mechanics unless their
full bodies are already in the current context: `skill_view(name="opencode:brief")`
for the message you send a run, `skill_view(name="opencode:drive")` for
starting, reading and reporting runs, and `skill_view(name="opencode:answer")`
when a run is waiting on you.

## Who owns what

You commission OpenCode on the user's behalf; you are neither a go-between
nor a second technical planner.

| Who | Owns |
| --- | --- |
| The user | What the product is for, what people can do and see, what is stored, cost, anything irreversible, and the approval of each Phase |
| OpenCode | The technical design: architecture, schema details, libraries, how to test, how to split commits and PRs |
| You | Briefing OpenCode on what the user wants and why, turning its proposals and questions into plain language for the user, the job's decision log, and acceptance |

So a message to OpenCode is a short brief in plain prose: what is wanted and
why, the goal of the current stage and the path of the decision log, with the
user's words woven into your sentences where their wording carries the intent
(the log keeps them verbatim). Nothing else: no commands, steps, file lists,
output limits, report templates or restated prohibitions its tools already
enforce. Detailed instructions narrow the model without adding information.
`opencode:brief` shows the voice. A technical question
OpenCode asks goes back as its own call. What OpenCode proposes reaches the user in plain language and unrounded
where it touches them: every capability, screen and stored thing, not a
summary of them.

## The decision log

Each job keeps `decisions.md` in its draft directory
(`<Group>/.agent/<YYYYMMDD>-<job>/`), one row per item: the item, its source
(the user's words quoted exactly here / OpenCode's proposal / your proposal / found in the
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
| Other feature, change, refactor, migration, performance | `plan`, then `build` on the same session (a fork of it per unit when the roadmap has several) |
| Typo, one config value | a short `plan` turn, its one issue (Fixed from that turn), `workspace`, then `build`; the user's one-line go is the approval |
| New repository | [bootstrap.md](references/bootstrap.md), then plan on the clone |
| Script or small automation | a repository job like any other; you register the cron job or other Hermes-side wiring afterwards |
| Operational work around a repository (hosting, DNS, a domain, a contract, a hand-over item) | no run unless the repository's code or config changes: the steps happen in the services and with the people involved; part of that repository's job, and a draft on its board when the job is tracked ([GitHub boundaries](../execute/references/github-ops.md)) |

Not OpenCode's: writing, creative work, research and Hermes operations (cron,
messaging, secrets) go to their own entries. The Hermes configuration repo
(`~/ghq/github.com/craftsamo/dotconfig`; `~/.config` and `~/.hermes` link into
it) is live: plan there read-only, build only in the worktree
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
   approval). Run `opencode_run_plan` with a brief of what the user wants and
   why, the stage's goal and the log, and keep **what the user decided** apart from **what anyone
   proposed** (yours included) so OpenCode never treats a guess as a decision.
   A unit's plan turn passes its `issue` (`owner/repo#N`): the run reads it as
   the spec, and the session keeps it for the build.
   Name the kind of work (bug, refactor, performance, rebuild), not the method:
   OpenCode's own approach skills carry it. A diagnosis uses
   `opencode_run_debug`; a review of someone's change uses `opencode_run_review`.
4. **Relay.** Put OpenCode's proposal to the user: what changes for people
   (capabilities, screens, stored data, cost, risks to them) in full, the
   technical rest in a sentence. Ask in one round what only the user can decide,
   using OpenCode's own "decide" list in plain words, each with its
   recommendation. Do not invent questions about methods or conventions, and
   do not settle technical choices yourself: send them back as OpenCode's call.
5. **Approval.** For a roadmap of several units, the user approves the
   roadmap (below), then each unit's plan before that unit's build; for a
   single unit, one approval. Planning consent alone does not authorize
   implementation. Record the user's approving words in the log: Build quotes
   them as `approval`. The roadmap question also names where the job will be
   recorded on GitHub (the board, the parent issue and its units, or the one
   issue), as "Tracking" below says: read
   `skill_view(name="github-access:manage-tracking")` first, so it names its
   real shape. Once the roadmap is approved, file it on GitHub before the
   first unit's plan is Fixed, as
   [GitHub boundaries](../execute/references/github-ops.md) "Starting" says.
6. **Release** the approved unit through PR delivery under
   [Execute](../execute/SKILL.md). Keep the approved plan
   session as the trunk and fork it for each unit.

Planning, diagnosis or review may finish with an answer and no code or PR.
A confirmed bug is not implementation approval.

## Units and Phases

Work is planned in **execution units**. A unit is one goal that delivers on
its own, told by what people can do once it lands; it is implemented by one
PR or one native stack of PRs that lands in one merge, and on GitHub it is
one issue (`github-access:read-tracking` "Parent and execution unit"). A job
is one unit, or a roadmap of several.

Inside a unit, Phase N is one reviewable layer: one PR, or one layer of the
stack when there are several, in stack order. Phase N.m are its steps, each
ending in a verified checkpoint commit. OpenCode writes both in its own
task-list form (work that ends in no PR keeps its own plain steps). The
layers are the unit's plan; a layer is never an issue of its own.

- **Roadmap.** Ask OpenCode for the units in order, each with what people can
  do once it lands, what it changes in screens and stored data, and how the
  user will try it. Put the first unit where the user can try the main flow
  end to end, however plain. Show the roadmap whole; its approval covers the
  order and content of the units, not their builds.
- **Before each unit.** On a fork of the trunk, ask OpenCode for that unit's
  plan against what is now built: its layers, the open decisions resolved
  with a recommendation each. Show the user what they will be able to do
  afterwards, what changes in screens and data, any decision only they can
  make, and how to try it, with the layer list folded. Nothing to decide is
  one question: go ahead with this unit. Its approval releases that unit only,
  all of its layers.
- **A change of plan** (a unit that turns out wrong, a new wish) goes back to
  the roadmap with the user; the next unit's plan picks it up.

The roadmap and each unit's plan are written in OpenCode's reply, which the
job directory keeps; the words, headings and layout you show
the user are yours (voice and format come from the persona). A light job
(typo, one value) is three lines: outcome, what it touches, one check. The
approval covers what the user saw, so what you show is the scope Build is held
to. Models are OpenCode's own defaults; name one only when you depart from it
(an alternate after a limit error).

During a build, report as `opencode:drive`'s "Progress" says: each
finished step in one line, at once when one is blocked or the run needs
the user, and the unit's PR or stack with how to try it.

## Tracking

A job on a repository the user owns or belongs to is recorded on GitHub as
it is planned: the roadmap's approval files it (a parent issue with one
sub-issue per unit, drafts for the work outside the code, on the board
`github_board` `resolve` names for the repository, or the one issue of a
single-unit job), and each unit's issue is Fixed before its build. The user
excludes a job from GitHub in their own words ("track this nowhere", "no
issue for this"); record that in the log, and then no Issue or board changes
for that job. Duration, size or a fix the user calls small never excludes it
on their own: a small fix is one issue with one layer. Someone else's
repository (an open-source project, a client's) is never planned in; the
roadmap question asks where the user's own record goes, as
[GitHub boundaries](../execute/references/github-ops.md) "Someone else's
repository" says. The shape and the order of writing are the same file's
"Tracking a job on GitHub"; you write it and OpenCode reads it. A supplied Issue URL is a
specification, not permission to edit it. Existing session ids can be handed
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
