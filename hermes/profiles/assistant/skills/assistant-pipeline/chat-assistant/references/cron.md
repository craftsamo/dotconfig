# Recurring requests — cron registration

For "every morning do X", "weekly digest of Y", register a cron job
inline:

- Use the appropriate profile's cron
  (`hermes/profiles/<name>/cron/jobs.json`). Most recurring jobs belong on
  `assistant` (which hosts the gateway and runs cron continuously).
- The job body should reference the workspace skill it performs. Heavy work
  that a job starts runs in a resident specialist session like any other.
- Time-deferred one-off work ("do X on <date>") is a one-shot cron job, never
  a note in chat memory.
- Confirm the schedule with the user via `clarify` before registering.

## Job scripts you write

A cron job only runs a `script` / `monitor_script` that resolves inside
`~/.hermes/profiles/assistant/scripts/`, and that directory is tracked
config. A script you write for one job is throwaway, so:

- Create it in `~/.hermes/profiles/assistant/scripts/adhoc/` (create the
  directory if missing). That subdirectory is ignored by Git.
- Reference it relative to `scripts/`: `adhoc/<name>.py` or
  `adhoc/<name>.sh` (`.sh` runs with bash, anything else with Python).
- Keep its state outside `scripts/`, e.g.
  `~/.hermes/profiles/assistant/cron/<name>.json`.
- When you remove the job, delete its `adhoc/` script and state file too.
- Never put a new file directly in `scripts/`; the scripts there are
  maintained through the repository, not created by a job.
