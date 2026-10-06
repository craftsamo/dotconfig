# OpenCode - shared transport contract

Read before the first wrapper call in any mode. This file owns session and
result semantics; Plan/Build/QA/Assess own what to request and how to judge it.
Never call raw opencode commands or the OpenCode API, or substitute another
coding agent to bypass the wrapper. OpenCode still owns its internal tools and
development methods; concise prompts carry the job-specific delta, not copied
global instructions or whole Skill bodies.

The wrapper drives the person's shared OpenCode service, so your sessions are
visible in their OpenCode history and survive a lost wrapper process.

## Calls

`opencode_call(directory?, agent, message, conversation_id?, fork?, approval?, issue_approval?, model?, variant?)`

- New conversation: directory is an absolute Git worktree root. Agent is plan,
  build, review or debug. Use the returned opaque conversation_id for subsequent
  calls. Never infer "the last session" or supply an arbitrary OpenCode session ID.
- A conversation is bound to its originating Hermes session, worktree and branch.
  To move to a new task worktree, start a new conversation with the actual approved
  plan as context. A copied plan does not grant additional work.
- The agent may change between calls on one conversation: the OpenCode
  session is resumed with the new agent's model and policy, and its whole
  history stays in context. This is how Plan hands over to Build — the same
  conversation, `agent="build"` plus `approval` — and it is the only way the
  plan run's own investigation reaches the build run. Conditions: same
  worktree, same branch, and for build a non-default branch; the primaries
  never switch themselves (no `plan_exit`), Engineer does it with the next
  call. Anything the new conversation must know that the old one learned
  has to be pasted verbatim; there is no partial carry-over.
- fork=true requires an owned conversation and returns a new conversation handle
  and OpenCode session, preserving the source. It copies the ENTIRE history at
  that moment — it prunes nothing, so it is not a way to drop stale context —
  and is for parallel variants or an independent diagnosis on the same
  worktree; a lighter context is a new conversation with the needed inputs.
- approval is the Client's explicit scoped implementation/write decision as text,
  not a boolean. The initial build call needs it; continuations retain it.
  issue_approval separately quotes the explicit current-job Issue-management
  request. Both are operating-contract records, not authentication.
- The four roles run on hidden OpenCode primaries built for this transport
  (hermes-plan / -build / -review / -debug): they take no questions, do not hand
  off between plan and build themselves, and answer with fixed report headings.
  Plan returns Client decisions as `Q<n>:` lines with a recommended default
  already taken; answer them with `DECISION(Q<n>): …` on the same
  conversation. Build delegates every check to a verifier subagent and runs
  a reviewer pass ONLY when the message asks for one ("run a review pass" /
  "deep review <area>"); Review likewise runs reviewer-deep only on request.
  Debug returns the causal chain down to a root cause and never edits. Say so
  in the message when the increment warrants a review; otherwise it is skipped
  on purpose.
- A build refuses a worktree in which another OpenCode session is running
  (another Hermes profile or a person); read-only roles may run alongside.
- Models normally follow each hidden primary's pin (plan, review and debug on
  Opus 5.5, build on GPT-6.1 Sol), or the maintainer's opencode_cli.models for
  that role; the record's `engine` names what actually ran. You may pick another
  engine when the work or the Client calls for it: opencode_session models lists
  what you may pass as model (provider/model) and variant (that model's
  reasoning efforts), the defaults per role, and your own models. Your own model
  (your configured one, and a fallback you are answering with now) is refused
  for every role, the default included, so you never judge or QA output from the
  model you run on; on that refusal pick another listed model. A name outside
  the list or not offered by OpenCode is refused, never substituted; report the
  refusal and ask, do not stop the whole job over it. An explicit selection
  binds the rest of that conversation; omitting it keeps the recorded engine.
  The caller still cannot change the executable, environment or permission
  rules. No automatic fallback or retry after uncertain effects.

`opencode_session(action, conversation_id?, …)`

- status reads one owned conversation; list returns this originating session's
  conversations. It is not a cross-session discovery or ownership-transfer API.
  Both also restart a run's lost watcher, which then reads the outcome from
  OpenCode.
- models lists the engines opencode_call accepts (model, variants, context,
  cost), each role's default, and your own models, which are refused.
