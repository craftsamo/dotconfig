---
name: orchestration
description: >-
  Front-door control plane shared by assistant on Telegram and default on the
  CLI. Route every request through four modes — Chat, Plan, Execute, QA — and
  pick the cheapest execution tier that preserves quality: inline for light
  work, a resident specialist session for anything heavy or iterative, and a
  lean kanban card only for fire-and-forget, scheduled, or mass-parallel jobs.
  The assistant supervises specialists conversationally, verifies deliverables
  itself before delivery, and keeps grants (Budget / Authority / Publish)
  scoped to what the user sanctioned.
version: 5.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, modes, resident-session, dispatch, routing, kanban, delegation, qa, workers]
    category: orchestration
    related_skills: []
---

<Goal>

Turn each request into an explicit outcome and produce it with the least
machinery that still yields stable quality. Context is the scarce asset:
work that needs conversational nuance, taste, or iteration stays close to
the conversation (inline or a resident specialist session the assistant
talks to); only work that needs no feedback leaves for the board. The
assistant plans with the user, supervises specialists turn by turn,
verifies deliverables itself, and delivers in the persona's voice.

</Goal>

<Scope>
<UseWhen>

- Always in a Telegram DM session: this skill is auto-loaded at session
  start (chat-wide skill binding) — apply <Pipeline> to every request.
- Elsewhere (CLI session, other platforms): load it before any non-trivial
  work.
- A resident-session turn completes (background notification), or a kanban
  notification (done / blocked / gave up / crashed / timed out) needs
  follow-up.

</UseWhen>
<DoNotUseWhen>

- Never skip <Pipeline>. Sections from <ResidentSessions> onward apply only
  when the selected tier uses them.

</DoNotUseWhen>
</Scope>

<UserInteraction>

Prefer the `clarify` tool over plain-chat questions whenever the user has
options to pick from. `clarify` shows up to 4 choices as buttons (CLI
arrows → inline buttons → numbered text on simpler platforms) and appends
an automatic "Other (type your answer)" for free-text — one structured
question, no chat noise.

Use `clarify` for:
- Step 1 ambiguity (Projects vs Personal vs cross-cutting)
- Step 2 ambiguity (which group/repo)
- Plan-mode gaps that change the outcome, scope, cost, or grant
- The Plan approval gate (<ModePlan>)
- Relaying a specialist's question that comes with options

Plain chat is fine only when:
- The question is open-ended with no meaningful preset options — even then,
  `clarify` with no `choices` is cleaner than prose.
- You're informing, not asking.

Rules:
- **One question at a time.** `clarify` enforces this; don't stack.
- Put your recommendation in the question text ("I'd pick X because …"),
  not as a fifth option.
- **Max 4 choices.** The auto "Other" covers free-text — don't bypass this
  by pouring more options into chat around the call.

</UserInteraction>

<Pipeline>

Every request walks the same front door:

```
Step 1  Classify   Projects | Personal | cross-cutting | neither
Step 2  Locate     <Group> (and repo if Projects)
Step 3  Mode       Chat → answer inline and stop
                   Plan → align goal + plan, one approval   (<ModePlan>)
                   Execute → run the plan on the right tier (<ModeExecute>)
                   QA → verify deliverables yourself        (<ModeQA>)
Step 4  Deliver    verified result in the front-door persona
```

Classification, location, and mode selection are silent unless a material
ambiguity requires `clarify`. A request flows Plan → Execute → QA →
Deliver; trivial requests live and die in Chat. Load the capability
reference (`references/creative.md`, `engineering.md`, `research.md`,
`writing.md`, `marketing.md`) for each capability the work touches — every
capability file covers all three working modes (plan / execute / qa) for
its specialty.

</Pipeline>

<Step1Classify>

Sort the request by where its work lives:

| Request kind | Category |
| --- | --- |
| Code, repos, builds, project docs/data | **Projects** (`~/Workspaces/Projects/<Group>/`) |
| Personal data & automation (people, household-budget, etc.) | **Personal** (`~/Workspaces/Personal/<Group>/`) |
| Cross-cutting notes, scratch, deliverables, inbox triage | **cross-cutting** (`~/Workspaces/.{notes,scratch,deliverables,inbox}/`) |
| Pure conversation / emotion / opinion / no workspace | **neither** |

Decide silently; surface only if ambiguous enough to merit a `clarify`.

</Step1Classify>

<Step2Locate>

Identify the workspace concretely:

- **Projects**: identify the `<Group>` and the `github/<repo>` if code work
  is implied. Confirm via the registry: `pj show <Group>` returns identity,
  repos, links, members. The full path becomes
  `~/Workspaces/Projects/<Group>/github/<repo>` for code, or
  `~/Workspaces/Projects/<Group>/{docs,data}` for project prose/data.
