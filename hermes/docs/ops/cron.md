# Cron — tracked jobs

Hermes design docs — index: [`../../PROFILES.md`](../../PROFILES.md).

A scheduled job that should outlive the machine it was typed on is a
**directory**, `profiles/<profile>/cron.d/<name>/`, in the repository that
owns it (this one for a neutral job, the private overlay for a personal one).
Hermes' own store, `~/.hermes/profiles/<profile>/cron/jobs.json`, is derived
from those directories by `scripts/cron-sync.py` and is never edited by hand
or tracked (why: [tracking.md "Cron"](tracking.md#cron)).

## A job directory

```
cron.d/<name>/
  job.yaml     what Hermes should do and when
  run.sh       the script, when the job has one (executable; honoured shebang)
```

The job's name is the directory name (`[a-z0-9][a-z0-9._-]*`); `job.yaml`
never repeats it. Nothing else lives in the directory. `job.yaml`:

| Key                          | Meaning                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schedule`                   | A Hermes schedule: cron expression, `every monday 9am`, interval (`30m`), or an ISO timestamp for a one-shot. Never `in 30m` (it re-derives on every sync). A job fired only by a webhook ([webhook.md](webhook.md)) keeps `0 0 29 2 *`: a paused job cannot be fired, and a one-shot completes after its first run.                                                                                         |
| `mode`                       | `no_agent`: `run.sh` **is** the job; empty stdout is silent, non-empty stdout is delivered, a nonzero exit is a failure notice. `prompt`: a model turn with `prompt` / `skills`; `run.sh`, when present, runs first and its stdout joins the prompt. `monitor`: `run.sh` (or `monitor_url`) runs first and the model is woken only when its output changed since the last tick, with the diff in the prompt. |
| `prompt`, `skills`           | The model's instruction and the skills loaded before it (`prompt` and `monitor` only; one of them is required). A plugin skill is named `<plugin>:<skill>`; a private technic by its name.                                                                                                                                                                                                                   |
| `deliver`, `failure_deliver` | Hermes' delivery grammar: `telegram` (the Inbox topic), `telegram:<chat>:<thread>`, `local`, … Default `local`.                                                                                                                                                                                                                                                                                              |
| `repeat`                     | Fire this many times, then complete.                                                                                                                                                                                                                                                                                                                                                                         |
| `paused`                     | `true` creates or holds the job paused; `false` resumes one; absent leaves a hand pause alone.                                                                                                                                                                                                                                                                                                               |
| `monitor_url`                | `monitor` only, instead of `run.sh`: a URL Hermes fetches itself.                                                                                                                                                                                                                                                                                                                                            |
| `workdir`                    | The script's working directory (absolute).                                                                                                                                                                                                                                                                                                                                                                   |
| `attach_to_session`          | `prompt` / `monitor`: a delivery to a thread-capable chat opens a thread of its own for the run and seeds it with the brief, so a reply there continues with context. Needs a delivery with no fixed thread (`telegram:<chat>`, not the bare `telegram` of the Inbox).                                                                                                                                       |
| `thread_title`               | The name of that thread (one line; default `Hermes — <name>`). A run's own output overrides it with one `[TITLE: …]` line, stripped before delivery — the way an event-fired job titles its thread from what it found. A local patch of the runtime (`fix/cron-thread-title`).                                                                                                                               |

Everything else a job record holds (run state, counters, output, who created
it) is Hermes' and is never written by the sync. The agent-only keys
(`context_from`, `enabled_toolsets`, `attach_to_session`, `thread_title`) are
refused on a `no_agent` job.

### The script and its profile

Hermes runs only a script inside `<HERMES_HOME>/scripts/`, by real path, so
`run.sh` is reached through a wrapper cron-sync generates at
`scripts/cron/<name>.sh`. The wrapper exports the owning profile's home as
`HERMES_HOME` and execs `$HERMES_HOME/cron.d/<name>/run.sh` — the link, so
no checkout path is written anywhere and a moved checkout needs only the
installer's relink. A `run.sh` reads its profile from `$HERMES_HOME` and
finds code by its own real path (`cd "$(dirname "$0")" && pwd -P`, which
resolves the link into the repository, never into a profile). Changes to
`run.sh` apply at the next tick; nothing is copied.

## cron-sync

`bin/hermes-python hermes/scripts/cron-sync.py [--profile <p> | --home <dir>] [sync|validate|adopt|…]`
(`install.sh` runs `sync` for every profile at its end; the Hermes runtime's
own cron API does the writes, under its lock).

For each manifest the sync keeps exactly one job carrying
`managed: {manifest, source, synced_at}`:

- missing → created; definition fields differ (a manifest edit, or a hand
  edit with `hermes cron edit`) → rewritten to the manifest; `source` changed →
  restamped. The job id, counters and output survive.
- the manifest is gone → the job is **paused** with reason
  `cron-sync: manifest removed` and listed as such by `hermes cron list`; its
  output and notepad stay. `--prune` removes such orphans instead. Restoring
  the directory resumes the job.
- a job **without** the marker is never touched (the Assistant's own jobs,
  anything created by hand). One that shares a manifest's name is a
  **conflict**: the sync reports it and skips that manifest until
  `cron-sync --profile <p> adopt <name>` stamps the marker on the existing
  job (its history continues) — never automatically.
- a manifest that fails validation is reported by name and its job, if any, is
  left exactly as it was: a typo never pauses a running job.

`--check` prints what a sync would do and exits 1 when anything is pending or
broken, writing nothing; `verify-work-continuity.py` runs it so a cutover
starts from a store that matches its links. `validate` loads every manifest
and touches no job.

## Public, private, local

The three places a job can come from differ only in **where the directory
is**; cron-sync and Hermes see one `cron.d/`:

| Job                                                         | Directory                                | Arrives in `~/.hermes/profiles/<p>/cron.d/` as |
| ----------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------- |
| neutral, tracked here                                       | `hermes/profiles/<p>/cron.d/<name>/`     | a link (`install.sh`)                          |
| personal, tracked in the private overlay                    | its `hermes/profiles/<p>/cron.d/<name>/` | a link (the overlay's `install.sh`)            |
| the profile's own (a reminder it was asked for, a one-shot) | written by the profile                   | a real directory (`source: local`)             |

Promotion of a local job into a repository is the `learned/ → technic/` move
([tracking.md "Tracked vs ignored"](tracking.md)): copy the directory into the
repository, delete the real one, run `install.sh`. The link takes its place,
the job is restamped `repo`, nothing else changes. Until the real directory is
deleted, `install.sh` warns that it will not overwrite it — that warning is the
signal.

A profile adds or removes its own jobs through `cronjob_manage`, the tool it
has always used: the `guards/cron-manifests` plugin replaces the built-in one
under the same name and schema ([plugins.md "Guards"](plugins.md#guards)), so
`create` writes the directory and derives the job, `update` rewrites it,
`remove` deletes it with the job, and a repository's job is refused with a
message that names the repository. A script the agent names (a path under the
profile's `scripts/`, as the runtime takes it) is run from a generated
`run.sh`. The same is possible by hand with `cron-sync add` / `remove` (the
`add` spec is JSON on stdin); nothing ever writes `jobs.json` directly. A
one-shot that has fired is cleared, with its directory, by
`cron-sync prune-completed`. What the Assistant tells the user about each
kind: the `cron.md` reference of its Chat pipeline.

## Cutover from hand-registered jobs

A job that was created with `hermes cron create` before its manifest existed
is adopted, not recreated: back up `jobs.json`, run `install.sh` (the sync
reports the conflict), `cron-sync --profile <p> adopt <name>` for each, run
`install.sh` again (the definitions are brought to the manifests). Hermes
reads `jobs.json` on every tick, so no gateway restart is needed for the jobs
themselves.