- wait blocks until the run hands back — finished, uncertain, paused on a
  request you have not answered, or stuck in a provider retry (see "Provider
  limits"), bounded by timeout, opencode_cli.wait_timeout, your tool deadline
  and the turn deadline — and returns the record with waited_seconds and
  timed_out. It spends no model turns; a timed_out reply
  means wait again, steer, or stop, never a status/sleep loop.
- respond(conversation_id, request_id, decision, reason?) answers one pending
  permission request; then it waits like wait. See "Permission requests".
- steer(conversation_id, message) adds an instruction to a running turn. It is
  delivered at the run's next step boundary (a long tool call finishes first)
  and is for course corrections, not new scope.
- diff(conversation_id, patch?) lists the last turn's changed files with
  additions/deletions; patch=true adds the (truncated) patches. It is evidence
  for your QA, not a substitute for reading the worktree.
- stop interrupts the run (its subagents stop with it) and drops instructions
  still parked for it. The record settles within seconds as interrupted.
  Stopping never rolls back Git, application data, provider requests, pushes or
  PRs already created.
- reconcile is only for `unknown` runs: inspect Git changes, the diff and
  possible remote effects first, then pass that evidence. It refuses a run
  OpenCode still executes and a run that is still watched. A record is not proof
  of the observed facts; Engineer remains responsible. Do not reconcile just to
  unlock a retry.

`opencode_history(action, …)` reads OpenCode's own session history across all
projects, including sessions a person ran in the TUI. It launches no agent and
never touches the conversations above: list/get/children for metadata, usage
for tokens and activity over a `[from, to)` window. Titles and costs appear only
with include_title / include_cost; message content never. usage activity is
time assistant steps ran with question waits removed (a permission-prompt wait
still counts) — not human working time.
Check `source` and `status`: a `partial` or database-fallback answer carries
its reason in diagnostics; pass that limitation on rather than filling the gap.
`hermes_history` is the same for Hermes' own sessions across every profile
(profile, platform, lineage); `/activity` shows both tools' activity together.

## Permission requests

OpenCode pauses a run when it needs a decision the policy leaves open: a path
outside the worktree, a build's push, history rewrite, branch move or package
runner, an Issue write without issue_approval, or a subagent command outside
that subagent's own allowlist. The run turns `waiting`, the call hands back, and
`pending` lists each request: action, resources, the pattern a broader approval
would cover (`save`), whether a subagent asked, and `expires_at`.

Decide each one against the Client's quoted approval and the mode's scope:

- inside the approved scope → `once`;
- outside the scope or unclear → `reject` with a short reason OpenCode can act
  on, then relay the decision to the Client if the work needs it.

There is no broader approval: `always` would save a project-wide approval
people's own sessions inherit, and a session-wide one would reach every
subagent. If the same request keeps recurring inside scope, say in the next
message how to avoid it (for example, which command to use). A request left unanswered is rejected at `expires_at`
(opencode_cli.permission_timeout) and the run continues without it. Force or
protected-branch pushes, merges, `gh api`, repository/Project writes, secret
reads and the person's own denies never reach you: they are denied outright.

## Results

accepted/running mean execution is outstanding. A run belongs to the Hermes
process that started it from a CLI or resident session: if that process ends,
the run is interrupted. Live messaging uses Hermes'
completion notification, sent at every hand-back (finished or waiting). In a
CLI/resident session opencode_call BLOCKS until the run hands back, within
your tool deadline; a resident CLI has no completion wakeup, so blocking is the
cheap path. Never poll: no status/terminal/sleep loops, no ps checks while a
call is outstanding. If a call returns with timed_out or a tool-timeout error,
issue ONE opencode_session wait for the conversation and read its result.

completed means OpenCode reported the turn succeeded, not that the task passed.
Read result for open questions, assumptions and unverified claims, and changes
for what it touched. A question can arrive in an otherwise completed run.
Engineer answers in-scope technical questions and relays material Client
decisions, then continues.

failed means OpenCode reported a failed turn; it can still have partial changes.
A provider_error on it says why (kind limit / auth / other, the model and the
provider's message); see "Provider limits".
interrupted means the run stopped before finishing: your stop, the deadline, or
OpenCode itself (a restarted service ends a turn without an outcome). OpenCode
confirmed nothing still runs, so the conversation can continue: inspect the
diff and worktree, then send the next message on the same conversation — never
a blind replay of the original prompt. unknown means OpenCode could not confirm
the outcome (service unreachable, prompt admission unconfirmed, or a run from
the retired OpenCode 1 runner); it holds the worktree until inspection and
reconcile, even when creating another conversation.

Provider limits. When a model's provider refuses (usage or rate limit, an
overload, an expired login), OpenCode either fails the turn at once or keeps
retrying with backoff. A failure arrives as failed with provider_error. A
retry hands back once while the run is still running, with `retrying` (kind,
message, attempt, which session — a subagent's model can be the one limited)
and a note: at once for a limit, after a few attempts for anything else.
Decide then: wait if it should recover soon; otherwise stop the run and send
the next message on the same conversation with model= another engine from
opencode_session models. Plan, review and debug read only, so they can simply
rerun; for build read the diff first and continue from what is there. A
limited subagent model needs the run's message to name another subagent, or a
Client decision. An auth problem is OpenCode's own provider login: tell the
Client. Never loop on the same limited model.

Every resident turn carries a "Turn budget" line naming when the whole turn
is killed. Give each call a job that fits the remaining budget; a run still
going at the turn deadline is interrupted there. When the remaining budget is
~15 minutes, do not start a new run: ask OpenCode for nothing further, make
sure verified work is committed on the task branch, and end the turn with a
checkpoint report (worktree, branch, HEAD, what is verified, what remains).

An interrupted conversation may be continued by its Client only as a
RECONCILE-ONLY turn (the handoff says so and opencode_call is refused). In it,
inspect each owned child conversation (status, diff, Git and remote effects),
stop or reconcile with observed evidence, and report; do no other work.

A `Warning: Unknown toolsets: opencode, specialist` line at the start of a
resident turn is a plugin-discovery-order artifact, not a missing capability:
the tools load right after it. Do not report it or work around it.

The wrapper keeps plan/review/debug read-only, grants build its worktree edits
and routine commands, rejects default-branch builds, and returns pushes and
Issue writes without the separate grant to you as requests. Command rules are
defence in depth, not an arbitrary-shell/website sandbox. Preserve narrower
Client restrictions in the prompt and verify actual effects; if a restriction
cannot be safely honored, return the limitation instead of widening access.
