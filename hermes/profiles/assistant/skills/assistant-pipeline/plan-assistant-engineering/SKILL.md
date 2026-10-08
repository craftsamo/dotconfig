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

1. **Outcome.** Establish what the user wants changed or learned, what must
   stay intact and how success is observed. Locate the repository through the
   workspace registry; do not demand paths or technical choices already known.
   Ask only consequential unresolved questions; OpenCode can investigate
   feasibility and recommend architecture, tools, sequencing and verification.
2. **Checkout.** When implementation is the likely outcome, put the checkout on
   a task branch BEFORE the first plan run (`git switch -c <branch>`; a separate
   `git worktree add` only when another session uses this checkout or the main
   checkout must stay untouched). A session is bound to its worktree and
   branch, and the plan session is the one Build continues, so the branch
   decides now whether the plan's context carries over. Plan-only work may stay
   on the default branch. Branch and worktree setup is yours; no file in the
   target repository is edited by you, ever — even a one-line change goes
   through an OpenCode build.
3. **Job directory.** Open or continue the job's draft directory
   (`<Group>/.agent/<YYYYMMDD>-<job>/`, see the kernel's StateLifecycle). It is
   the `output_dir` for runs that produce reports or screenshots.
4. **Ground it.** Run `opencode_run_plan` on the worktree with the outcome,
   constraints, known decisions and success criteria, and ask for a proposal:
   the change, its boundaries, verification, risks, and the choices that need
   the user. A diagnosis uses `opencode_run_debug`; a review of someone's change
   uses `opencode_run_review`. Bugs need reproduction, performance a measured
   baseline, refactors a behavior safety net, rebuilds data preservation and
   recovery — OpenCode's own approach skills carry the method; name the kind of
   work, not the method.
5. **Challenge and settle.** Read the proposal for unsupported assumptions and
   request the smallest useful further investigation on the same session.
   Settle in-scope technical questions yourself through `opencode_request`;
   bring choices about outcome, cost, risk, public behavior or scope to the
   user, keeping what OpenCode suggested distinct from what the user decided.
6. **Approval.** Present the proposed outcome, scope, verification, important
   tradeoffs and risks as visible text, then obtain explicit implementation
   approval for that plan (one `clarify`). Planning consent alone does not
   authorize implementation. A small settled fix needs no large ceremony, but
   still the user's go before a build. Record the user's approving words: Build
   quotes them as `approval`.
7. **Release** the approved scope through PR delivery under
   [Execute](../execute-assistant-engineering/SKILL.md) on the same OpenCode
   session. Do not gate every internal phase.

Planning, diagnosis or review may finish with an answer and no code or PR.
A confirmed bug is not implementation approval.

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

These guides hold Client questions and acceptance expectations, not prescribed
implementation units. OpenCode owns technical planning and its own checks.