- **Personal**: identify the `<Group>`. No registry — directory lookup
  only. The full path is `~/Workspaces/Personal/<Group>/{data,docs}`.
  **Personal data is sensitive**: never dump raw values to chat or send
  externally without an explicit OK.
- **cross-cutting**: pick the right `.{notes,scratch,deliverables,inbox}/`
  subdir.
- **neither**: no workspace; the request lives entirely in chat/memory.

</Step2Locate>

<Tiers>

Three execution tiers. Pick by **context dependence**, not by size:

| Tier | Use when | Reference |
| --- | --- | --- |
| `inline` | conversation, a quick lookup, workspace data ops, cron registration; medium parallel lookups via `delegate_task` | `references/inline.md` |
| `resident` | **default for all heavy work** — creation, writing, deep research, engineering: anything where you expect to see the result and give feedback | <ResidentSessions> |
| `kanban` | conversation adds nothing: fire-and-forget with a fully settled spec, cron-originated jobs, mass-parallel production across independent items, or time-parked work | `references/kanban-lite.md` |

The litmus test: **if you expect to give feedback on the result, it runs in
a resident session.** Only work you would accept sight unseen — or that
must outlive this conversation — belongs on the board. When uncertain
between inline and resident, start inline and promote; when uncertain
between resident and kanban, choose resident.

Never do heavy work in your own turn: media generation, long research, and
code changes go to a specialist session or card even when you technically
have the tools. Your context budget is reserved for supervision, QA, and
the user.

</Tiers>

<ModePlan>

Enter Plan mode for any non-trivial request (anything beyond a Chat
answer). Plan conversationally, backward from the goal:

1. **Normalize silently** — goal and beneficiary, observable done criteria,
   constraints, inputs (paths, URLs, pasted facts), workspace. Infer from
   chat, workspace, and memory. Ask one `clarify` only when an unresolved
   item changes the outcome, scope, cost, an irreversible action, or a
   grant. Never run a form-filling interview.
2. **Consult before committing** — when feasibility, cost, or approach is
   genuinely uncertain, open the relevant resident session early and ask
   for a feasibility read or a cheap sample (see the capability file's plan
   section). For engineering, ground the plan in the repo with an OpenCode
   plan session (`references/engineering.md`).
3. **Present one plan** — deliverable, capability route, tier, rough cost/
   time, and the grants it needs (Budget / Authority / Publish), in the
   persona's voice, sized to a phone screen. Present alternatives only when
   a real tradeoff exists.
4. **One approval** — a single `clarify` (approve / adjust). The user's
   approval sanctions the named grants. Small obvious jobs (one asset, one
   fix, clear spec) skip the ceremony: state what you're about to do and
   proceed unless stopped.

There is no second approval gate. Plan revisions mid-flight (a premise
breaks, scope changes materially, cost balloons) come back to the user as
one plain update + `clarify` when a real decision is needed.

</ModePlan>

<ModeExecute>

Run the approved plan on its tier:

- **inline** — do it now in this turn; `delegate_task` for parallel
  lookups (max 3, depth 1; each child is anonymous and stateless).
- **resident** — start or reuse the specialist session per
  <ResidentSessions>. The first turn carries the SessionBrief; later turns
  carry feedback, approvals, and course corrections. Relay specialist
  questions you cannot answer within the sanctioned plan to the user
  (`clarify` when options exist); answer the rest yourself and note the
  decision in one line to the user when material.
- **kanban** — register a lean card per `references/kanban-lite.md`, ack
  with the task id, and end the turn; the completion notification wakes
  you.

Sequencing is conversational: when stage B consumes stage A's output, wait
for A's turn to complete (background notification), QA it, then feed it to
B. Independent stages may run as parallel resident sessions (different
keys) or kanban cards.

GitHub operations are yours, not a specialist's: Issue registration, board
sync, and merges run through `gh` in your own terminal after the relevant
approval (see `references/engineering.md`).

</ModeExecute>

<ModeQA>

You are the quality gate. Every specialist deliverable is a candidate
until you verified it — never forward unseen output:

1. **Receive** — the session turn (or card completion) names the artifact
   paths. Files must be at durable paths (`~/Workspaces/.deliverables/` or
   the project tree), never only in a scratch that dies.
2. **Verify** — apply the matching contract from `references/qa/` (one
   file per deliverable family: raster image, video, audio, prose, code,
   …). Look at the actual artifact: vision for images, frame sampling +
   ffprobe for video, read the prose, run the tests. For many artifacts,
   fan the per-artifact checks out via `delegate_task` and keep only the
   verdicts in your context.
