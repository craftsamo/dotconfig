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
| Engineer with OpenCode       | Technical planning, in-scope implementation sequencing, evidence and correction | opencode_call / opencode_session                |
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

`plugins/opencode` drives the person's shared OpenCode 2 service over its HTTP
API (`opencode_call`, `opencode_session`) and keeps the private
`opencode-sessions/` records (one per conversation, never Git). Requests go
through the documented `opencode api` command, which finds or starts the
background service and authenticates like the TUI, so the plugin handles no
server address or password. The command gets a minimal environment (`PATH`,
`HOME`, locale, `TMPDIR`, `XDG_*`): a service it starts keeps that environment
for every session, a person's included, so Hermes' secrets never reach it. Each conversation binds its originating Hermes
session, Git worktree and branch; there is no implicit last-session resume.
The plugin never blindly retries uncertain work:

- Completion is the turn's own `idle` outcome reported by OpenCode
  (`succeeded` → completed, `failed` → failed, `interrupted` → interrupted),
  read after this turn's prompt; a session-level outcome alone would still be
  the previous turn's.
- Deadlines are finite. A stop, the deadline, or the end of the CLI/resident
  Hermes process that started the turn interrupts the session, which ends its
  tool processes and every subagent session, and drops parked input. The
  interrupt is resent until the turn settles; one OpenCode never confirms within
  three minutes leaves the run `unknown`. Never a rollback.
- `unknown` is left for what OpenCode could not confirm (service unreachable
  past the deadline, prompt admission unconfirmed, setup cut short, a record
  from the retired OpenCode 1 runner). It holds the worktree until
  `opencode_session reconcile` with observed Git/remote evidence.
- Approval text is an operating-contract record, not authentication; records and
  permission rules are not a process sandbox.

**Watcher.** Each turn gets one detached watcher process
(`__init__.py watch`). It holds the conversation's lock for its lifetime — the
OS drops the lock when it dies, which is how a lost watcher is detected — and
it alone writes the running record: progress tokens, pending permission
requests, the permission timeout, the deadline interrupt and the final outcome,
result text and changed files. `status`, `list`, `wait` and a live caller's
notifier restart a lost watcher, which then reads the outcome from OpenCode or
resumes watching; that is how a run survives a dead Hermes process. A turn that
is neither running nor idle for 30 s ended without an outcome (the service
restarted under it) and is recorded `interrupted`, resumable by the next
message on the same conversation.

**Hand-back.** A blocking call (CLI/resident) returns when the run hands back
— finished, uncertain, `waiting` on an unanswered permission request, or stuck
in a provider retry — or at a bounded wait limit below the caller's own tool
deadline.

