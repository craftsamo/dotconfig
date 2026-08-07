# Engineering — execute

The specialist is the **engineer** resident session, which drives
OpenCode on the repo. The engineer is your hands, not a contractor:
you release the approved decomposition **one unit at a time** and
hold the quality gate between units. GitHub bookkeeping stays with
you. Engineering is **resident-only**: no `card_units` —
implementation is never a card.

## Resident session

Start the engineer resident session with the SessionBrief plus:

- `Repo:` the absolute worktree path (the engineer works in place; it
  may create its own worktree for isolation when parallel work
  demands it).
- `Authority:` the sanctioned preset + `scope:` / `do not touch:`
  boundaries. The engineer translates it into OpenCode permission
  denies; anything outside the grant comes back as a question in its
  reply.
- For Wave-unit work, `Base session:` the OpenCode plan-session id
  from Plan — the engineer forks it per Wave; the session, not
  prose, carries the plan.

## The unit loop

Supervise as a loop, one unit per turn:

1. **Release one unit** — "implement Wave 1" / "implement Issue #12".
   Never hand over the whole decomposition or the deliverable
   ("build the LP") — sequencing is yours. The engineer details the
   unit inside OpenCode (plan fork → confirm → build) under its own
   discipline (PermissionBridge; model ladder).
2. **Receive the report** — what landed, verification output, session
   ids, open questions. Answer in-plan questions yourself in the next
   turn; relay real decisions to the user.
3. **Gate** — check the report against the QA contract
   (`../../quality-assurance/engineering/index.md`) and the unit's
   done criteria before releasing the next unit. A failed gate goes
   back as a course correction on the SAME unit, never a new one.

Course corrections are conversational turns ("そのスキーマはBにして",
"Wave 2 の前にテストを先に"). The session holds the repo context
across units. Long builds are normal **within** a unit — turns run in
background; the completion notification wakes you. Batch autonomy
("run units 1–3, report once") only when the plan named it and the
user sanctioned it.

## GitHub ops — assistant-owned

Repo lifecycle, Issue registration, board sync, and merges are
**your** job, through your own `gh`/`ghq`/`pj`, after the relevant
approval — the engineer only works inside a repo you manage, never
needs issue-write grants, and never merges:

- Repo lifecycle: bootstrap (creation, ghq clone, workspace link,
  `pj` registry) per `../../plan/engineering/bootstrap.md` —
  worktree-side establishment is delegable only under an explicit
  `B1`/`B2` grant; the GitHub/registry side never is.
- Register the approved decomposition yourself: `gh issue create` per
  purpose (epic linked), then keep the epic and the user's Roadmap
  board in sync as units land.
- PRs: at `A1` the engineer only commits — you push/open the PR
  yourself if the user wants one; at `A2` the engineer pushes its
  branch and maintains its own PR — a multi-PR purpose grows as a
  stack, one layer at a time — and responds to reviews inside the
  session.
- Merge only on the user's explicit go; merging is never autonomous
  and never the engineer's.

## Pitfalls

- Handing the engineer the whole deliverable or the full
  decomposition at once — the unit loop, not the engineer, owns
  sequencing.
- Handing prose when a base session id exists — the session is the
  handoff, prose drifts.
- Releasing unit N+1 before unit N passed your QA gate.
- Writing `A2`/`A3` grants the user never sanctioned, or letting a
  session widen its own grant.
- Re-planning inside chat what the engineer's plan fork will do
  better against the live worktree.
- Merging, or letting any session merge, without the user's explicit
  go.
