# Resident sessions — the default for heavy work

A resident session is a persistent `hermes -p <profile> chat` conversation.
For new work, use `specialist_call(target, message, kind="work")` and keep its
`conversation_id`; send follow-ups with that id and the same target. Use
`specialist_session(action="status"|"list"|"close")` for your originating
session's conversations, `wait` and `cancel` for parallel work and stopping a
turn (see "Parallel conversations, waiting and cancelling"); `reconcile`
additionally inspects abandoned resident transport as described below. Short consultations use `kind="inquiry"`, which
selects a configured A2A peer when available. Metered work is never inquiry.
The route stays pinned; never retry an unknown result or switch its backend.

The plugin retains the initial request without truncation and records each
agent request separately. Its runtime handoff header distinguishes your message
from direct human input; it does not authenticate a human approval. In follow-ups,
separate the user's actual decision (source, affected proposal and scope), your
implementation choice and an unapproved suggestion. Preserve original purpose,
audience, must-keep conditions and consumed grants. Do not rewrite them to make
a restricted implementation look acceptable, or renew an old grant on resume.

The original wrapper remains for pre-existing keys and explicit maintenance;
do not adopt a key into the plugin by guessing its owner:

```
~/.hermes/profiles/assistant/scripts/resident-session.sh \
    start <key> --profile <name> [--topic "<t>"] (-q "<brief>" | -f <file>)
resident-session.sh send  <key> (-q "<msg>" | -f <file>) [--image <path>]
resident-session.sh status [<key>] | list [--open|--all]
resident-session.sh close <key> [--note "<n>"]
resident-session.sh prune [--older-than <days>] [--yes]
```

## Mechanics

- **Let the plugin choose the execution lifetime.** Verified live Telegram
  and Discord calls return an accepted job and later completion notification.
  CLI and nested resident calls wait synchronously with the resident deadline;
  do not promise notifications there. A2A inbound allows only synchronous peer
  inquiries and rejects work before launch; reissue work through resident.
  For old keys on live messaging only, use terminal background execution with
  `notify_on_complete`. The gateway watcher still polls every five seconds.
- **Key = `<topic>-<profile>[-<purpose>]`** (e.g. `12116-video-creator-pv`).
  One live session per key; turns are serialized per key by the wrapper
  (busy → exit 75: wait for the in-flight notification instead of
  retrying). The wrapper re-captures the session id every turn, so
  compaction never strands a key.
- **The session cannot see this chat.** The first turn carries a
  self-contained SessionBrief:

  ```text
  Goal: <outcome and beneficiary — one short paragraph>
  Context: <the settled decisions and taste signals from the chat that
            the specialist needs; paste, don't reference>
  Inputs: <paths, URLs, pasted data, reference images via --image>
  Deliverable: <format, language, length; where to write files — always the
               job's one draft directory, e.g.
               ~/Workspaces/Projects/<Group>/.agent/<YYYYMMDD>-<job>/;
               use ~/Workspaces/.agent/<YYYYMMDD>-<job>/ only when no single
               Group owns the work>
  Constraints: <scope limits, deadlines, things NOT to do>
  <grant lines when relevant — see below>
  ```

  After the first turn the session accumulates its own context;
  follow-up turns are ordinary conversation ("C2の本を開いた状態に",
  "最後2秒は開眼で").
- **Grants live in the conversation.** State them in the brief and expand
  them in later turns; the session log is the record:
  - `Budget:` (hands) — generation-spend caps; omitted = the leaf's
    documented default.
  - Engineer: explicit implementation approval releases the agreed scope through
    task-branch PR delivery; Issue management requires a separate explicit request.
    Planning consent or an Issue URL is not a write grant. No merge/deploy/default
    push; no per-phase release loop after the user approves implementation.
  - Marketing remote-save consent names the exact content/assets, service/account
    and create/update target before typing (autosave is an upload); you save,
    Marketer only advises. No Publish/P1
    grant enables publication, scheduling or sending; the user publishes.
- **Deliverables are files at durable paths + a reply that names them.**
  Engineering normally delivers a PR and evidence; plan/assessment replies need
  no invented file or Issue merely to fit the production-artifact convention.
  Sessions must never leave results only in scratch dirs or tool caches.
- **Lifecycle: close on acceptance.** A resident session is per-
  deliverable, not immortal — `close` it once the user accepts, so
  context rot never accumulates. A follow-up request after close starts a
  fresh session, seeded with the canonical keeper or the user's accepted
  chat attachment rather than cleaned staging.
- **Clean on acceptance, not promotion.** Producer-verification promotion
  removes only reproducible caches; variants and useful intermediates
  survive until acceptance. Once accepted, move any canonical keepers to
  the Group's typed surfaces, clear the job's scratch and delivery staging,
  then close the session. Durable notes remain.
