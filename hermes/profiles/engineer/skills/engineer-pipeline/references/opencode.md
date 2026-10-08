# OpenCode - shared transport contract

Read before the first wrapper call in any mode. This file owns session and
result semantics; Plan/Build/QA/Assess own what to request and how to judge it.
Never call raw opencode commands or the OpenCode API, or substitute another
coding agent to bypass the wrapper. OpenCode still owns its internal tools and
development methods; concise prompts carry the job-specific delta, not copied
global instructions or whole Skill bodies.

The wrapper drives the person's shared OpenCode service, so your sessions are
visible in their OpenCode history and keep running if your Hermes process dies.
It keeps no run record: a session's state is read from OpenCode each time.

## Runs

One tool per role: `opencode_run_plan`, `opencode_run_review`,
`opencode_run_debug` (read-only: they never edit) and `opencode_run_build`
(write). Each takes
`(directory?, session_id?, message, model?, variant?, fork?, timeout?)`, and
build also `approval` and `issue_approval`.

- The agents are OpenCode's own plan, review, debug and build modes, run with no
  human at the terminal: you sit in the person's seat. A question the agent
  would put to a person, and a permission it needs, come back to you as
  `waiting` (see "Requests"). A run's operating note says a Hermes agent drives
  it and that it should take a recommended default rather than ask about what
  does not block the work. Its own advice to "ask the user to switch to Build" is
  yours to act on: only you switch, and only on the Client's approval.
- New session: `directory` is an absolute Git worktree root. The result names
  the `session_id`; keep it, and pass it for every later turn. Never infer "the
  last session". `opencode_session list` returns the sessions this originating
  session started.
- A session is bound to its originating Hermes session, worktree and branch.
  To move to a new task worktree, start a new session with the actual approved
  plan as context. A copied plan does not grant additional work.
- The role may change between turns of one session: the next run on the same
  `session_id` switches the agent, model and policy, OpenCode records the
  switch, and the whole history stays in context. This is how Plan hands over
  to Build — `opencode_run_build` with the plan run's `session_id` plus
  `approval` — and the only way the plan run's own investigation reaches the
  build run. Conditions: same worktree, same branch, and for build a non-default
  branch. Anything a new session must know has to be pasted verbatim; there is
  no partial carry-over.
- `fork=true` needs a `session_id`, copies the ENTIRE history at that moment and
  runs on the copy. It prunes nothing, so it is not a way to drop stale
  context; it is for parallel variants or an independent diagnosis on the same
  worktree. A lighter context is a new session with the needed inputs.
- `approval` is the Client's explicit scoped implementation decision as text,
  not a boolean. A build turn needs it every time you start one; quote it again
  on continuations. `issue_approval` separately quotes the explicit current-job
  Issue-management request. Both are operating-contract records, not
  authentication.
- A build may edit files in its worktree without asking. Pushes, history
  rewrites, branch moves, package runners and Issue writes without
  `issue_approval` come back to you as requests; force or protected-branch
  pushes, merges and the like are denied outright. A read-only role cannot edit,
  and cannot hand work to an editing subagent.
