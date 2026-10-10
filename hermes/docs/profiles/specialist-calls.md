# Specialist calls and work continuity

How primaries open, continue and close conversations with specialists and hands
(`plugins/orchestration/specialist-call`), and what survives a failure. Read it
before changing call, wait, cancel or deadline behavior. Part of the Hermes
design docs — index: [`PROFILES.md`](../../PROFILES.md). Install/enable steps
live in [`ops/plugins.md`](../ops/plugins.md) "Transports".

## Specialist calls

The shared plugin exposes the `specialist` toolset to assistant, creator and
marketer; it is their only outbound path (the raw `a2a_*` tools stay off, see
[topology](../topology.md) "Toolsets"). Each caller has an explicit
`specialist_call.resident_targets` allowlist:

| Caller    | Targets                                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------------------------- |
| assistant | creator, marketer, writer, image-creator, video-creator, audio-creator; searcher resident-only. Never researcher directly |
| creator   | researcher; searcher resident-only                                                                                        |
| marketer  | researcher; searcher resident-only (keeps inbound A2A for its clients)                                                    |

Short inquiries use an allowed target's existing `a2a_agents` RPC endpoint when
one exists; no endpoint is ever discovered from model text or a supplied URL.
Work always uses the resident script (`assistant/scripts/resident-session.sh`).

Call `specialist_call(target, message, kind="inquiry"|"work")`, then continue
with the same `target`, the returned `conversation_id` and the next `message`;
route and target stay pinned for the conversation. `inquiry` is for free,
bounded, single-reply requests; `work` is for metered, multi-turn or long work.
Pass purpose/consumer/constraints/budget for Researcher/Searcher framing, or the
explicitly authorized settled brief for execution, and preserve any released
unit, inputs, permissions and grant unchanged. Transport selection grants no
authority or budget. `kind="reconcile"` is the only call an interrupted
conversation accepts (see "Failure and reconciliation").

`specialist_session` (`status`, `list`, `wait`, `cancel`, `close`, `reconcile`)
works only in the same originating session and profile. The registry lives under
the caller's real Hermes home in `specialist-sessions/`.

### Parallel conversations, wait and cancel

Independent conversations run in parallel; one conversation never does (its
lock refuses a second turn). Each originating session may have at most
`specialist_call.max_active` conversations accepted or running; a call over the
cap dispatches nothing. An optional `group` label ties a batch together for
`wait` and for the `group_progress` in each completion.

- **Launch.** Messaging callers are always background. A CLI caller passes
  `wait=false` to get the `conversation_id` at once (upstream runs plugin tools
  one at a time, so a parallel batch would not launch in parallel); the runner stays its child,
  so it dies with a one-shot caller — collect before the turn ends.
- **`wait`** blocks without model turns until the work settles, the limit
  passes, or a new user message / interrupt arrives; it never stops a
  specialist. Its limit is the smallest of `specialist_call.wait_timeout`, the
  request, the caller's tool deadline minus 30 s and the inherited resident
  deadline. On messaging it marks settled completions consumed so they do not
  return as extra turns (best effort).
- **`cancel`** stops a resident turn. Not yet picked up: cancelled in place,
  nothing ran. Otherwise it leaves a stop request for the runner that owns the
  turn; only that runner signals its group (TERM the shell once, `KILL_GRACE` for
  the CLI to flush its transcript and session id, then kill the rest). Gateway
  `/stop` reaping may SIGKILL the runner before it records the stop: such a
  conversation stays `running`/`unknown` and goes through `reconcile`.
