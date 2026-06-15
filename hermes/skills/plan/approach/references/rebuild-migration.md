# Scenario: rebuild & migration

Apply on top of the general spine in `SKILL.md` when the task is a full rebuild,
restructure, schema/architecture/layout overhaul, or data migration.

## Extra intent check
Confirm **improve-in-place vs rebuild-from-scratch** explicitly — they yield very
different plans. If the system was built opaquely and isn't understood, co-design the
rebuild so the user regains ownership.

## Safe execution phases
1. **Evacuate** — back up live data + export a human-readable copy (establish ≥1 recovery point).
2. **Define the new** — design schema/structure on the side; version it; don't apply to the live thing yet.
3. **Build alongside** — implement the new engine/tooling against a *separate* copy; keep the live system intact.
4. **Migrate / transform** — map old → new explicitly; flag ambiguous cases for review
   (sentinels + needs-review) instead of guessing.
5. **Verify & reconcile** — counts, totals, round-trip export/import, validation; new vs old must reconcile.
6. **Cut over** — only after verification + explicit approval; keep the old as a recovery point.
7. **Sync & clean up** — update docs/config to the new shape; retire/stash the old.

## Gates
- [ ] Recovery points exist (backup + human-readable export) before any change
- [ ] New built on a copy; live untouched until cutover
- [ ] Migration maps old→new; ambiguous flagged, not guessed
- [ ] Reconciled (counts / totals / round-trip / validate) vs old
- [ ] Explicit approval before the irreversible cutover
- [ ] Docs/config synced; old kept as a recovery point
