---
name: approach-rebuild-migration
description: >-
  Use for a full rebuild, restructure, or schema/data migration — overhauling
  architecture, moving data, or rebuilding an opaque system (再構築, 作り直し,
  マイグレーション, rebuild, migrate, restructure, overhaul). Includes the
  evacuate → build-alongside → cutover safety sequence. For incremental
  behavior-preserving cleanup, use `approach-refactor`.
---

<Goal>

Handle a full rebuild, restructure, schema/architecture/layout overhaul, or
data migration without losing data or breaking the live system.

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

<IntentCheck>

Confirm improve-in-place vs rebuild-from-scratch explicitly. They yield very
different plans. If the system was built opaquely and is not understood,
co-design the rebuild so the user regains ownership. Incremental,
behavior-preserving structural cleanup is `approach-refactor`, not this skill.

</IntentCheck>

<AntiPatterns>

- Do not rewrite in place as a big bang; build alongside and cut over.
- Do not mix behavior changes into the migration — move first, change later.
- Do not retire the old system before the new one has soaked in real use.

</AntiPatterns>

<Steps>

1. Evacuate: back up live data and export a human-readable copy. Establish at
   least one recovery point.
2. Define the new: design schema/structure on the side, version it, and do not
   apply it to the live thing yet.
3. Build alongside: implement the new engine/tooling against a separate copy;
   keep the live system intact.
4. Migrate / transform: map old -> new explicitly. Flag ambiguous cases for
   review with sentinels and needs-review markers instead of guessing.
5. Verify and reconcile: counts, totals, round-trip export/import, validation;
   new vs old must reconcile.
6. Cut over only after verification and explicit approval. Define how to roll
   back before flipping; keep the old as a recovery point.
7. Sync and clean up: update docs/config to the new shape; retire/stash the old.

</Steps>

<Gates>

- [ ] Recovery points exist, including backup + human-readable export, before
  any change.
- [ ] New built on a copy; live untouched until cutover.
- [ ] Migration maps old -> new; ambiguous cases flagged, not guessed.
- [ ] Reconciled counts, totals, round-trip, or validation vs old.
- [ ] Explicit approval before the irreversible cutover.
- [ ] Docs/config synced; old kept as a recovery point.

</Gates>