- **`cancelled`** requires the group confirmed gone (else `unknown`); the runner
  then removes only its own dead shell's lock. It is the one stopped state a
  conversation may continue from: the next `specialist_call` with a corrected
  message resumes the same Hermes session, and the handoff says the step in
  flight has unknown effects. A turn that finished before the stop reached it
  stays `completed`. A2A inquiries cannot be cancelled. Nested children (a
  Creator's Researcher call) are not part of the confirmed group: their own
  runners stop them on parent death, as `unknown` on the nested side. A cancelled
  reconcile turn returns to `interrupted`, so cancelling never reopens work.

### Completion and deadlines

Live Telegram/Discord contexts use the official terminal background completion
notification. A multiplex gateway must provide an explicit task-scoped home;
unbound routing or ambiguous multiplex flags fail closed. Check completions for
secondary profiles in a topic that existed before the last gateway restart: a
restored session is the case that breaks, a fresh topic hides it.

CLI callers — including creator nested under the assistant's resident child —
wait for a short-lived runner with a maximum 5400-second deadline (the
`TURN_TIMEOUT` shared by `resident-session.sh` and the plugin). Nested calls
inherit the outer wall-clock deadline rather than resetting it. If the caller
dies, the runner terminates its resident process group, preserves an `unknown`
result and exits. Resident exit `143` (INT/TERM, `status: interrupted`) and
`124` (deadline) are never proof of completion.

`specialist_call` is a blocking tool for those CLI callers, so the caller's
generic tool deadline (`timeouts.tools.sequential_call`, default 420 s) would cut
it long before the runner's 5400 s and degrade it into `specialist_session`
polling. `creator` and `marketer` (CLI callers of long Researcher turns)
therefore set `sequential_call` / `concurrent_batch` to 5460 — the runner
deadline plus its cleanup allowance. The key applies to every tool of that
profile. Telegram/Discord
launches are background completions and never hit this deadline; a `wait` does,
so the Assistant sets `wait_timeout: 900` (wait in place up to 15 min, then
report progress and collect the rest by notification) under a 960 s tool
deadline, which must stay above `wait_timeout` + 30 s. `/stop` releases a stuck
tool.

Plugin tools that block on a send size their own deadline under the Assistant's
960 s, so they fail with their own error instead of being cut by the generic
one: `whatsapp-access` (`wa.py`) allows 840 s for a whole file send,
`discord-access` (`access.py`, `engine.py`) 840 s for uploads and 660 s for
media downloads. Peer `a2a_agents` entries keep
`timeout: 310`, because the 120 s caller default undercuts the 300 s server reply
window.

A2A inbound permits only synchronous inquiries and rejects `work` before launch;
it is not a durable queue.

### Ownership

Gateway ownership uses the framework-dispatched agent session ID and the gateway
turn's session ID, never a model argument or a process-environment fallback.
Resetting a chat does not grant access to its previous specialist conversations.

## Shared work continuity

Continuity is implemented in the plugin, not an upstream patch. Each new
conversation retains its untruncated initial agent request, and each turn has a
private `.handoff` record. Only the current request is actionable; history
supplies constraints only, never another production run or regrant. Runtime
attribution and request hashes are not human-approval authentication.

## Failure and reconciliation

- `close` is bookkeeping, not cancellation; `cancel` is the stop.
- A caller-requested, runner-confirmed `cancelled` turn may be continued (see
  "Parallel conversations, wait and cancel"); nothing else that stopped early is.
- An uncertain transport result or an interrupted runner is never retried,
  reclaimed or moved to another backend automatically: inspect retained
  status/logs and reconcile manually.
- Proven pre-dispatch failures (terminal rejection, invalid configuration,
  DNS/refused connections, spawn failures) are `failed` and closable even when no
  resident session exists.
- Ambiguous launches retain their request file and become `unknown`; they cannot
  be closed or retried.
- `specialist_session(reconcile, evidence=...)` records only a confirmed stopped
  resident process group, as `interrupted` — never `completed` or resumable.
  Missing handles, live groups and foreign locks stay blocked. A2A has no local
  liveness proof.
- Caller observations remain unverified external effects even after the
  bookkeeping closes.

## Specialist dialogue discipline

Each specialist's own dialogue rules live in its doc; only the common rules are
here. A brief carrying `Review: required` makes the resident session present the
exact candidate and wait for sign-off (researcher and writer honor it). Hands
take filled forms and return a missing field as one batched `Q<n>:` block
([`broker.md`](../broker.md)); writer takes released units and returns undecided
deliverable-defining choices as spec-gap or granularity findings
([`writer.md`](./writer.md)); researcher and searcher likewise
([`research.md`](./research.md)); creator and marketer are advisors that never
execute ([`creator.md`](./creator.md), [`marketer.md`](./marketer.md) "Marketer
as strategy advisor").