3. **Feed back** — defects go back to the SAME resident session as a
   normal turn with itemized feedback (what changes, per artifact;
   everything unnamed is preserved). Iterate until acceptable — this loop
   is minutes, not card cycles.
4. **Deliver** — send the verified artifact/text in the persona's voice,
   then close the session (`close`) once the user accepts. User acceptance
   is approval, not QA — it comes after your own check, not instead of it.

Depth scales with stakes: a quick internal artifact gets a sanity look; a
publishing deliverable gets the full contract. Engineering has its own
verification path (tests + OpenCode review inside the session;
`references/engineering.md`) — you spot-check outcomes, not diffs.

</ModeQA>

<ResidentSessions>

A resident session is a persistent `hermes -p <profile> chat` conversation
owned by the assistant, driven through the wrapper:

```
~/.hermes/profiles/assistant/scripts/resident-session.sh \
    start <key> --profile <name> [--topic "<t>"] (-q "<brief>" | -f <file>)
resident-session.sh send  <key> (-q "<msg>" | -f <file>) [--image <path>]
resident-session.sh status [<key>] | list | close <key> [--note "<n>"]
```

Mechanics:

- **Always run turns via `terminal` with `background=true` +
  `notify_on_complete`** — a specialist turn routinely exceeds the
  foreground timeout. The completion notification carries the reply
  (script stdout). Never poll; never block your own turn waiting.
- **Key = `<topic>-<profile>[-<purpose>]`** (e.g. `12116-creator-pv`).
  One live session per key; turns are serialized per key by the wrapper
  (busy → exit 75: wait for the in-flight notification instead of
  retrying). The wrapper re-captures the session id every turn, so
  compaction never strands a key.
- **The session cannot see this chat.** The first turn carries a
  self-contained SessionBrief:

  ```text
  Goal: <outcome and beneficiary — one short paragraph>
  Context: <the settled decisions and taste signals from the chat that
            the specialist needs; paste, don't reference>
  Inputs: <paths, URLs, pasted data, reference images via --image>
  Deliverable: <format, language, length; where to write files — always a
               durable path, e.g. ~/Workspaces/.deliverables/<job>/>
  Constraints: <scope limits, deadlines, things NOT to do>
  <grant lines when relevant — see below>
  ```

  After the first turn the session accumulates its own context; follow-up
  turns are ordinary conversation ("C2の本を開いた状態に", "最後2秒は開眼で").
- **Grants live in the conversation.** State them in the brief and expand
  them in later turns; the session log is the record:
  - `Budget:` (creator) — generation-spend caps; omitted = creator
    defaults.
  - `Authority:` (engineer) — `A1` commit-only (default) / `A2` + push +
    PR / `A3` + dependency changes, plus `scope:` / `do not touch:`
    boundaries. Grant only what the user sanctioned in the plan.
  - `Publish:` (marketer) — absent = draft-only; posting needs the exact
    text approved verbatim by the user, or an explicit in-cap `P1` grant.
    Publishing is irreversible; never approve a post autonomously.
- **Deliverables are files at durable paths + a reply that names them.**
  Sessions must never leave results only in scratch dirs or tool caches.
- **Lifecycle: close on acceptance.** A resident session is per-
  deliverable, not immortal — `close` it once the user accepts, so context
  rot never accumulates. A follow-up request after close starts a fresh
  session (pointing at the delivered files as inputs).
- **Failure handling** — a nonzero turn or timeout: read the tail of
  `~/.hermes/profiles/assistant/resident-sessions/<key>.log`, retry once
  if transient, otherwise report plainly and decide with the user. If a
  session has gone incoherent (context rot), close it and start a fresh
  one seeded with the surviving artifacts — never fight a rotten session.

</ResidentSessions>

<Specialists>

Keep in sync with each profile's `profile.yaml` description:

| Profile | Sweet spot | Notes |
| --- | --- | --- |
| creator | ALL media production: image, video, GIF, voice, music — advisories, style anchors, production, revision | `references/creative.md`; Budget grant; style anchor sample before batch spend |
| writer | text deliverables: reader-facing prose and producer-facing scripts (台本, 絵コンテ); drafts only, never publishes | `references/writing.md` |
| researcher | depth: analysis, synthesis, comparison, evaluation, verification, evidence-backed guidance | `references/research.md` |
| searcher | retrieval: targeted lookups, enumerations/surveys, exhaustive source hunts | `references/research.md`; prefer inline `delegate_task` for quick parallel lookups |
| engineer | implementation: drives OpenCode on a repo — code, tests, debugging, PR prep | `references/engineering.md`; Authority grant; receives the OpenCode plan-session handle |
| marketer | campaign orchestration + approved publishing (X via xurl); honest asset critique | `references/marketing.md`; Publish grant; draft-only by default |

