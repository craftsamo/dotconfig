---
name: plan-assistant-engineering
description: "Plan engineering: agree outcomes with the user and ground the plan in the repository through OpenCode plan, debug and review runs. Implementation approval, not technical decomposition or automatic Issue management."
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

OpenCode is the developer: it investigates the code and proposes the technical
plan with its own agents and skills. You are the user's Client, not a second
technical planner: you own the outcome, the constraints, the decisions only the
user can make and the implementation approval. Do not pre-decompose the
implementation or prescribe files; ask OpenCode for the proposal. An existing
Issue or plan is useful context, not a required intake artifact.

## What goes to OpenCode

Whatever reads or changes a repository's code goes to OpenCode, even a small
question; you never read or edit target code yourself.

| Case | Run |
| --- | --- |
| How does X work, where is Y | `plan` (read-only) |
| Bug, failing test, incident | `debug`; a fix is a separate approval |
| Review of someone's change | `review` on a fresh session |
| Feature, change, refactor, migration, performance | `plan`, then `build` on the same session |
| Typo, one config value | `build` directly; the user's one-line go is the approval |
| New repository | [bootstrap.md](references/bootstrap.md), then plan on the clone |
| Script or small automation | a repository job like any other; you register the cron job or other Hermes-side wiring afterwards |

Not OpenCode's: writing, creative work, research and Hermes operations (cron,
messaging, secrets) go to their own entries. You do not run OpenCode on the
Hermes configuration repo (`~/.config`): the person runs OpenCode on it directly.

## Steps

1. **Outcome.** Establish what the user wants changed or learned, what must
   stay intact and how success is observed. Locate the repository through the
   workspace registry; do not demand paths or technical choices already known.
   Ask only consequential unresolved questions; OpenCode can investigate
   feasibility and recommend architecture, tools, sequencing and verification.
2. **Ready check.** `opencode_preflight(directory, phase="plan")`: an `error`
   stops the run, a `warn` is worth one line to the user. It also tells you
   which role defaults are your own model. Then open or continue the job's
   draft directory (`<Group>/.agent/<YYYYMMDD>-<job>/`, see the kernel's
   StateLifecycle): it is the `output_dir` for runs that produce reports or
   screenshots.
3. **Ground it.** Plan on the repository's default checkout: a plan is
   read-only, so it needs no task branch or worktree (those come after
   approval). Run `opencode_run_plan` with the outcome, constraints and
   success criteria, and keep **what the user decided** apart from **what you
   assume** so OpenCode never treats a guess as a decision. Ask also for the
   repository's current test state. A diagnosis uses `opencode_run_debug`; a
   review of someone's change uses `opencode_run_review`. Name the kind of
   work (bug, refactor, performance, rebuild), not the method: OpenCode's own
   approach skills carry it.
4. **Challenge and settle.** Read the proposal for unsupported assumptions and
   request the smallest useful further investigation on the same session.
   Settle in-scope technical questions yourself through `opencode_request`;
   bring choices about outcome, cost, risk, public behavior or scope to the
   user, keeping what OpenCode suggested distinct from what the user decided.
5. **Approval.** Show the user the plan card below, then obtain explicit
   implementation approval for it (one `clarify`). Planning consent alone does
   not authorize implementation. A small settled fix needs no large ceremony,
   but still the user's go before a build. Record the user's approving words:
   Build quotes them as `approval`.
6. **Release** the approved scope through PR delivery under
   [Execute](../execute-assistant-engineering/SKILL.md) on the same OpenCode
   session; Execute gives it its worktree. Do not gate every internal phase.
   To keep a clean plan to return to, or to try a second approach, fork the
   plan session before its build.

Planning, diagnosis or review may finish with an answer and no code or PR.
A confirmed bug is not implementation approval.

## The plan card

One shared record, used when you ask OpenCode, when it answers, when the user
approves and when you accept the work. Ask OpenCode for these elements; the
words, headings and layout are yours (voice and format come from the persona).

- **Decisions and assumptions**, each with its source: the user's decision,
  OpenCode's proposal, verified in the repository, or assumed. A table is the
  readable form; five rows is plenty.
- **Scope** in and out, and how many PRs (an ordered list when several).
- **Verification** as a checklist of runnable checks with the expected result;
  at most seven. It is also the progress record and the acceptance list.
- For a migration, rebuild or public-API change, the way back.
- Risks and alternatives stay in the OpenCode session. Do not copy them out;
  fetch them with `opencode_session messages` when the user asks.

What the user sees is the part that needs them: the proposed and assumed items,
the scope and the checks, in a phone screen. Say the verified and decided items
in one sentence. A light job (typo, one value) is three lines: outcome, what it
touches, one check. The approval covers what the user saw, so the plan card
you show is the scope Build is held to. Models are OpenCode's own defaults; name
one in the plan only when you depart from it (an alternate after a limit error).

During the build, report only at four points, one line each: the build starts,
a PR is done (`2/3 checks`), it pauses for the user, QA is done. A deviation
inside the approved scope is continued and mentioned afterwards; one that
exceeds the scope stops the build and comes back to the user.

Issue management is explicit-only: Issue writes happen only when the user
requested tracking this job that way. A supplied Issue URL is a specification,
not permission to edit it. Duration, complexity or multiple PRs never create an
automatic Issue/epic/Projects requirement. Existing session ids can be handed
over as context, but old grants need reconciliation, not adoption.

## Client guides

| Archetype | Guide |
| --- | --- |
| A repository needs to be established | [bootstrap.md](references/bootstrap.md) |
| Content-led site, landing page, blog or portfolio | [web-content.md](references/web-content.md) |
| Stateful Web application | [webapp.md](references/webapp.md) |
| Script, CLI or automation | [tool.md](references/tool.md) |
| Existing-repository change | [existing-change.md](references/existing-change.md) |
| A change that alters what a web page looks like | [web-ui.md](references/web-ui.md) |

These guides hold Client questions and acceptance expectations, not prescribed
implementation units. OpenCode owns technical planning and its own checks.
