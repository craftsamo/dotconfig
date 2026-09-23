# OpenCode - shared transport contract

Read before the first wrapper call in any mode. This file owns session and
result semantics; Plan/Build/QA/Assess own what to request and how to judge it.
Never call raw opencode run, attach to a human server, or substitute another
coding agent to bypass the wrapper. OpenCode still owns its internal tools and
development methods; concise prompts carry the job-specific delta, not copied
global instructions or whole Skill bodies.

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
- plan, build and review run on hidden OpenCode primaries built for this
  transport (hermes-plan / hermes-build / hermes-review), not the human TUI
  agents: they take no questions, never wait for approval, do not hand off
  between plan and build themselves, and answer with fixed report headings.
  Plan returns Client decisions as `Q<n>:` lines with a recommended default
  already taken; answer them with `DECISION(Q<n>): …` on the same
  conversation. Build delegates every check to a verifier subagent and runs
  a reviewer pass ONLY when the message asks for one ("run a review pass" /
  "deep review <area>"); Review likewise runs reviewer-deep only on request.
  Say so in the message when the increment warrants it; otherwise it is
  skipped on purpose. debug is the ordinary primary.
- Models normally follow OpenCode's configured agent defaults (plan and
  review on Opus 5.5, build on GPT-6 Sol, independent of the model this
  profile runs on, so your challenge and QA stay cross-family). Maintainer
  opencode_cli.models may override per-agent models. A Client may ask for a
  specific engine: pass model (provider/model) and/or variant (reasoning effort
  such as high) from the maintainer allowlists opencode_cli.allowed_models /
  allowed_variants. A name outside the allowlist is refused, never substituted;
  report the refusal and ask, do not stop the whole job over it. An explicit
  selection binds the rest of that conversation; omitting it keeps the recorded
  engine. The caller still cannot change executable, environment or arbitrary
  permission JSON. No automatic fallback or retry after uncertain effects.
  Private logs are not public deliverables.

`opencode_session(action, conversation_id?, evidence?, timeout?)`

- status reads one owned conversation; list returns this originating session's
  conversations. It is not a cross-session discovery or ownership-transfer API.
- wait blocks until the run leaves accepted/running (bounded by timeout,
  opencode_cli.wait_timeout and the turn deadline) and returns the record with
  waited_seconds and timed_out. It spends no model turns; a timed_out reply
  means wait again, inspect, or stop, never a status/sleep loop.
- stop records a stop request for the live runner. The reply does not prove the
  process stopped. Inspect status afterward. Stopping never rolls back Git,
  application data, provider requests, pushes or PRs already created.
- reconcile is an explicit recovery after uncertain work: inspect process state,
  Git changes and possible remote effects first, then pass that evidence. It
  refuses an active runner/process group. A record is not proof of the observed
  facts; Engineer remains responsible. Do not reconcile just to unlock a retry.

## Results

accepted/running mean execution is outstanding. Live messaging uses Hermes'
completion notification. In a CLI/resident session opencode_call BLOCKS until
the run finishes (the Engineer tool deadline is set above opencode_cli.timeout
for this); a resident CLI has no completion wakeup, so blocking is the cheap
path. Never poll: no status/terminal/sleep loops, no ps checks while a call is
outstanding. If a call does return a tool-timeout error, issue ONE
opencode_session wait for the conversation and read its result. Unknown
results hold the worktree until inspection and reconciliation, even when
creating another conversation.

Every resident turn carries a "Turn budget" line naming when the whole turn
is killed. Give each blocking call a job that fits the remaining budget; an
OpenCode run cut by the turn deadline is unknown and leaves a stale hold on
its worktree that only this session can reconcile. When the remaining budget
is ~15 minutes, do not start a new run: ask OpenCode for nothing further, make
sure verified work is committed on the task branch, and end the turn with a
checkpoint report (worktree, branch, HEAD, what is verified, what remains).

An interrupted conversation may be continued by its Client only as a
RECONCILE-ONLY turn (the handoff says so and opencode_call is refused). In it,
inspect each owned child conversation (status, process liveness, event log,
Git and remote effects), stop/reconcile with observed evidence, and report;
do no other work.

A `Warning: Unknown toolsets: opencode, specialist` line at the start of a
resident turn is a plugin-discovery-order artifact, not a missing capability:
the tools load right after it. Do not report it or work around it.

completed means the CLI ended with a matching JSON stop event, not that the task
passed. Read result for open questions, assumptions and unverified claims. A
question can arrive in an otherwise completed run. Engineer answers in-scope
technical questions and relays material Client decisions, then continues.

failed can still have partial changes. unknown includes interrupted, malformed
or unconfirmed completion. Neither permits blind replay. An error event is an
error even when the CLI exits zero. Use the private log only for necessary
diagnosis; never paste credentials, tool inputs or raw private traces into PRs.

The wrapper applies read-only policies to plan/review/debug and grants build's
permitted branch/PR surface. It rejects default-branch builds and denies Issue
writes without the separate grant. Command rules are defence in depth, not an
arbitrary-shell/website sandbox. Preserve narrower Client restrictions in the
prompt and verify actual effects; if a restriction cannot be safely honored,
return the limitation instead of widening access.
