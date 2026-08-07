# Engineering — execute

The specialist is the **engineer** resident session, which drives
OpenCode on the repo. The engineer is your hands, not a contractor:
you release the approved decomposition **one unit at a time** and
hold the quality gate between units. Engineering is
**resident-only**: no `card_units` — implementation is never a card.

One boundary governs every write: **codebase-dependent writes go
through OpenCode; pure bookkeeping stays direct.** Commits, pushes,
PR creation/upkeep, and Issue/epic drafting + registration need the
worktree and the repo's conventions — whoever supervises them
(engineer normally, you for your own ops) runs them as OpenCode
sessions, where the git/PR/project skills live. Merges, Roadmap-board
status sync, and repo lifecycle (`gh repo create` / `ghq` / `pj`)
need no codebase and stay your direct `gh`/`pj` calls.

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
   unit inside OpenCode (plan fork → confirm → build) under its own
   discipline (PermissionBridge; model ladder).
2. **Receive the report** — what landed, verification output, session
   ids, open questions. Answer in-plan questions yourself in the next
   turn; relay real decisions to the user. An out-of-grant need
   (dependency, push, architecture) is met with an explicit grant
   expansion in your next turn — the session log records it — but
   only within what the user sanctioned; anything beyond goes to the
   user first. A capability signal or a spec gap pulls the work back
   to Plan, not into another turn.
3. **Gate** — check the report against the QA contract
   (`../../quality-assurance/engineering/index.md`) and the unit's
   done criteria before releasing the next unit. A failed gate goes
   back as a course correction on the SAME unit, never a new one.
4. **Close out the unit** (next section), then release the next.

Course corrections are conversational turns ("そのスキーマはBにして",
"Wave 2 の前にテストを先に"). Long builds are normal **within** a
unit — turns run in background; the completion notification wakes
you. Batch autonomy ("run units 1–3, report once") only when the
plan named it and the user sanctioned it.

## Unit close-out — after the gate passes

- **Purpose unit**: confirm the PR(s) carry `Closes #n` (missing →
  have the engineer fix the PR body in-session); tick the epic's
  sub-issue state and move the Roadmap board item directly. Merge
  waits for the user's go.
- **A1 work where the user wants a PR**: the engineer only committed
  — run OpenCode yourself in the repo
  (`cd <repo> && opencode run --auto '<push the branch and open the
  PR for …>'`); its PR skill resolves the title/body convention and
  Issue links. Never hand-write a PR with raw `gh pr create`.
- **Merge** — yours, direct, on the user's explicit go. After
  merging a stack layer, tell the engineer in the next turn so the
  remaining layers are rebased/retargeted in-session; the next unit
  is released against the updated default branch.
- **Wave unit**: verify the commit landed per the report; nothing
  external to sync.

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

## GitHub ops — assistant-owned

Repo lifecycle, decomposition registration, board sync, and merges
are **your** job, after the relevant approval — the engineer only
works inside a repo you manage, never needs issue-write grants, and
never merges:

- Repo lifecycle (direct): bootstrap (creation, ghq clone, workspace
  link, `pj` registry) per `../../plan/engineering/bootstrap.md` —
  worktree-side establishment is delegable only under an explicit
  `B1`/`B2` grant; the GitHub/registry side never is.
- Register the approved decomposition (via OpenCode): run OpenCode
  in the repo to create the epic + purpose sub-issues from the
  approved decomposition — Issue bodies must be grounded in the
  codebase, and OpenCode's issue/project skills own the formats.
  Then sync the user's Roadmap board directly.
- PRs: at `A1` the engineer only commits — the close-out recipe
  covers the PR; at `A2` the engineer pushes its branch and
  maintains its own PR through OpenCode — a multi-PR purpose grows
  as a stack, one layer at a time — and responds to reviews inside
  the session.
- Merge only on the user's explicit go; merging is never autonomous
  and never the engineer's.

## Pitfalls

- Handing the engineer the whole deliverable or the full
  decomposition at once — the unit loop, not the engineer, owns
  sequencing.
- Handing prose when a base session id exists — the session is the
  handoff, prose drifts.
- Releasing unit N+1 before unit N passed your QA gate and
  close-out.
- Hand-writing Issues or PRs with raw `gh` — codebase-dependent
  writes go through OpenCode, whoever runs them.
- Carrying one engineer session across purposes — per-purpose
  sessions keep an epic rot-free.
- Writing `A2`/`A3` grants the user never sanctioned, or letting a
  session widen its own grant.
- Re-planning inside chat what the engineer's plan fork will do
  better against the live worktree.
- Merging, or letting any session merge, without the user's explicit
  go.
