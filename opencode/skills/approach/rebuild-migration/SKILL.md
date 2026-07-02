---
name: approach-rebuild-migration
description: >-
  Use for a full rebuild, restructure, or schema/data migration — overhauling
  architecture, moving data, or rebuilding an opaque system (再構築, 作り直し,
  マイグレーション, rebuild, migrate, restructure, overhaul). Includes the
  evacuate → build-alongside → cutover safety sequence. For incremental
  behavior-preserving cleanup, use `approach-refactor`. Apply on top of the
  `approach` spine.
---

<Goal>

Handle a full rebuild, restructure, schema/architecture/layout overhaul, or
data migration. Apply this on top of the `approach` spine (load it first if
not already in context): investigate → confirm the real goal → co-design one
decision at a time → proceed in small reversible verified steps.

</Goal>

<IntentCheck>

Confirm improve-in-place vs rebuild-from-scratch explicitly. They yield very
different plans. If the system was built opaquely and is not understood,
co-design the rebuild so the user regains ownership. Incremental,
behavior-preserving structural cleanup is `approach-refactor`, not this skill.

</IntentCheck>

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
6. Cut over only after verification and explicit approval. Keep the old as a
   recovery point.
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
