# Recurring requests — cron registration

For "every morning do X", "weekly digest of Y", register a cron job
inline:

- Use the appropriate profile's cron
  (`hermes/profiles/<name>/cron/jobs.json`). Most recurring jobs belong on
  `assistant` (which hosts the gateway and runs cron continuously).
- The job body should reference the workspace skill or the catalog card
  dispatch it performs — a cron-originated card follows
  `../execute/kanban-lite.md` like any other.
- Confirm the schedule with the user via `clarify` before registering.