**Provider limits.** A provider that refuses (usage or rate limit, overload,
expired login) makes OpenCode fail the turn at once or retry with backoff,
possibly until the deadline. A failed turn records `provider_error` (`kind`
limit / auth / other, model, message) from its last assistant message's error,
and the error text says what to do. While a run is in a retry, its newest
assistant message (root or any running subagent's) carries OpenCode's `retry`
state; the watcher checks every 10 s and records `retrying`. A limit hands back
at once and anything else from the 3rd attempt, once per retry episode (the
`<job>.retried` side file records which), so the caller can stop and continue
with another model instead of waiting out a backoff. A live caller
(Telegram) gets an immediate reply and a notifier process launched through the
terminal tool with completion notification; it exits at the next hand-back, and
`respond` launches the next one.

The plugin registers for `engineer` AND `assistant`, each with its own
`opencode_cli` block and its own registry under its home. The Assistant's grant
is the Admin topic's scope (this config repo, Hermes upkeep, a named workspace
repo; contract text in that topic's private `channel_prompts` entry), never
Engineer's project work. Registries are per home, but a build refuses any
worktree in which the service already runs another session — another profile's
or a person's — so the two profiles cannot edit one worktree at once;
read-only roles may run alongside.

**Session history.** `opencode_history` is the read side of the same plugin,
separate from execution: it never touches `opencode-sessions/`, grants or
`opencode_cli`. Contract, with the Hermes counterpart:
[docs/session-history.md](../session-history.md).

**Hidden primaries.** All four roles run on hidden OpenCode primaries, not the
human TUI agents: `OPENCODE_AGENTS` in the plugin maps each Hermes role to
`~/.config/opencode/agent/hermes-{plan,build,review,debug}.md` (`mode: primary`,
`hidden: true`). Every other plugin decision keys on the Hermes role name, so
renaming an installed agent touches only the map. OpenCode's plan-mode reminder
is keyed on the literal agent name `plan`, so `hermes-plan`'s read-only posture
is prompt + permission, not plan mode. The primaries replace the provider
default prompt with a non-interactive contract: no `question` tool, no
plan→build handoff or PlanHandoff todos, Client decisions returned as `Q<n>:`
with a default already taken, every check delegated to `verifier`, and
reviewer / reviewer-deep passes ONLY when the message asks. The plugin checks
before each turn that the agent is still the hidden primary and that a
read-only role still denies edits, shell writes and `worker` under the combined
rules; otherwise it launches nothing.

**Models.** Models are pinned per role in the agent frontmatter (plan, review
and debug Opus 5.5, build GPT-6.1 Sol); a profile's `opencode_cli.models`
overrides them per role as `provider/model` or `provider/model#variant` (the
Assistant, which runs on Opus 5.5, sets its own). The plugin passes the model
explicitly with every turn (and on every resume or fork), checks it against the
service's model catalog (it must use tools; a variant must be one the model
offers), and records it as `engine`. A caller may choose any catalog model of
`opencode_cli.allowed_providers` with `opencode_call` `model` / `variant`;
`opencode_session models` lists them with each role's default. A name outside
the providers or the catalog is refused, never substituted, and an explicit
selection binds the rest of that conversation.

The caller's own model is refused for every role, so a profile never judges or
QAs output from the model it runs on: the configured `model.default` and the
model it last answered with in this Hermes session (a `post_api_request` hook
records it, so a fallback counts too). Speed tiers and dated snapshots
(`-fast`, `-20251001`) count as the same model. A refused default needs another
model from the list, never a retry on the same one.

**Permissions.** OpenCode 2 evaluates ordered rules, last match wins: global
config, then the agent's own `permissions`, then the session's ruleset; and
every subagent session copies its parent's ruleset (measured on 2.0.23). So
policy has two owners with a fixed boundary:

- Each hidden primary's frontmatter owns its **role posture**: plan, review and
  debug start from a full deny and list what they need (read tools, read-only
  git/gh, their subagents); build allows edits, routine commands and its
  subagents. A full deny also shadows the person's global allows, so a
  read-only role names every tool it needs.
