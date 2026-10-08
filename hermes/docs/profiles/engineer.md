# Engineer

Engineer dialogue loop, grants and approvals, mode entries, the OpenCode runtime, resident turns and UI verification. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Engineer dialogue loop

Engineer is a developer using OpenCode, not a passive relay or a second coder.
Its Client is either a human directly or Assistant. The Client supplies purpose,
constraints and decisions, not a pre-built technical decomposition; Engineer
investigates and proposes the technical plan with OpenCode. No
Assistant-produced decomposition, Issue or Base session is required. Existing
plans remain useful context, not an automatic new approval.

| Relationship                 | Owner of decisions                                                              | Execution                                       |
| ---------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------- |
| Client with Engineer         | Outcome, scope and important tradeoffs agreed conversationally                  | Human clarify or structured Client Q<n> replies |
| Engineer with OpenCode       | Technical planning, in-scope implementation sequencing, evidence and correction | opencode*run*<role> / opencode_session          |
| OpenCode with its own agents | Code-level methods, exploration, testing and review                             | OpenCode's own tools/skills                     |

One explicit implementation approval releases the agreed scope through QA,
task-branch push and PR delivery. Ordinary internal steps need no per-unit
re-release; a short implementation approval advances to Build, not a restarted
Plan. Material changes return to the Client. Plan/Assess can finish with an
answer and no code. Issue create/edit/comment is enabled only when the Client
explicitly requests Issue management for this job — never inferred from an
Issue URL (read-only grounding) or task size. No automatic Issues/epics/boards,
merge, deployment, repo creation or default-branch push.

### Mode entries

Engineer v9 exposes `plan-engineer`, `build-engineer`, `qa-engineer` and
`assess-engineer` below the retained, thin `engineer-pipeline` root, outside its
`references/`. Their bodies own the mode procedures and each entry routes its
own details. The root retains invariant role, approval and delivery rules; only
`references/opencode.md` (OpenCode transport) and
`references/shared/design-catalog.md` are shared. No old mode-path aliases.
Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract);
Engineer's delta: read the shared OpenCode contract before a wrapper call when
its body is missing. Unavailable required instructions stop that action, never
widen a grant or replay work.

Status: candidate. Cutover needs explicit approval, a controlled gateway restart
and fresh sessions; offline runtime tests (real scanner, index, reader and
canonical recovery in an isolated HOME) are not evidence of live model
selection, approval compliance or delivery. Existing specialist jobs and grants
are reconciled, never silently replayed by migration.

### OpenCode runtime

