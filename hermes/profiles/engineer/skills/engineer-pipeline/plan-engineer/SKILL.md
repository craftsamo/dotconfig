---
name: plan-engineer
description: "Plan engineering: agree a grounded implementation scope."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: engineer-pipeline
    tags: [plan, engineering]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or scope changes, including within a turn.
Load the root with skill_view(name="engineer-pipeline") only if its full body
is not already present in the current context; reuse full-body instructions
only while present in the current context, not a past load or summary. This
entry is the mode procedure itself, not a second common mode index. Canonical
root fallback when skill_view returns unchanged without its earlier body is
`${HERMES_SKILL_DIR}/../SKILL.md`; recover this entry's own
body and its references from `${HERMES_SKILL_DIR}` via read_file and
next_offset. Stop the affected action when a required body is unavailable;
never take an alternate path or an artificial range to dodge this check.

Before the first wrapper call, or whenever transport context is lost, load
skill_view(name="engineer-pipeline", file_path="references/opencode.md") if
its full body is not already present, with fallback
`${HERMES_SKILL_DIR}/../references/opencode.md`; no generic per-mode common
transport copy. Reading the root or transport file is not implementation
approval. A cross-mode link requires loading that mode's owning entry and the
root before applying its details -- only the locally relevant details apply here.

</ReadBeforeWork>

# Plan

Start from the Client's outcome and existing decisions, not a mandatory form.
Technical planning is yours with OpenCode. A plan-only request ends here.
Read [OpenCode](../references/opencode.md) before a wrapper call and
[Web UI](references/web-ui.md) when visual direction or user flows need decisions.

1. Establish purpose, current behavior, constraints and observable success.
   Locate the intended repository; ask on ambiguity, never search all private
   workspaces or guess a project. A supplied Issue is read-only grounding unless
   the Client explicitly requested Issue management.
2. Ground in the current tree. Use opencode_call(agent="plan") for investigation,
   options and a technical proposal. Existing approved plans need a relevance
   check, not compulsory re-decomposition. Separate ordinary implementation
   choices from Client choices about outcomes, cost, risk and scope.
3. Use the fitting OpenCode approach, not a duplicate methodology here: a bug
   needs reproduction; performance needs a baseline; refactoring needs a behavior
   safety net; rebuilds need recovery/data preservation; dependencies need actual
   version/advisory evidence. Engineer can run bounded safe observations/tests;
   no target edits or unapproved side effects during planning. Missing evidence
   stays explicit. Mixed work can be split technically without asking the Client
   to design the split, unless that changes the requested scope.
4. Read OpenCode's proposal, challenge unsupported assumptions and request the
   smallest useful additional investigation. For Web UI, agree direction before
   target implementation; existing design systems outrank style-catalog defaults.
5. Present the plan: intended change, boundaries, meaningful steps, verification,
   risks and unresolved decisions. Human clarify or Client Q<n>, not a fixed
   questionnaire. Obtain explicit implementation approval for that scope.
6. Prepare or identify a separate task worktree/branch before Build. A planning
   conversation cannot silently change worktree/branch: start a new wrapper
   conversation grounded on the approved plan text when moving from the main
   checkout. Then follow [Build](../build-engineer/SKILL.md).

Record the approved plan and the Client's decision in private job state or the
agreed existing record. No automatic PLAN.md in the repository, Issue or board.
If Issue-managed work was explicitly requested, include that scoped request in
the handoff. Issue writes run through the build agent after implementation/write
authority is settled; an Issue-only registration request is a bounded authorized
write, not permission to start implementing the proposed feature.

An image-creator/video-creator/audio-creator hands leaf's option-backed
reference addition or improvement uses [Hands references](references/hands-references.md)
instead of a generic Skill-authoring approach.

No repository exists: use starter-catalog only to investigate/propose candidates.
Client owns repo creation/registry. Scaffolding in an established clone is planned
here and implemented by OpenCode, never handwritten by Engineer. An empty remote
without a PR base is a real bootstrap blocker; do not push default to hide it.
