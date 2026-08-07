# Engineering — execute

The specialist is the **engineer** resident session, which drives
OpenCode on the repo. The engineer is your hands, not a contractor:
you release the approved decomposition **one unit at a time** and
hold the quality gate between units. Everything around the units —
decomposition registration, close-out, PRs, merges, repo lifecycle —
is yours, per `github-ops.md`: codebase-dependent writes through
OpenCode, pure bookkeeping direct. Engineering is **resident-only**:
no `card_units` — implementation is never a card.

## Resident session

Start the engineer resident session with the SessionBrief plus:

- `Repo:` the absolute worktree path.
- `Authority:` the sanctioned preset + `scope:` / `do not touch:`
  boundaries. The engineer translates it into OpenCode permission
  denies; anything outside the grant comes back as a question in its
  reply.
- For Wave-unit work, `Base session:` the OpenCode plan-session id
  from Plan — the engineer forks it per Wave; the session, not
  prose, carries the plan.

Session lifetime follows the unit kind:

- **Purpose units: one session per purpose.** Open with `Issue: #n`,
  close on the purpose's acceptance, start the next purpose as a
  fresh session — context travels through the worktree and the
  Issue, not the chat log, so rot never accumulates across an epic.
- **Wave units: one session for the whole job.** The job is small by
  definition; the session spans its Waves and closes on delivery.

## The unit loop

Supervise as a loop, one unit per turn:

1. **Release one unit** — "implement Wave 1" / "implement Issue #12".
   Never hand over the whole decomposition or the deliverable
   ("build the LP") — sequencing is yours. The engineer details the
   unit inside OpenCode under its own discipline.
2. **Receive the report** — what landed, verification output,
   session ids, open questions. Answer in-plan questions yourself in
   the next turn; relay real decisions to the user. An out-of-grant
   need is met with an explicit grant expansion in your next turn —
   only within what the user sanctioned; anything beyond goes to the
   user first. A capability signal or a spec gap pulls the work back
   to Plan, not into another turn.
3. **Gate** — check the report against
   `../../quality-assurance/engineering/index.md` and the unit's
   done criteria. A failed gate goes back as a course correction on
   the SAME unit, never a new one.
4. **Close out** per `github-ops.md`, then release the next unit.

Course corrections are conversational turns ("そのスキーマはBにして",
"Wave 2 の前にテストを先に"). Long builds are normal **within** a
unit — turns run in background; the completion notification wakes
you. Batch autonomy ("run units 1–3, report once") only when the
plan named it and the user sanctioned it.

## Parallel units

Independent units may run as parallel engineer sessions — only when
their `scope:` boundaries are disjoint:

- One session per unit, distinct keys (`<topic>-engineer-<unit>`),
  each in its own worktree (tell the session its work runs in
  parallel so it isolates itself).
- Units touching shared foundations (schema, shared layout, config)
  never parallelize — sequence them.
- The frontier rule (execute index) applies: release only units
  whose inputs already passed your QA.

## Mechanics leaves

| Leaf | Owns |
| --- | --- |
| `github-ops.md` | the write boundary, decomposition registration, unit close-out, PRs / merges / stacks, repo lifecycle |

## Pitfalls

- Handing the engineer the whole deliverable or the full
  decomposition at once — the unit loop, not the engineer, owns
  sequencing.
- Handing prose when a base session id exists — the session is the
  handoff, prose drifts.
- Releasing unit N+1 before unit N passed your QA gate and
  close-out.
- Carrying one engineer session across purposes — per-purpose
  sessions keep an epic rot-free.
- Writing `A2`/`A3` grants the user never sanctioned, or letting a
  session widen its own grant.
- Re-planning inside chat what the engineer's plan fork will do
  better against the live worktree.
- Hand-writing Issues or PRs with raw `gh`, merging without the
  user's explicit go, or letting any session merge — the write
  boundary and merge gate live in `github-ops.md`.
