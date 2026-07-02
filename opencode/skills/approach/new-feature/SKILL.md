---
name: approach-new-feature
description: >-
  Use when adding a feature or capability to an existing system — extending
  behavior and wiring a new path into existing code (機能追加, フィーチャー追加,
  add feature, extend, enhance). Apply on top of the `approach` spine with an
  existing-system integration playbook.
---

<Goal>

Add a capability to an existing system. Apply this on top of the `approach`
spine (load it first if not already in context): investigate → confirm the
real goal → co-design one decision at a time → proceed in small reversible
verified steps.

</Goal>

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

</Steps>

<Gates>

- [ ] Existing patterns/conventions followed.
- [ ] Footprint mapped; each entailed piece explicitly in or out of scope.
- [ ] Creep deferred to follow-ups.
- [ ] Tests added or updated; project checks pass.
- [ ] No nearby regressions.

</Gates>