`plugins/orchestration/opencode-v2` drives the person's shared OpenCode 2 service
over its HTTP API for Engineer and the Assistant (`plugins.enabled: opencode-v2`,
settings under `opencode_v2` in each profile's `config.yaml`). Requests go
through the documented `opencode api` command, which finds or starts the
background service and authenticates like the TUI, so the plugin handles no
server address or password. The command gets a minimal environment (`PATH`,
`HOME`, locale, `TMPDIR`, `XDG_*`): a service it starts keeps that environment
for every session, a person's included, so Hermes' secrets never reach it.

**No run record.** A run is an OpenCode session. Its metadata (`hermes`) binds it
to the originating Hermes session (owner, routing digest), role and branch, and
a caller can only act on sessions it is bound to; there is no implicit
last-session resume. State is read from the service each time: the `idle`
message that closes a turn carries its outcome (`succeeded`, `failed`,
`interrupted`); the active-session list says whether it still runs; pending
permission requests and forms say whether it is paused. Why: the service is the
one source of truth and sessions survive Hermes. The cost is deliberate —
nothing enforces a deadline, so a run outlives its Hermes process and its
resident turn until the caller interrupts it, and an unanswered request stays
pending. The only local file is a per-worktree lock under the profile home that
serializes concurrent starts; it records nothing. Approval text is an
operating-contract record, not authentication; permission rules are not a
process sandbox.

**Roles are configuration.** `opencode_v2.roles` maps a role name to an installed
OpenCode agent, a policy (`read-only` or `write`), and optionally a model
(`provider/model[#variant]`) and a note. Each becomes an
`opencode_run_<role>` tool; with no `roles` the four defaults apply (plan,
review and debug read-only, build write). The agents are the person's own
modes — there are no hidden primaries and no operating contract beyond a short
`hermes.note` instruction entry (prepended to the prompt if the service refuses
the entry). Hermes sits in the person's seat: a question the agent asks and a
permission it needs arrive as `waiting` and are answered with `opencode_request`.

**Plan → Build on the same session.** The next run on a plan session may use
`opencode_run_build` plus `approval`: OpenCode records the switch of agent and
injects its own mode-change reminder, so the session keeps its whole history
(investigation, proposal, answered questions) in context, and each turn re-sends
agent, model, permissions and metadata and verifies the service applied them
before the prompt. The plugin requires the same worktree and branch and refuses
a default-branch build, so `plan-engineer` moves the checkout onto a task branch
BEFORE the first plan call when implementation is likely (a worktree only for
isolation). A plan made on the default branch starts a new session whose message
carries the proposal sections and decisions verbatim; a fork is a full-history
copy and prunes nothing.

**Permissions.** OpenCode 2 evaluates ordered rules, last match wins: global
config, then the agent's own `permissions`, then the session's ruleset; and
every subagent session copies its parent's ruleset (measured on 2.0.23). So the
session ruleset (`policy.rules`) owns each **run's constraints** for the whole
session tree, and it is applied after a subagent's own posture. It therefore
holds denies, asks and narrow allows: the worktree boundary
(`external_directory` asks, OpenCode's own scratch dirs and the read-only
config/skill dirs re-allowed), secrets unreadable, history rewrites, branch
moves, package runners and ungranted Issue writes as asks, the hard denies
(force and protected-branch pushes, merges, `gh api`, Project writes), and last
the person's own denies read from the built-in `build` agent, so a broad allow
never reopens `sudo` or `secret get`. One deliberate exception: a `write` run
allows `edit` in its worktree. Without it every edit is a round trip to the
caller, as OpenCode's own build mode asks a person each time; the cost is that a
subagent that denies itself edits (explore) loses that denial for the run. The
allow is placed before the edit denies for OpenCode's config/skill directories
and secret files, which therefore still win. `read-only` denies edits and the
`worker` and `general` subagents. A write run needs the Client's quoted
`approval`, a named non-default task branch, and a worktree no other session is
running in (another profile's or a person's), so the two profiles cannot edit
one worktree at once; read-only runs may run alongside. V2 wildcards match whole
values and `*` crosses `/`, so secrets are spelled `*.env`, `*.pem`, …
(`**/.env` misses a root-level file).

**Requests.** An `ask` pauses the run as `waiting`, from the session or any of
its subagents (requests are listed per location; the plugin keeps those of its
own session tree). The caller answers each with `opencode_request`: a permission
`once`, or `reject` with a reason OpenCode receives; a question with its answer.
There is no broader approval: `always` saves a project-wide approval people's
own sessions would inherit, and a session-wide allow would be copied into every
subagent session after its own denies. A request stays pending until answered.
The decision rule — inside the Client's approved scope, otherwise reject and
ask — lives in the callers' runtime instructions (Engineer's
`references/opencode.md`, the Assistant's Admin topic prompt).

**Models.** A role's model comes from `opencode_v2.roles.<role>.model`, else the
OpenCode agent's own pin. The plugin passes the model explicitly with every turn
(and on every resume or fork), checks it against the service's model catalog (it
must use tools; a variant must be one the model offers), and reports it as
`engine`. A caller may choose any catalog model of `opencode_v2.allowed_providers`
with `model` / `variant`; `opencode_catalog` `models` lists them with each role's
default. A name outside the providers or the catalog is refused, never
substituted, and an explicit selection binds the rest of that session. The
caller's own model is refused for every role, so a profile never judges or QAs
output from the model it runs on: the configured `model.default` and the model
it last answered with in this Hermes session (a `post_api_request` hook records
it, so a fallback counts too). Speed tiers and dated snapshots (`-fast`,
`-20251001`) count as the same model. A refused default needs another model from
the list, never a retry on the same one; when a profile's main model equals a
role's default, give that role its own `model`.

**Hand-back.** A run tool returns when the turn finished (`completed`, `failed`,
`interrupted`), paused (`waiting`), is stuck in a provider retry worth a decision
(`running` with `retrying`; a limit at once, anything else from the third
attempt), or cannot be confirmed (`unknown`: service unreachable for two minutes,
no outcome 30 s after the run stopped, or a prompt whose admission was not
confirmed). Otherwise it returns `running` with `timed_out` at
`min(opencode_v2.wait_timeout, tool deadline − 30 s, turn deadline)`.
`opencode_session wait` blocks the same way and takes `through_retry` to wait a
retry out. A provider that refuses (usage or rate limit, overload, expired login)
makes OpenCode fail the turn at once or retry with backoff; a failed turn
records `provider_error` (`kind` limit / auth / other, model, message) from its
last assistant message, and the error text says what to do. Engineer's tool
deadline (3660) stays above `wait_timeout` (3300). `unknown` blocks nothing: with
no record there is nothing to reconcile, so the caller reads the diff and
worktree before another turn. A live (Telegram) caller gets the current state at
once and a notifier process, launched through the terminal tool with completion
notification, for the next hand-back.

