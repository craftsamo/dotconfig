# Specialist calls and work continuity

How primaries open, continue and close conversations with specialists and hands
(`plugins/specialist-call`), and what survives a failure. Part of the Hermes
design docs — index: [`PROFILES.md`](../../PROFILES.md). Install/enable steps
live in [`README.md`](../../README.md).

## Specialist calls

The shared `plugins/specialist-call` plugin exposes the `specialist` toolset to
assistant, creator, marketer and engineer; it is their only outbound path (the
raw `a2a_*` tools stay off, see [topology](../topology.md) "Toolsets"). Each
caller has an explicit `specialist_call.resident_targets` allowlist:

| Caller | Targets |
| --- | --- |
| assistant | engineer, creator, marketer, writer; searcher resident-only. Never the hands, never researcher directly |
| creator | its seven configured peers: engineer, marketer, researcher, writer, image-creator, video-creator, audio-creator |
| marketer | engineer, creator, researcher, writer (keeps inbound A2A) |
| engineer | marketer, researcher, writer |

The default CLI flow is unchanged. Short inquiries use an allowed target's
existing `a2a_agents` RPC endpoint when one exists; no endpoint is ever
discovered from model text or a supplied URL. Work always uses the resident script
(`assistant/scripts/resident-session.sh`).

Call `specialist_call(target, message, kind="inquiry"|"work")`, then continue
with the same `target`, the returned `conversation_id` and the next `message`;
route and target stay pinned for the conversation. `inquiry` is for free,
bounded, single-reply requests; `work` is for metered, multi-turn or long work.
Pass purpose/consumer/constraints/budget for Researcher/Searcher framing, or the
explicitly authorized settled brief for execution, and preserve any released
unit, inputs, permissions and grant unchanged. Transport selection grants no
authority or budget. `kind="reconcile"` is the only call an interrupted
conversation accepts — see [engineer.md](./engineer.md) "Resident turns and
reconcile".

`specialist_session` supports `status`, `list`, `wait`, `cancel`, `close` and
`reconcile`, only in the same originating session and profile. The registry and restrictive request
files live under the caller's real Hermes home in `specialist-sessions/`;
resident JSON and logs keep their format in `resident-sessions/`. Old resident
keys stay runnable through the original script; automatic adoption is
unsupported because old entries establish no originating-session owner. Listing
skips revoked targets without hiding other permitted rows.

### Parallel conversations, wait and cancel

Independent conversations run in parallel; one conversation never does (its
lock refuses a second turn). Each originating session may have at most
`specialist_call.max_active` (default 4) conversations accepted or running; a
call over the cap dispatches nothing. An optional `group` label ties a batch
together (one comparison, say) for `wait` and for the `group_progress` in each
completion.

- **Launch.** Messaging callers are always background. A CLI caller passes
  `wait=false` to get the `conversation_id` at once; the runner stays its child,
  so it still dies with a one-shot caller — collect before the turn ends.
  Upstream runs plugin tools one at a time, which is why launch returns rather
  than relying on a parallel tool batch.
- **`wait`** (`conversation_id`, `conversation_ids` or `group`; `mode` all/any)
  blocks without model turns until the work settles, the limit passes, or a new
  user message / interrupt arrives; it never stops a specialist. Its limit is the
  smallest of `specialist_call.wait_timeout`, the request, the caller's tool
  deadline minus 30 s and the inherited resident deadline. On messaging it marks
  the settled runners' completions consumed so they do not come back as extra
  turns (best effort: a notice already queued can still arrive).
- **`cancel`** stops a resident turn and waits up to 25 s for the result. Not yet
  picked up by a runner: cancelled in place, nothing ran. Otherwise it leaves a
  stop request for the runner that owns the turn; only that runner signals its
  group. The runner TERMs the shell once; the shell gives the CLI `KILL_GRACE`
  to flush its transcript and report its session id, records it and exits; the
  rest of the group is killed. The runner treats its own TERM/INT/HUP the same
  way, and a blocking CLI call cancels on a user interrupt (a yield request
  detaches it instead). Gateway `/stop` reaping SIGKILLs the runner's tree after
  `terminal.daemon_term_grace_seconds` per stage, so it may end before recording
  the stop: such a conversation stays `running`/`unknown` and goes through
  `reconcile`.
