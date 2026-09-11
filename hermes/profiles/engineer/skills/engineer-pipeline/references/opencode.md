# OpenCode - shared transport contract

Read before the first wrapper call in any mode. This file owns session and
result semantics; Plan/Build/QA/Assess own what to request and how to judge it.
Never call raw opencode run, attach to a human server, or substitute another
coding agent to bypass the wrapper. OpenCode still owns its internal tools and
development methods; concise prompts carry the job-specific delta, not copied
global instructions or whole Skill bodies.

## Calls

`opencode_call(directory?, agent, message, conversation_id?, fork?, approval?, issue_approval?)`

- New conversation: directory is an absolute Git worktree root. Agent is plan,
  build, review or debug. Use the returned opaque conversation_id for subsequent
  calls. Never infer "the last session" or supply an arbitrary OpenCode session ID.
- A conversation is bound to its originating Hermes session, worktree and branch.
  To move to a new task worktree, start a new conversation with the actual approved
  plan as context. A copied plan does not grant additional work.
- fork=true requires an owned conversation and returns a new conversation handle
  and OpenCode session, preserving the source. It forks the current state only.
- approval is the Client's explicit scoped implementation/write decision as text,
  not a boolean. The initial build call needs it; continuations retain it.
  issue_approval separately quotes the explicit current-job Issue-management
  request. Both are operating-contract records, not authentication.
- Models normally follow OpenCode's configured agent defaults. Maintainer
  opencode_cli.models may override per-agent models; the caller cannot change
  executable, environment or arbitrary permission JSON. No automatic fallback
  or retry after uncertain effects. Private logs are not public deliverables.

`opencode_session(action, conversation_id?, evidence?)`

- status reads one owned conversation; list returns this originating session's
  conversations. It is not a cross-session discovery or ownership-transfer API.
- stop records a stop request for the live runner. The reply does not prove the
  process stopped. Inspect status afterward. Stopping never rolls back Git,
  application data, provider requests, pushes or PRs already created.
- reconcile is an explicit recovery after uncertain work: inspect process state,
  Git changes and possible remote effects first, then pass that evidence. It
  refuses an active runner/process group. A record is not proof of the observed
  facts; Engineer remains responsible. Do not reconcile just to unlock a retry.

## Results

accepted/running mean execution is outstanding. Live messaging uses Hermes'
completion notification; CLI/resident calls wait within a finite inherited
deadline. Do not poll in short loops. Unknown results hold the worktree until
inspection and reconciliation, even when creating another conversation.

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
