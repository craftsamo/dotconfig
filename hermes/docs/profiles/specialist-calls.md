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
| engineer | marketer, researcher, writer, ui-review, ux-persona |

UI evaluators are resident-only, without bots or A2A ports. The default CLI flow
is unchanged. Short inquiries use an allowed target's existing `a2a_agents` RPC
endpoint when one exists; no endpoint is ever discovered from model text or a
supplied URL. Work always uses the resident script
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

`specialist_session` supports `status`, `list`, `close` and `reconcile`, only in
the same originating session and profile. The registry and restrictive request
files live under the caller's real Hermes home in `specialist-sessions/`;
resident JSON and logs keep their format in `resident-sessions/`. Old resident
keys stay runnable through the original script; automatic adoption is
unsupported because old entries establish no originating-session owner. Listing
skips revoked targets without hiding other permitted rows.

### Completion and deadlines

Live Telegram/Discord contexts use the official terminal background completion
notification. A single-profile gateway verifies its process home against the
plugin's registered profile; a multiplex gateway must provide an explicit
task-scoped home. Unbound routing or ambiguous multiplex flags fail closed.
Background completions for secondary profiles depend on profile-aware
notification routing (carried as a local patch); verify it in a topic that
existed before the last gateway restart, because a restored session is the
case that breaks and a fresh topic hides it. Shutdown and `/restart`
notifications for secondary profiles are still not routed.

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
calls are background completions and never hit this deadline.

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

- `close` is bookkeeping, not cancellation.
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
