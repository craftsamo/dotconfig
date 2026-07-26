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
   comment — the base id and the current Wave's fork id):
   - **Re-establish the base if needed.** The base plan session is recorded;
     reuse it if `opencode session list` still shows it. If it's gone
     (worktree preserved, session lost), re-seed the base from the attached
     Wave outline (`references/implement.md` "Base") before forking.
   - Blocked **mid-Wave** → continue that Wave's build fork:
     `opencode run -s <build-fork-id> '<follow-up incorporating the
     DECISION(s)>'` (wrapped per PermissionBridge, same model).
   - **Between Waves** (or the DECISION invalidates the current Wave's
     approach) → fork fresh from the base for the current Wave per
     OpenCodeLoop (decompose → confirm → build); prior Waves are committed, so
     ground on the worktree.
   - The DECISION **invalidates the outline itself** → the Waves changed:
     re-establish the base from the revised outline, attach it, note the
     supersession; Waves already committed stay as they are.
   - **Read-only slice** (orient / advisory / plan) → no build sessions to
     rejoin; fold the DECISION(s) into the deliverable recorded in the last
     `STATE:` and finish it.
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
- The recorded session was rejoined (or a fresh fork from the base was
  justified by the DECISION); the outcome is logged as `PROGRESS:`.