- The plugin's session ruleset (`_rules`) owns each **run's constraints** for
  the whole session tree: the worktree boundary (`external_directory` asks,
  OpenCode's own scratch dirs and the read-only config/skill dirs re-allowed),
  `question` denied, secrets unreadable, plan's tree unedited, build's pushes,
  history rewrites, branch moves, package runners and ungranted Issue writes
  as asks, the hard denies (force and protected-branch pushes, merges, `gh api`,
  Project writes), and last the person's own denies read from the built-in
  `build` agent, so build's broad allow never reopens `sudo` or `secret get`.
  Because subagents copy it and it is applied after their own posture, the
  ruleset carries no broad allow — one would reopen what an explore or reviewer
  subagent denies itself. A test enforces this.

V2 wildcards match whole values and `*` crosses `/`, so secrets are spelled
`*.env`, `*.pem`, … (`**/.env` misses a root-level file).

**Permission requests.** An `ask` pauses the run as `waiting`, from the session
or any of its subagents (requests are listed per location; the watcher keeps
those of its own session tree). The caller answers each with `opencode_session
respond`: `once`, or `reject` with a reason OpenCode receives. There is no
broader approval: `always` saves a project-wide approval people's own sessions
would inherit, and a session-wide allow would be copied into every subagent
session after its own denies. An unanswered
request is rejected at `opencode_cli.permission_timeout` (default 900 s). The
decision rule — inside the Client's approved scope, otherwise reject and ask —
lives in the callers' runtime instructions (Engineer's `references/opencode.md`,
the Assistant's Admin topic prompt).

**Plan → Build on the same conversation.** The next `opencode_call` on a plan
conversation may name `agent="build"` plus `approval`; the session switches
agent, model and ruleset and keeps its whole history (investigation, proposal,
`DECISION(Q<n>)` lines) in context. The wrapper requires the same worktree and
branch and refuses a default-branch build, so `plan-engineer` moves the
checkout onto a task branch BEFORE the first plan call when implementation is
likely (a worktree only for isolation). A plan made on the default branch
starts a new conversation whose message carries the proposal sections and
decisions verbatim; a fork is a full-history copy and prunes nothing.

### Resident turns and reconcile

A resident Engineer is a plain CLI process, and CLI has no background-process
wakeup (completion notifications are gateway-only), so resident turns block on
OpenCode rather than poll. A blocking call waits until the run hands back or
`min(opencode_cli.wait_timeout, tool deadline − 30 s, turn deadline)`; the
engineer `config.yaml` raises `timeouts.tools.sequential_call` /
`concurrent_batch` to 3660 because the generic 420 s tool deadline cut calls
into costly `status`/`ps`/`sleep` polling loops (the assistant uses 960 for
`specialist_session wait`; see [specialist-calls.md](./specialist-calls.md)).
The fallback `opencode_session(action="wait", timeout?)` blocks the same way.

The 90-minute resident turn (`TURN_TIMEOUT`, fixed in both
`resident-session.sh` and `plugins/specialist-call`) is visible to the
specialist: the handoff prints a `Turn budget:` line from `data["deadline"]`,
and `build-engineer` checkpoint-commits verified increments and stops at
~15 min remaining. An OpenCode turn's own deadline never outlives the resident
turn (`RESIDENT_DEADLINE`), so a run still going then is interrupted, not left
uncertain. The Assistant sizes turns to one verifiable increment and continues
in the same conversation — never a whole "implement to PR" scope in one turn,
which strands uncommitted work.

An interrupted conversation accepts `specialist_call(kind="reconcile")` and
nothing else. OpenCode records are owned by the Engineer session + routing
digest, so after a timeout only the SAME resident session can
`opencode_session reconcile` its children — a fresh conversation or a terminal
resume is refused as "another originating session". The reconcile turn runs
with `RESIDENT_TURN_KIND=reconcile`, under which `opencode_call` is refused; on
success the conversation ends `reconciled` (closable, never resumable for
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
Creator consumes **released units** (anchor / part / assembly) whose
deliverable-defining decisions the assistant fixed in its plan family
leaves; a spec gap or implied composite returns as a finding, input
parts are consumed verbatim, and the production boundary keeps every
content-altering transform on the creator side (the assistant handles
bytes, never re-encodes). Details: creator's `creator-pipeline` skill.
**writer** consumes released units the same way — an outline unit
(structure + tone samples, gated before drafting), piece units against
the approved outline, or a whole small job — under the selected leaf's
QA contract, returning
undecided deliverable-defining choices as spec-gap or granularity findings. Details: writer's
`writer-pipeline` skill. **marketer** owns strategy, offer discovery, producer
coordination and browser draft work for both human and Assistant clients;
Assistant supplies goals/constraints, not a fully settled marketing strategy.
Its exact-consent, draft-only grant: [`marketer.md`](./marketer.md) "Marketer
strategy and browser drafts".