- **`cancelled`** requires the group confirmed gone (else `unknown`, as before);
  the runner then removes only its own dead shell's lock. It is the one stopped
  state a conversation may continue from: the next `specialist_call` with a
  corrected message resumes the same Hermes session, and the handoff says the
  step in flight has unknown effects (a first turn cancelled before a session
  was recorded restarts fresh and is told so). A turn that finished before the
  stop reached it stays `completed`. A2A inquiries cannot be cancelled, and A2A
  inbound callers cannot detach. Nested children (a Creator's hands, an
  Engineer's OpenCode runs) are not part of the confirmed group: their own
  runners stop them on parent death, a little later — a Creator's hands as
  `unknown` on the nested side, an OpenCode run as `interrupted` once OpenCode
  confirms it stopped. A cancelled reconcile turn returns to `interrupted`, so cancelling never
  reopens work.

### Completion and deadlines

Live Telegram/Discord contexts use the official terminal background completion
notification. A single-profile gateway verifies its process home against the
plugin's registered profile; a multiplex gateway must provide an explicit
task-scoped home. Unbound routing or ambiguous multiplex flags fail closed.
Background completions for secondary profiles depend on profile-aware
notification routing (upstream behavior); verify it in a topic that
existed before the last gateway restart, because a restored session is the
case that breaks and a fresh topic hides it. Re-check whether shutdown and
`/restart` notifications reach secondary profiles after each update.

CLI callers — including creator nested under the assistant's resident child —
wait for a short-lived runner with a maximum 5400-second deadline (the
`TURN_TIMEOUT` shared by `resident-session.sh` and the plugin). Nested calls
inherit the outer wall-clock deadline rather than resetting it. If the caller
dies, the runner terminates its resident process group, preserves an `unknown`
result and exits; this covers caller death, not simultaneous termination of the
runner itself or descendants that deliberately leave the group. The resident
script exits `143` on INT/TERM with `status: interrupted` and retained partial
logs and session identity; `124` means deadline expiry. Neither is proof of
successful completion.

`specialist_call` is a blocking tool for those CLI callers, so the caller's
generic tool deadline (`timeouts.tools.sequential_call`, default 420 s) cuts it
long before the runner's 5400 s: 41 Creator calls timed out that way and turned
into `specialist_session` polling. `creator` and `marketer` (the CLI callers of
long hands/peer turns) set `sequential_call` / `concurrent_batch` to 5460 —
the runner deadline plus its cleanup allowance. The key applies to every tool of
that profile; long terminal commands keep their own timeouts. Verify with
`HERMES_HOME=~/.hermes/profiles/<p>` +
`agent.tool_executor._resolve_sequential_tool_timeout()`. Telegram/Discord
launches are background completions and never hit this deadline; a `wait` does,
so the Assistant sets `wait_timeout: 900` (wait in place up to 15 min, then
report progress and collect the rest by notification) under a 960 s tool
deadline. The key covers all of its tools; `/stop` releases a stuck one.

A2A inbound permits only synchronous A2A inquiries and rejects `work` before
launch. This is not a durable queue: notification delivery does not survive
every gateway restart. Resident polling defaults to one second; the upstream
completion watcher polls every five seconds.

### Ownership

Gateway ownership uses the framework-dispatched agent session ID and the gateway
turn's session ID, never a model argument or a process-environment fallback. The
dispatched ID is also bound task-locally for the notification stamp, so cached
turns work even when gateway setup leaves the ID ContextVar empty. Resetting a
chat does not grant access to its previous specialist conversations.

## Shared work continuity

Continuity is implemented in `plugins/specialist-call`, not an upstream patch.
Each new conversation retains its untruncated initial agent request, and each
turn has a private `.handoff` record. Only the current request is actionable;
history supplies constraints only, never another production run or regrant.
Runtime attribution and request hashes are not human-approval authentication.

## Failure and reconciliation

- `close` is bookkeeping, not cancellation; `cancel` is the stop.
- A caller-requested, runner-confirmed `cancelled` turn may be continued (see
  "Parallel conversations, wait and cancel"); nothing else that stopped early is.
- An uncertain transport result or an interrupted runner is never retried,
  reclaimed or moved to another backend automatically: inspect retained
  status/logs and reconcile manually.
- Proven pre-dispatch failures (terminal rejection, invalid request
  configuration, DNS/refused connections, spawn failures) are `failed` and
  closable even when no resident session exists.
- Ambiguous launches retain their request file and become `unknown`; they cannot
  be closed or retried.
- `specialist_session(reconcile, evidence=...)` records only a confirmed stopped
  resident process group, as `interrupted` — never `completed` or resumable.
  Missing handles, live groups and foreign/unverifiable locks stay blocked; an
  owned dead shell lock is retained, not reclaimed. A2A has no local liveness
  proof.
- Caller observations remain unverified external effects even after the
  bookkeeping closes.
- Rollout never migrates or rewrites task artifacts, grants or approvals (see
  [topology](../topology.md) "Candidate rollout and cutover").
