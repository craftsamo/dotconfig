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
4. Align on a concise plan before heavy or irreversible work. Persist durable
   or cross-session plans via `approach-github-projects`, not local TODO files.
5. Execute in small reversible verified steps; checkpoint before anything
   irreversible.
6. Close the loop — summarize what changed and what remains.

</Method>

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
