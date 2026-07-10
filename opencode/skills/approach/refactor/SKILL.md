---
name: approach-refactor
description: >-
  Use when improving structure without changing behavior — refactor, reorganize,
  clean up, extract, rename, or simplify under a test safety net in small
  behavior-preserving steps (リファクタリング, 整理, リファクタ, refactor,
  restructure code, clean up, extract method, rename). Behavior must stay
  identical. For wholesale rebuilds or data migration, use
  `approach-rebuild-migration`.
---

<Goal>

Improve the structure of working code without changing its behavior. If the
system or its data is being replaced or moved wholesale, use
`approach-rebuild-migration` instead.

</Goal>

<Method>

Non-trivial work runs through this spine; do not jump straight to edits:

1. Investigate before asserting — read the relevant code, files, and history
   first.
2. Confirm the real goal — mirror it back instead of designing from
   assumptions. Do not ask what investigation can answer; take the recommended
   default on low-risk details and report it.
3. Co-design one decision at a time — widen to the realistic candidates (not
   just two straw options), present tradeoffs with a recommendation, and let
   the user decide.
4. Align on a plan shaped backward from the goal at fixed granularity:
   Goal (acceptance criteria — how we know it is done) → sub-goals (each an
   independently verifiable, reviewable-PR-sized increment) → steps
   (commit-sized edit→verify moves). A sub-goal whose verification cannot be
   stated needs further decomposition. Persist durable or cross-session plans
   via `approach-github-projects`, not local TODO files.
5. Hand off to execution: register the agreed plan as todos shaped
   `Phase{N}.{m} - <task> (executor)` — Phase is the dependency wave, {m} a
   reference id within the phase (no ordering implied), executor one of
   Build | worker | reviewer | verifier | debugger | ui-review (default
   Build; worker only for mechanical work) — then switch to Build and
   execute in phase order. The todos are the session's execution queue;
   the board holds the durable plan.
6. Execute in small reversible verified steps; checkpoint before anything
   irreversible.
7. Close the loop — summarize what changed and what remains.

</Method>

<Questioning>

Questions to the user must be answerable in ~30 seconds without opening code:

- Never make a bare file/line reference the subject of a question; summarize
  what that code does in plain language first.
- One question = one decision: context summary in the user's terms (what is
  at stake, why decide now) + options phrased as behavior/outcomes, not
  implementation details + a recommended default.
- If answering would require the user to read code, the question is not
  ready — investigate yourself and present conclusions as options.
- Non-blocking details: proceed on the recommended default and report it.

</Questioning>

<AntiPatterns>

- Do not refactor without a behavior-asserting safety net (tests or a spec).
- Do not mix behavior changes into a refactor — keep the two in separate steps
  or separate commits.
- Do not attempt a large restructure in one move; break it into verifiable
  steps.
- Do not rename or move public API without checking call sites and consumers.

</AntiPatterns>

<Steps>

1. Secure a safety net: confirm existing tests cover the behavior you will
   touch. If coverage is thin, characterize the current behavior with tests
   first — the refactor must keep them green.
2. Define the target structure: name the smell and the intended shape (extract,
   inline, rename, move, simplify). Keep the goal structural, not behavioral.
3. Plan small, behavior-preserving moves: decompose into steps where each
   leaves the system working and the tests green.
4. Execute one move at a time: make the change, run the safety net, commit
   (or checkpoint) before the next move.
5. Verify behavior is identical: run the full build/lint/test suite; confirm
   no public behavior, API, or output changed beyond intent.
6. Close the loop: summarize what moved, why, and what follow-up refactors (if
   any) remain.

</Steps>

<Gates>

- [ ] Behavior-asserting safety net in place before any structural change.
- [ ] Goal is structural only; no behavior change mixed in.
- [ ] Each move left the tests green and the system working.
- [ ] Full build/lint/test suite passes; public behavior/API unchanged.

</Gates>