- OpenCode runs its own method and subagents. Ask in the message for what you
  need: actual check results, a review pass ("run a review pass", "deep review
  <area>") when an increment is risky, a checkpoint commit.
- A build refuses a worktree in which another OpenCode session is running
  (another Hermes profile or a person); read-only roles may run alongside. Never
  start a second turn on a session that is still running: wait, steer or
  interrupt it.
- Models: each role follows its configured pin (`opencode_v2.roles`; build is
  pinned to GPT-6.1 Sol) or, without one, the OpenCode agent's own model (Opus
  5.5); the result's `engine` names what ran. You may pick another when the work
  or the Client calls for it: `opencode_catalog` `models` lists what you may pass
  as `model` (provider/model) and `variant` (that model's reasoning efforts), the
  defaults per role, and your own models. Your own model (your configured one,
  and a fallback you are answering with now) is refused for every role, the
  default included, so you never judge or QA output from the model you run on;
  on that refusal pick another listed model. A name outside the list or not
  offered by OpenCode is refused, never substituted; report the refusal and ask,
  do not stop the whole job over it. An explicit selection binds the rest of
  that session; omitting it keeps the recorded engine. The caller cannot change
  the executable, environment or permission rules. No automatic fallback or
  retry after uncertain effects.

## Session tools

`opencode_session(action, session_id?, …)` works on sessions bound to your
originating session.

- `list` (optionally `directory`, `limit`) returns your sessions; `status` reads
  one without waiting.
- `wait` blocks until the run hands back — finished, paused on a request you have
  not answered, stuck in a provider retry worth a decision (see "Provider
  limits"), or unconfirmed — bounded by `timeout`, `opencode_v2.wait_timeout`,
  your tool deadline and the turn deadline. It returns the state with
  `timed_out` when the bound came first, and spends no model turns: a timed-out
  reply means wait again, steer, or interrupt, never a status/sleep loop.
  `through_retry` keeps waiting through a provider retry you chose to wait out.
- `steer` (with `message`) adds an instruction to a running turn. It is delivered
  at the run's next step boundary (a long tool call finishes first) and is for
  course corrections, not new scope.
- `diff` (optionally `patch=true`) lists the newest turn's changed files, as
  OpenCode computed them for that turn; patches are truncated. It is evidence for
  your QA, not a substitute for reading the worktree. `messages` reads recent
  messages (text truncated).
- `interrupt` stops the run (its subagents stop with it) and drops instructions
  still parked for it. The state settles within seconds as `interrupted`.
  Interrupting never rolls back Git, application data, provider requests,
  pushes or PRs already created.
- `fork` copies an idle session to a new `session_id`.

`opencode_instructions(action, session_id, key?, value?)` lists, sets or removes
durable instructions on a session, announced to the agent at its next step
boundary. Keys are `hermes.<name>`. The run's operating note lives in
`hermes.note`; use another key for a constraint that should outlast one message.

`opencode_catalog(what, directory?)` reads what OpenCode offers: `models` (with
variants, context, cost, role defaults and your own models), `agents`, `skills`,
`commands`, `vcs`, `info`. It never changes anything.

`opencode_history(action, …)` reads OpenCode's own session history across all
projects, including sessions a person ran in the TUI. It launches no agent: list/get/children for metadata, usage
for tokens and activity over a `[from, to)` window. Titles and costs appear only
with include_title / include_cost; message content never. usage activity is
time assistant steps ran with question waits removed (a permission-prompt wait
still counts) — not human working time.
Check `source` and `status`: a `partial` or database-fallback answer carries
its reason in diagnostics; pass that limitation on rather than filling the gap.
`hermes_history` is the same for Hermes' own sessions across every profile
(profile, platform, lineage); `/activity` shows both tools' activity together.

## Requests

OpenCode pauses a run when it needs a decision: a permission (a path outside the
worktree, a build's push, history rewrite, branch move or package runner, an
Issue write without `issue_approval`, a subagent command outside that
subagent's own allowlist) or a question the agent would put to a person. The
state is `waiting` and the call hands back; `pending` lists each request with
its `kind` (`permission`, `question`), `id`, whether a subagent asked, and for a
permission its action, resources and the pattern a broader approval would cover
(`save`), for a question its fields and options.

`opencode_request(action, session_id, …)`: `list` shows what is pending;
`reply` answers one by `request_id`, then waits for the next hand-back.

- A permission inside the approved scope → `decision: "once"`; outside the scope
  or unclear → `decision: "reject"` with a short `reason` OpenCode can act on,
  then relay the decision to the Client if the work needs it. Decide against the
  Client's quoted approval and the mode's scope.
- A question is an OpenCode agent asking a person. Answer it with
  `answer: {field: value}` when it is an in-scope technical question you can
  settle; relay a material decision to the Client first. `decision: "reject"`
  declines it.

There is no broader approval: `always` would save a project-wide approval
people's own sessions inherit, and a session-wide one would reach every
subagent. If the same request keeps recurring inside scope, say in the next
message how to avoid it (for example, which command to use). A request stays
pending until you answer it; nothing times it out, and the run does not move
meanwhile. Force or protected-branch pushes, merges, `gh api`,
repository/Project writes, secret reads and the person's own denies never reach
you: they are denied outright.

## Results

`running` means execution is outstanding. A run keeps going if the Hermes
process that started it ends: nothing stops it but you (`interrupt`) or the
person. Live messaging uses Hermes' completion notification, sent at every
hand-back (finished or waiting). In a CLI/resident session a run tool BLOCKS
until the run hands back, within your tool deadline; a resident CLI has no
completion wakeup, so blocking is the cheap path. Never poll: no
status/terminal/sleep loops, no ps checks while a call is outstanding. If a call
returns with `timed_out` or a tool-timeout error, issue ONE
`opencode_session wait` for the session and read its result.

`completed` means OpenCode reported the turn succeeded, not that the task
passed. Read `result` for open questions, assumptions and unverified claims, and
`changes` for what it touched. A question can arrive in an otherwise completed
run. Engineer answers in-scope technical questions and relays material Client
decisions, then continues.

`failed` means OpenCode reported a failed turn; it can still have partial
changes. A `provider_error` on it says why (kind limit / auth / other, the model
and the provider's message); see "Provider limits". `interrupted` means the run
stopped before finishing: your interrupt, or OpenCode itself. OpenCode confirmed
nothing still runs, so the session can continue: inspect the diff and worktree,
then send the next message on the same session — never a blind replay of the
original prompt. `idle` is a session that never ran a turn.

`unknown` means OpenCode could not confirm how the turn ended (the service was
unreachable, the prompt admission was not confirmed, or the turn ended with no
outcome). Nothing is recorded about it and nothing blocks the next turn, so the
discipline is yours: read `diff`, `messages` and the worktree first; never
replay the original prompt blindly; never start a second turn while the first
may still run (check `status`).

Provider limits. When a model's provider refuses (usage or rate limit, an
overload, an expired login), OpenCode either fails the turn at once or keeps
retrying with backoff. A failure arrives as `failed` with `provider_error`. A
retry hands back while the run is still `running`, with `retrying` (kind,
message, attempt, which session — a subagent's model can be the one limited)
and a note: at once for a limit, after a few attempts for anything else. Decide
then: wait if it should recover soon (`wait` with `through_retry`); otherwise
`interrupt` and run the same session again with `model=` another engine from
`opencode_catalog models`. Read-only roles can simply rerun; for build read the
diff first and continue from what is there. A limited subagent model needs the
run's message to name another subagent, or a Client decision. An auth problem is
OpenCode's own provider login: tell the Client. Never loop on the same limited
model.

Every resident turn carries a "Turn budget" line naming when the whole turn
is killed. Give each call a job that fits the remaining budget. A run still going
at the turn deadline keeps going in OpenCode, but you can no longer judge it: stop
it with `interrupt` before the turn ends unless it is a read-only run you will
read next turn. When the remaining budget is ~15 minutes, do not start a new
run: ask OpenCode for nothing further, make sure verified work is committed on
the task branch, and end the turn with a checkpoint report (worktree, branch,
HEAD, what is verified, what remains, session ids).

An interrupted conversation may be continued by its Client only as a
RECONCILE-ONLY turn (the handoff says so and every run tool is refused). In it,
inspect each owned session (`status`, `diff`, `messages`, Git and remote
effects), `interrupt` what still runs, and report; do no other work.

A `Warning: Unknown toolsets: opencode, specialist` line at the start of a
resident turn is a plugin-discovery-order artifact, not a missing capability:
the tools load right after it. Do not report it or work around it.

The wrapper keeps plan/review/debug read-only, lets a build edit its worktree and
run routine commands, rejects default-branch builds, and returns pushes and
Issue writes without the separate grant to you as requests. Command rules are
defence in depth, not an arbitrary-shell/website sandbox. Preserve narrower
Client restrictions in the prompt and verify actual effects; if a restriction
cannot be safely honored, return the limitation instead of widening access.
