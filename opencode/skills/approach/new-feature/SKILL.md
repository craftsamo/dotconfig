---
name: approach-new-feature
description: >-
  Use when adding a feature or capability to an existing system — extending
  behavior and wiring a new path into existing code (機能追加, フィーチャー追加,
  ここに追加, add feature, add support for, extend, enhance). Investigate the
  system first, confirm the real goal, co-design one decision at a time, then
  integrate in small verified steps. Do NOT use for bug fixes (that is
  debug/debugger work) or trivial single-step edits.
---

<Goal>

Add a capability to an existing system by integrating with its existing
patterns and seams, keeping the user in control of every scope decision.

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

- Do not build a parallel new pattern when an existing seam fits — integrate.
- Do not silently expand beyond the agreed scope; surface new needs as
  follow-ups.
- Do not ship the happy path while ignoring the feature's entailed footprint
  (permissions, errors, data migrations).
- Do not pull in a new dependency without flagging it as a decision.

</AntiPatterns>

<Steps>

1. Understand the existing system:
   - Find the relevant areas and the existing patterns/conventions to follow.
   - Identify the seams where the feature plugs in; read nearby tests.
2. Design the smallest change:
   - Map the footprint first: what the feature entails beyond the ask — data,
     UI, permissions, background jobs, notifications, config, migrations,
     docs — and make each explicitly in or out of scope.
   - Prefer the minimal, idiomatic change that fits existing patterns over a
     parallel new way.
   - Defer scope creep to follow-ups.
3. Implement and integrate:
   - Build incrementally; keep the system working at each step.
   - Wire in at the identified seams; reuse existing helpers/abstractions.
4. Verify:
   - Add or extend tests; run the project's build/lint/test checks before
     claiming done.
   - Confirm no regressions in adjacent behavior.
5. Close the loop: summarize what was added, how it integrates, and the
   deferred follow-ups.

</Steps>

<Gates>

- [ ] Real goal confirmed with the user before designing.
- [ ] Existing patterns/conventions followed.
- [ ] Footprint mapped; each entailed piece explicitly in or out of scope.
- [ ] Creep deferred to follow-ups.
- [ ] Tests added or updated; project checks pass.
- [ ] No nearby regressions.

</Gates>