- **Failure handling** — a nonzero turn or timeout: inspect the returned
  status, exit code, and resident log. An unknown result is not proof that
  execution stopped: never retry it, close it, or dispatch a replacement
  automatically. Inspect outputs, child jobs and external effects first. For a
  plugin-owned resident, `specialist_session(action="reconcile", conversation_id=...,
  evidence=...)` requires a recorded dead process group and no live, foreign or
  unverifiable shell lock. A lock naming that same dead group stays as evidence,
  never removed. It records `interrupted`, keeps effects `unknown`, and never permits
  continuation of WORK in that conversation. Closing it is bookkeeping, not acceptance.
  Missing handles/locks need separate investigation; A2A has no local liveness
  proof and remains blocked. The evidence text is your report, not proof of
  external completion. Do not signal stored PIDs or steal locks. If a
  session has gone incoherent (context rot), close it and start a fresh
  one seeded with the surviving artifacts — never fight a rotten session.
  Read the exit code first: **75** the key is busy (wait for the in-flight
  notification), **124** the turn was killed at `TURN_TIMEOUT` — the log
  now holds its partial output and stderr tail; **143** means INT/TERM
  interruption with `status: interrupted` and retained partial logs/session
  identity, not confirmed completion. Anything else is the
  CLI's own status. A plugin conversation you cancelled is different: its
  `cancelled` status already carries the runner's confirmation and may be
  continued as described in "Parallel conversations, waiting and cancelling".
- **Reconcile turn after an interruption (Engineer).** An interrupted Engineer
  conversation usually still owns OpenCode child runs whose records only THAT
  resident session can reconcile; left alone they hold the worktree
  indefinitely, and no other route (a fresh conversation, the terminal, a
  `--resume`) is accepted as owner. After `specialist_session reconcile`, send
  exactly one `specialist_call(conversation_id=<same>, kind="reconcile",
  message=<which child conversations to inspect>)`. The plugin marks the turn
  RECONCILE-ONLY: Engineer inspects and reconciles, `opencode_call` is refused,
  nothing is edited or committed, and the conversation ends `reconciled`. Then
  release the remaining work as a fresh conversation seeded with the committed
  checkpoint and the evidence paths — not with the interrupted transcript.
- **Turn budget is 90 minutes and the handoff says so.** Every resident turn
  carries a "Turn budget" line; the specialist is expected to checkpoint
  before it. Your side of that contract is turn sizing: release one
  verifiable increment per turn and continue in the same conversation, rather
  than one turn that must reach the finish line. Engineer's OpenCode calls
  block until they finish (no polling), so a turn's wall clock is roughly the
  sum of its runs plus verification — plan for that.
- **A key whose first turn died never established a conversation.** Its
  following wrapper restart procedure is for explicit maintenance after effects
  are reconciled, not a bypass for an unknown specialist conversation. Its
  registry entry has an empty `session_id`; `send` refuses it and says so.
  Re-run `start` on the SAME key with the brief to restart it in place
  (`created_at` is kept, `restarts` counts the attempts). This replaces the
  old close-and-pick-a-new-name dance. `start` still refuses a key that
  does own a session id — that one is live, so `send` or `close` it.
- **Housekeeping** — `list` shows open keys newest-first and hides closed
  ones (`--all` to see them). Once closures pile up, `prune` archives the
  long-closed entries into `resident-sessions/archive/` with their logs
  gzipped; it only lists until you pass `--yes`.

## Parallel conversations, waiting and cancelling

- **Parallel = separate conversations.** Independent units (e.g. three Writer
  drafts to compare) each get their own `specialist_call(kind="work")` with a
  shared `group` label and a distinct output path in each brief. At most four
  run at once per chat; one conversation never takes a second turn while busy.
  Nothing here widens a grant: N parallel drafts spend N times, so the release
  must cover that.
- **Collect a comparison in one message.** After launching, call
  `specialist_session(action="wait", group=<label>)` in the same turn. It waits
  up to 15 minutes without spending turns. All settled: compare and reply once.
  Limit reached: reply once that the drafts are in progress, then answer each
  following completion notification of that group with `[SILENT]` until its
  `group_progress` shows nothing pending, and only then send the comparison.
  A notification for a conversation you already reported is also `[SILENT]`.
- **A new user message during a wait** releases the wait (`released_by`); the
  specialists keep running. Answer the message; do not cancel unless asked.
- **"Stop it" / "stop B and change X"** means `specialist_session(action=
  "cancel", conversation_id=<B>)`. It waits up to 25 s for the stop. If it
  returns `cancelled`, send the correction in the SAME turn with
  `specialist_call(target, conversation_id=<B>, message=<correction>)`, so the
  user gets one reply (the correction is a new released turn: same scope and
  grants, never a widened one). The specialist resumes its own session and is told the
  step in flight may or may not have taken effect. Other conversations keep
  running. If the reply is still `running` (stop not confirmed), say so and do
  not resend; check `status` before acting. A `completed` reply with
  `cancel_too_late` means the turn had already finished: show that result and
  ask whether the change still applies. `cancelled` confirms only the
  specialist's own process. Engineer's OpenCode runs and the hands'
  conversations are stopped by their own runners when it exits, possibly a few
  seconds later, and end as `unknown` on their side, so the resumed turn first
  inspects and reconciles them. Spend already incurred is not refunded.
- **"What is running?"** answers from `specialist_session(action="list")`:
  target, status and `elapsed_seconds` per conversation.
- `/stop` hard-stops the specialists launched in that turn. Check `list`
  afterwards: a `cancelled` one can be resumed as above; one left `running` or
  `unknown` (the reaper killed it before the stop was recorded) needs inspection
  and `reconcile`, never a resend.

## Revision escalation

When a deliverable fails your QA and the fix is not a mechanical
re-render, do NOT restart from scratch: reuse (or open) the capability's
resident session seeded with the artifact paths + itemized defects, and
iterate there.
