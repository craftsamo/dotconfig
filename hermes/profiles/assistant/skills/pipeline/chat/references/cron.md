# Recurring requests — cron registration

For "every morning do X", "weekly digest of Y", register a cron job
inline with `cronjob_manage`:

- Most recurring jobs belong on `assistant` (which hosts the gateway and
  runs cron continuously). The job body should reference the workspace skill
  it performs. Heavy work that a job starts runs in a resident specialist
  session like any other.
- Time-deferred one-off work ("do X on <date>") is a one-shot cron job, never
  a note in chat memory.
- Confirm the schedule with the user via `clarify` before registering, and
  give the job a short `name`: it becomes the job's directory.

## Where a job lives

A job you create is a directory `~/.hermes/profiles/assistant/cron.d/<name>/`
(`job.yaml`, and `run.sh` when it runs a script); the tool writes it and
derives the job from it. `list` shows every job, with a `managed` field on the
ones that have a directory:

- `source: local` — yours: `update`, `pause`, `resume`, `remove` work as
  before. `remove` deletes the directory with the job.
- `source: repo` — tracked in a repository (the directory is a link): the tool
  refuses to change it. Tell the user it is a tracked job; they change its
  `job.yaml` in the repository and run the installer.
- no `managed` — made before jobs had directories: it can be paused or
  removed, not updated. To change one, remove it and create it again.

A job keeps its name: to rename one, remove it and create it again.

## A job that opens its own topic

Create it with `attach_to_session: true` and `deliver: telegram:<chat id>`
(the chat, no thread): each delivery then opens a new Telegram topic, seeded
with the brief, and a reply there continues with context. A bare
`deliver: telegram` goes to the Inbox topic instead and opens none. The
topic is named `Hermes — <name>` unless the run's output contains one line
`[TITLE: …]` (stripped before delivery): put one there when the run knows a
better name than the job does ("Dependabot #12 critical: lodash").

Webhooks are not yours to register: a route that fires a job is a tracked
`webhook.d/` directory in a repository, and the job it names keeps a schedule
that never comes round (`0 0 29 2 *`), never `paused` (an event cannot fire a
paused job).

## Job scripts you write

A job's `script` (or `monitor`) is a path inside
`~/.hermes/profiles/assistant/scripts/`, and that directory is tracked
config. A script you write for one job is throwaway, so:

- Create it in `~/.hermes/profiles/assistant/scripts/adhoc/` (create the
  directory if missing). That subdirectory is ignored by Git.
- Reference it relative to `scripts/`: `adhoc/<name>.py` or
  `adhoc/<name>.sh` (`.sh` runs with bash, anything else with Hermes'
  Python). The job's `run.sh` is generated to run it; never edit `run.sh`.
- Keep its state outside `scripts/`, e.g.
  `~/.hermes/profiles/assistant/cron/<name>.json`.
- When you remove the job, delete its `adhoc/` script and state file too
  (the job's own directory goes with the job).
- Never put a new file directly in `scripts/`; the scripts there are
  maintained through the repository, not created by a job.