**Both profiles.** The plugin registers for `engineer` AND `assistant`, each with
its own `opencode_v2` block. The Assistant's grant is the Admin topic's scope
(this config repo, Hermes upkeep, a named workspace repo; contract text in that
topic's private `channel_prompts` entry), never Engineer's project work.

**Session history.** `opencode_history` is the read side of the same plugin,
separate from execution: it never touches sessions' bindings or `opencode_v2`.
Contract, with the Hermes counterpart: [docs/session-history.md](../session-history.md).

**Tests.** `opencode-v2/tests` run against a fake service (`fake_service.py`)
that models the messages, idle markers, requests and forms the real service
returns. They cannot show what the real service does; the shape of those replies
was measured on OpenCode 2.0.23 and a real-service smoke run is a manual step
before a cutover.

### Resident turns and reconcile

A resident Engineer is a plain CLI process, and CLI has no background-process
wakeup (completion notifications are gateway-only), so resident turns block on
OpenCode rather than poll. A blocking call waits until the run hands back or
`min(opencode_v2.wait_timeout, tool deadline − 30 s, turn deadline)`; the
engineer `config.yaml` raises `timeouts.tools.sequential_call` /
`concurrent_batch` to 3660 because the generic 420 s tool deadline cut calls
into costly `status`/`ps`/`sleep` polling loops (the assistant uses 960 for
`specialist_session wait`; see [specialist-calls.md](./specialist-calls.md)).
The fallback `opencode_session(action="wait", timeout?)` blocks the same way.

The 90-minute resident turn (`TURN_TIMEOUT`, fixed in both
`resident-session.sh` and `plugins/orchestration/specialist-call`) is visible to the
specialist: the handoff prints a `Turn budget:` line from `data["deadline"]` to
every target, and asks for a committed checkpoint on the task branch only when
the target is Engineer (`COMMIT_TARGETS`; the other roles have no branch, so
they are told only to stop with a checkpoint report). `build-engineer`
checkpoint-commits verified increments and stops at
~15 min remaining. Nothing interrupts an OpenCode run at the turn's end
(`RESIDENT_DEADLINE` only bounds how long a call waits): Engineer interrupts it
before the turn ends, or reads a read-only run next turn. The Assistant sizes
turns to one verifiable increment and continues
in the same conversation — never a whole "implement to PR" scope in one turn,
which strands uncommitted work.

An interrupted conversation accepts `specialist_call(kind="reconcile")` and
nothing else. OpenCode sessions are bound to the Engineer session + routing
digest, so after a timeout only the SAME resident session can
`opencode_session interrupt` the runs it left going — a fresh conversation or
a terminal resume is refused as "not bound to this originating session". The
reconcile turn inspects with `status` and `diff` and runs with
`RESIDENT_TURN_KIND=reconcile`, under which every `opencode_run_<role>` is
refused; on success the conversation ends `reconciled` (closable, never resumable for
work). The Assistant-side `kind` validation runs inside the gateway process, so
changing it needs a gateway restart; runner/handoff/opencode changes apply on
the next turn. The `Warning: Unknown toolsets: …` line naming plugin toolsets
(`opencode`, `specialist`, `session_history`) on every resident turn is a benign
plugin-discovery-order artifact.

### UI verification

Engineer browses isolated development/test targets itself
(`qa-engineer/references/web-ui.md`): its own browser sessions, isolated test
accounts and state, never owner cookies or another profile's CDP. Browser
actions may still change test data; this is not a website sandbox. UI design
and visual review belong to Engineer's mode entries, not OpenCode global
skills; OpenCode keeps implementation-time rendering and project tests.

### Hands-reference maintenance

Hands-reference maintenance has conditional Assess / Plan / Build / Quality
assurance guides in Engineer, not another production leaf. They own Client scope
and independent acceptance; the dotconfig OpenCode Skill
`opencode/skills/hermes/hands-references/SKILL.md` owns the procedure.
`scripts/audit-hands-references.py` is a read-only companion to the topology
validator: orphan candidates are warnings, not deletion permission; card checks
import the trusted candidate's adapter, not sandboxed code. Assess never fixes
or upgrades UNVERIFIED claims automatically. A branch in the live
symlink-backed checkout is not runtime isolation: use task worktrees, and keep
self-modification scope, PR delivery and live cutover separate.

### Specialist dialogue discipline

The dialogue discipline is specialist-generic, not engineer-specific:
**creator** and **writer** also honor the `Review: required` gate; creator
speaks the same protocol with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
The **hands** consume filled forms the assistant commissions directly; a
missing required field returns as a `Q<n>:` block, input parts are consumed
verbatim, and every content-altering transform stays with the hands (the
assistant handles bytes, never re-encodes). Details:
[`broker.md`](../broker.md).
**writer** consumes released units the same way — an outline unit
(structure + tone samples, gated before drafting), piece units against
the approved outline, or a whole small job — under the selected leaf's
QA contract, returning
undecided deliverable-defining choices as spec-gap or granularity findings. Details: writer's
`writer-pipeline` skill. **marketer** is the strategy advisor for human,
Assistant and Engineer clients: strategy, offer discovery, review
findings and outcome analysis, read-only toward every service; clients
execute. Contract: [`marketer.md`](./marketer.md) "Marketer as strategy
advisor".
