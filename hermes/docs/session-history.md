# Session history

Read-only history of the AI tools actually in use — OpenCode and Hermes — for
reports and everyday checks. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                         | Home                                            | Reader              |
| ----------------------------------------------------------------------------- | ----------------------------------------------- | ------------------- |
| Shared contract: windows, opt-in fields, interval arithmetic, result envelope | `plugins/session-history/common.py`             | both readers        |
| OpenCode reader and `opencode_history`                                        | `plugins/opencode/history.py`                   | Engineer, Assistant |
| Hermes reader and `hermes_history`                                            | `plugins/session-history/hermes.py`             | Engineer, Assistant |
| Cross-tool summary, text output, `/activity`                                  | `plugins/session-history/cli.py`, `__init__.py` | people, cron        |
| Launcher                                                                      | `../bin/ai-history`                             | people, cron        |

Each reader owns its sources and what a session is; the common module owns only
what must mean the same in both. They are stdlib modules loaded by path, so the
Hermes tools, the `ai-history` launcher and cron run the same code. Only two
tools are covered on purpose: others are not in regular use.

Every result carries `source`, `status` (`complete` / `partial`) and
`diagnostics`; a `partial` diagnostic means a figure is missing or undercounted,
never estimated. Windows are half-open `[from, to)`: dates are local midnight of
`timezone`, `days=N` is the last N local days ending today. Titles and costs
only on request; message content, prompts, tool input/output and messaging
identities never.

## Activity, not work time

A session's start→last-activity span includes idle and resumed gaps, so it is
never reported. Activity is the time the agent was running — model output and
tool execution — minus waits for a person's answer (`question` in OpenCode,
`clarify` in Hermes), which otherwise count a question left open overnight as
hours of work. A tool held on a permission prompt is not visible and still
counts. `active_union_seconds` removes overlap between parallel sessions and,
in the summary, between the two tools. Nothing here observes human working
time. `usage` includes archived sessions by default — archiving hides a
session, it does not undo the work.

## OpenCode reader

It reads OpenCode's own sessions across every project and never touches the
execution side (`opencode-sessions/`, grants, `opencode_cli`).

- **Official API first.** It asks the person's shared OpenCode 2 service
  through the documented `opencode api` command (which finds or starts the
  service and authenticates like the TUI; output goes to files, because a
  piped reply is cut off at a buffer boundary with exit status zero). It lists
  through `/api/session`, newest-updated first, following the cursor until a
  session predates the window; the API reports no version or change summary
  per session.
- **Database only where the API cannot answer.** `usage` needs message-level
  model, tokens and step times, which the API returns only with message content,
  so it reads the database (`opencode debug paths db`) read-only in one
  snapshot, selecting scalar JSON paths only, from OpenCode 2's
  `session_v2`/`session_message` (tool calls sit inside the assistant message);
  a file without them is unavailable. OpenCode 2 imports V1 steps with their
  completion and tool times set to the V1 row's last update, so while the
  imported V1 tables remain, an imported step's V1 record supplies its times.
  list/get/children fall back to the database only in `auto` and say so
  (`api-unavailable`). A missing required column fails closed; the internal
  schema has no compatibility promise.
- Activity is the union of assistant step intervals (tool execution sits inside
  a step) minus `question` tool waits.

## Hermes reader

It reads every profile's `state.db` under the Hermes root (`HERMES_ROOT`, else
derived from `HERMES_HOME`, else `~/.hermes`), including `default`.

- **Hermes' own store first.** list/get/children open each profile through
  `SessionDB(read_only=True)`, the attach Hermes provides for cross-profile
  aggregation (no schema init, no write lock); it owns compression lineage and
  hidden/archived semantics. Without Hermes' Python (plain `python3`), a guarded
  read-only SQLite route answers and says so.
- **One profile at a time.** A profile whose database cannot be read is left out
  and disclosed (`profile-unreadable`, partial); the others still answer.
- A compression continuation is the same conversation, so it is kind `root`;
  only branch, delegate and tool children are `child`.
- An inbound A2A request is refused in code as well as by toolset.
- **usage reads scalar columns directly**, because Hermes has no windowed usage
  API: message role, timestamp and tool name, and `session_model_usage`.
- **Activity** is the gap before each model reply or tool result (the agent
  working); a gap ending at a user message is the person away. Events are
  merged per conversation (a compression chain), because compression copies the
  kept tail into the continuation with its original timestamps; duplicates and
  synthetic compression-summary rows count once. A day either side of the window
  is read so gaps crossing its edges are clipped, not lost. `clarify` results are waits.
  `opencode_call` and `specialist_call` waits stay in activity (the caller did
  wait) and are also reported as `opencode_wait_seconds` /
  `specialist_wait_seconds`, because the callee's own session counts the same
  time; the cross-tool summary's union removes that overlap.
- **Tokens** come from per-model usage records (`first_seen`..`last_seen`). A
  record spanning a window edge cannot be split, so it is excluded and
  disclosed (`usage-crosses-window`, with its output tokens) — long resident
  sessions make this common for short windows.

## Everyday use

- `ai-history` — today's activity for both tools, overlap removed;
  `--days 7`, `--from/--to`, `--json`.
  `ai-history hermes|opencode list|get|children|usage` reach each reader with a short table. The launcher
  runs on Hermes' interpreter (read from the real `hermes` launcher's shebang)
  so the Hermes reader can use `SessionDB`.
- `/activity [today|week|month|N]` in Engineer and Assistant sessions (Telegram
  included) returns the same summary without a model turn, as plain Markdown:
  a per-tool table, then each tool's breakdown and the notes folded in
  `<details>`. Chats with Telegram rich messages render the tables and folds.
  `/history` is a Hermes built-in, hence the name.
- The tools are enabled per profile: plugin `session-history`, toolset
  `session_history` (never on `a2a`). Registration is limited to Engineer and
  Assistant in code as well.