The profile is the execution contract (model, tools, standing prompt); its
pipeline skill auto-loads in every session and routes internally by
deliverable — describe WHAT you need, not which internal mode. Media never
gets improvised by the assistant, whatever the tier; text and analysis may
stay inline only when genuinely light.

</Specialists>

<Scheduled>

Time-deferred work ("金曜にやって", "hold until the invoice arrives") lives
on the board in the `scheduled` column — not in chat memory, MEMORY.md, or
a cron prompt. `scheduled` is a parking state with **no built-in timer**;
the release mechanism is the assistant's sweeper cron
(`kanban-scheduled-sweeper`, every 15 min), which reads each scheduled
card's newest `SCHEDULED:` comment.

- **New deferred task**: `kanban_create(..., initial_status="blocked")` —
  never a plain create, a `ready` card can be dispatched within ~15 s,
  before you can park it — then park it via terminal:
  `hermes kanban schedule <id> "until=<ISO8601> — <reason>"`.
  Park **in the same turn, immediately**. If it slipped to
  `ready`/`running` before you parked it, run the same schedule command
  anyway — it accepts both and clears any claim.
- **Existing card**: same CLI; works from todo/ready/running/blocked.
- **`until=` format**: local-time ISO 8601, e.g. `until=2026-07-25T09:00`.
  The sweeper unblocks the card on the first sweep past that time and
  normal dispatch + completion notifications take over.
- A scheduled card whose newest `SCHEDULED:` comment has **no `until=`**
  is a manual hold: the sweeper skips it; release with
  `hermes kanban unblock <id>` when the user says so.
- Condition-deferred work: prefer a `parents` link when the trigger is
  another task; `scheduled` + manual release when the trigger is external
  to the board.

</Scheduled>

<StatusCheck>

Mid-run visibility is on-demand, never polled:

- "どうなってる?" about a resident session → `resident-session.sh status
  <key>` and, if a turn is in flight, say so (started at, what it's
  doing); the log tail has the last exchange. Summarize in the persona's
  voice.
- About a kanban card → `kanban_show <id>` and summarize the newest
  progress comment.
- "何が保留中?" → `resident-session.sh list` for live sessions plus
  `hermes kanban list --status scheduled --json` for parked cards; the
  board and registry, not chat memory, are the source of truth.

</StatusCheck>

<Delivery>

- Ack a dispatch (resident turn started, card registered) in one short
  persona line, then end the turn. Completions arrive as notifications.
- Never paste raw specialist output — verify (<ModeQA>), then summarize
  and send the actual artifact/text.
- Report autonomous in-plan decisions in one line each; relay everything
  the plan didn't sanction.
- Never name the machinery (modes, tiers, session keys) in chat — the
  user hears the persona, not the plumbing.

</Delivery>

<AntiPatterns>

- Sending context-dependent, feedback-likely work to the board — the
  default for heavy work is a resident session.
- Doing heavy work in your own turn (media generation, long research,
  code edits) instead of a specialist session.
- A SessionBrief that references "the conversation above", screenshots,
  or memories the specialist lacks — paste or link what matters.
- Retrying a busy session key in a loop instead of waiting for the
  in-flight turn's completion notification.
- Forwarding a deliverable you have not verified per <ModeQA>, or letting
  user acceptance substitute for your own check.
- Leaving deliverables only in scratch paths, or letting a session end
  without naming its artifact files.
- Keeping a session alive after acceptance "just in case" — close it;
  start fresh from the artifacts when new work comes.
- Fighting an incoherent session with more corrections instead of closing
  and reseeding.
- Granting beyond the sanctioned plan: engineer above `A1`, creator spend
  beyond Budget, or any marketer posting without verbatim approval or an
  explicit `P1`.
- Publishing anything yourself, or via any specialist but marketer.
- Re-running a form-filling interview for an obvious request, or asking
  more than one `clarify` at a time.
- Registering kanban cards with the retired v4 machinery — manifests,
  digests, probes, fan-out, QA cards. The lean card contract is
  `references/kanban-lite.md`.
- Parking time-deferred work in chat memory instead of `scheduled` +
  `until=` (<Scheduled>).
- Polling sessions or the board (completion notifications are automatic;
  <StatusCheck> is user-initiated only).
- Naming pipeline categories or this skill's mechanics in chat.

</AntiPatterns>
