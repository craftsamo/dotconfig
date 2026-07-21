# Resume mode — rejoining after an unblock / respawn

Loaded when the task has prior runs/comments (block answered, crash,
timeout). Load it TOGETHER with the underlying mode's reference (usually
`references/implement.md`). The goal: rebuild the dialogue state
mechanically, then rejoin the recorded session — never restart blind.

## Procedure

1. `kanban_show <id>` — read the full comment thread and prior-attempt
   summaries. Rebuild the dialogue state mechanically:
   - **Match every `Q<n>` against a `DECISION(Q<n>)`.** Unanswered Q<n> →
     still open; if it gates the next step, re-block referencing the same n
     (don't renumber, don't re-ask answered questions).
   - **Recompute the effective Authority**: body grant + every `AUTHORITY+:`
     comment (core <Authority>).
2. Confirm the worktree state: `git log --oneline -5`, `git status --short`.
3. **Rejoin the right session** (ids from the latest `STATE:`/`PROGRESS:`
   comment):
   - Blocked **mid-unit** → continue the unit fork:
     `opencode run -s <fork-id> '<follow-up incorporating the DECISION(s)>'`
     (wrapped per PermissionBridge, same model).
   - Between units (or the DECISION invalidates the current unit's approach)
     → fork fresh from P0 per OpenCodeLoop.
   - The DECISION invalidates the plan itself → redo P0 (new master plan),
     attach it, note the supersession.
   - Advisory task → no sessions to rejoin; fold the DECISION(s) into the
     assessment recorded in the last `STATE:` and finish it.
4. Record the outcome in a short `PROGRESS:` comment so the thread stays an
   audit trail.

## Pitfalls

- Restarting work from scratch when a recorded fork id exists — rejoin
  `-s <fork-id>`.
- Re-asking an answered `Q<n>` or renumbering an open one.
- Missing an `AUTHORITY+:` comment and re-blocking for something already
  granted.
- Treating child fan-out tasks as still pending — they may have completed
  during the block; `kanban_show <child-id>` before re-dispatching.

## Verification

- Every open `Q<n>` was matched to its `DECISION(Q<n>)` before work resumed.
- Effective Authority recomputed from body + all `AUTHORITY+:` comments.
- The recorded session was rejoined (or a fresh fork/P0 was justified by the
  DECISION); the outcome is logged as `PROGRESS:`.
