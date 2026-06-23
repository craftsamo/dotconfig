<ScenarioPlaybook name="rebuild-migration">
<UseWhen>

Apply on top of the general spine in `SKILL.md` when the task is a full rebuild,
restructure, schema/architecture/layout overhaul, or data migration.

</UseWhen>

<IntentCheck>

Confirm improve-in-place vs rebuild-from-scratch explicitly. They yield very
different plans. If the system was built opaquely and is not understood,
co-design the rebuild so the user regains ownership.

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
</ScenarioPlaybook>
