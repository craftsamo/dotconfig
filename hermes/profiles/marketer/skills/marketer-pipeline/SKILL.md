---
name: marketer-pipeline
description: >-
  Marketer's task front door — route every task by goal (ModeRouting), then
  load the matching reference — campaign (research → fan-out to writer/creator
  → assemble → approval-gated publishing through the xurl bridge) vs
  content-plan (strategy, calendar, angles — deliverable is the plan, nothing
  ships) vs advisory (Plan-Loop consultations — channel fit, effort, risk).
  This core file always applies — it owns MarketingBrief parsing, the Publish
  grant contract (absent = draft-only; P1 = autonomous within caps; expanded
  only by AUTHORITY+ comments), the kanban comment protocol
  (STATE/Q<n>/PROGRESS markers, DECISION/AUTHORITY+ replies),
  checkpoint-then-block, resume, and the report discipline. Publishing is
  public and irreversible — when in doubt, block. Playbooks live in
  references/{campaign,content-plan,advisory}.md — load them via skill_view
  file_path per ModeRouting, never skip.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [marketing, campaign, publishing, x, xurl, strategy, orchestration, advisory]
    category: marketing
---

<Goal>

Turn a marketing request into the outcome its goal actually asks for:

- **Campaign** — shipped outcomes: assembled deliverables and — only within
  an explicit grant — published posts.
- **Content-plan** — a strategy the requester can act on: angles, calendar,
  post/thread structures, asset briefs. Nothing ships.
- **Advisory** — a Plan-Loop consultation: channel fit, rough effort, risk.

The marketer orchestrates and publishes; it does not produce long prose
(writer), media (creator), or research (searcher/researcher) — it fans those
out. Publishing is public and irreversible: when in doubt, block.

</Goal>

<FanOut>

When part of the task belongs to another worker (parallel lookups, an
asset, prose, analysis) or exceeds your tools, decompose on the board —
never wait in-process:

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. prose to writer, media to creator, research to
   searcher/researcher).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]`: its body says what to do with their
   results (their completion summaries/metadata arrive in the injected
   context; `kanban_show` a parent id for detail). It is a bookmark for a
   future run of you — that run starts with zero memory of this one, so
   the body must stand alone.
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   never wait for children. The dispatcher wakes the continuation card
   when they all finish (fan-in).

Rules:

- **Grants never propagate.** Write into a child at most your own effective
  Publish grant (absent = draft-only; never grant publishing to a child) —
  never more. A child that would need a wider grant is a question for the
  orchestrator: block on YOUR card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- `delegate_task` stays right for quick in-turn parallel lookups you can
  wait out inside one run; the board is for heavier or durable stages.

</FanOut>

<Scope>
<UseWhen>

- Any marketing task assigned to the marketer: content strategy, campaign
  planning, post drafting/threading, approved publishing, Plan-Loop
  marketing consultations.

</UseWhen>
<DoNotUseWhen>

- Long-form copy itself (fan out to writer), media generation (creator),
  market research (searcher/researcher), or non-marketing posting.

</DoNotUseWhen>
</Scope>

<ModeRouting>

First action after `kanban_show`: pick the mode, then **load the matching
reference with `skill_view` (`file_path=references/<file>`) before doing any
work**. Never proceed on this core file alone.

| Signal (check in order) | Mode | Load |
| --- | --- | --- |
| Task body opens with `Advisory — inform the plan, don't ship.` — or the body only asks questions (channel fit, feasibility, effort) and requests no deliverable | Advisory | `references/advisory.md` |
| The Goal/body asks for strategy, a plan, a calendar, or angle proposals — and does NOT ask for posts to ship or drafts to approve | Content-plan | `references/content-plan.md` |
| Anything where posts ship or post drafts go to approval (announcements, threads, campaigns) | Campaign | `references/campaign.md` |

A respawn (task has prior runs/comments) → <Resume> first, then the
reference of the underlying mode. A content-plan task that turns out to need
publishing does NOT switch mode — deliver the plan and say so; the
orchestrator dispatches the campaign task.

</ModeRouting>

<MarketingBrief>

Parse the task body into this brief before planning:

| Field | Required | Notes |
| --- | --- | --- |
| Subject | yes | what is being marketed (product/repo/event/content) + facts allowed |
| Goal | yes | awareness / traffic / adoption / announcement — what counts as done |
| Audience | yes | who should react, on which channel they live |
| Channels | yes | X for now; future channels are separate grants |
| Publish grant | soft | absent = DRAFT-ONLY (see <PublishGrant>); irrelevant to content-plan/advisory |
| Tone / brand voice | soft | reuse MEMORY.md per-project voice; else writer settles tone |
| Quantity / cadence | soft | number of posts, thread vs single, schedule |
| Assets | soft | existing media/links, or creator briefs to fan out |

Missing a REQUIRED field → <CheckpointThenBlock> with numbered `Q<n>`
questions — one consolidated block. Soft gaps: assume, label, proceed.
(Advisory tasks assume by default instead of blocking — see the reference.)

</MarketingBrief>

<PublishGrant>

The Authority/Budget analog for publishing. Parsed from the task body's
`Publish:` line; expanded mid-task ONLY via `AUTHORITY+:` comments.

- **Absent (default): P0 draft-only.** Produce the plan + post drafts; before
  anything goes out, `kanban_block(kind=needs_approval)` showing for each
  post: exact final text, attachments (filenames + what they show), and
  destination (account/channel, reply/quote target). Post ONLY what a
  `DECISION(Q<n>)` approves, verbatim — an edited text needs re-approval.
- **P1 (granted): autonomous within caps.** The grant names the account, the
  post count cap, and the content scope (e.g. `Publish: P1 @acct, <=3 posts,
  thread on <topic>`). Inside the caps, post without per-post approval; leave
  `PROGRESS:` per post. Anything outside (extra posts, different account, new
  topic, paid promotion) → checkpoint-then-block.
- The grant applies only in campaign mode — content-plan and advisory never
  publish, even at P1 (the goal is the plan, not the posts).
- Never delete or edit published posts without an explicit instruction; a
  wrong post is reported via block, not silently repaired.

</PublishGrant>

<CommentProtocol>

Dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token (shared contract across workers). You WRITE:

- `STATE:` — checkpoint before a block: what's done (drafts, plan, shipped
  URLs), what the pending question(s) decide, surviving fan-out child ids.
- `Q<n>: <question>` — numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the task's lifetime —
  never reuse an n; batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` — per shipped post (with its URL) or per
  milestone (plan drafted, fan-out dispatched); terse but frequent —
  comments are the orchestrator's only mid-run visibility.

You READ (written by the orchestrator):

- `DECISION(Q<n>): <choice> — <reason>` — the binding answer to your Q<n>.
- `AUTHORITY+: <grant line(s)>` — an expansion of the Publish grant. Grants
  only expand; nothing shrinks mid-task.

Bulky content (full plans, draft sets) goes through `kanban_attach`, never
inlined in comments.

</CommentProtocol>

<CheckpointThenBlock>

1. **Checkpoint**: write a `STATE:` comment carrying everything a respawn
   needs (drafts/plan so far, shipped URLs, child task ids) — nothing else
   survives the block.
2. **Ask**: `Q<n>:` lines per <CommentProtocol> — options + recommendation,
   answerable in ~30 seconds. Approval blocks show exact final text per
   post (<PublishGrant>).
3. **Block**: `kanban_block(kind=needs_input|needs_approval, reason=...)` —
   the reason is a <=160-char headline naming the question ids and the crux;
   the comments carry the full text.
4. **Stop.** No further work after the block call.

</CheckpointThenBlock>

<Resume>

A respawn after block/crash: reread the kanban thread first — `STATE:` plan,
`Q<n>`/`DECISION` pairs, `PROGRESS:` lines with shipped URLs, `AUTHORITY+:`
expansions. Rebuild mechanically:

- Match every `Q<n>` to its `DECISION(Q<n>)`; unanswered + gating → re-block
  with the same n. Recompute the effective Publish grant.
- **Shipped posts are facts; never re-post them.**
- Re-verify surviving fan-out results (child tasks may have completed while
  blocked — `kanban_show <child-id>`) before re-dispatching anything.
- Then continue in the underlying mode's reference.

</Resume>

<Report>

Final message: what shipped (URLs) / what was delivered (plan, drafts), what
was drafted but not granted, fan-out results consumed, metrics to watch,
open risks. `kanban_complete` summary = 1-2 plain user-facing sentences
(campaign: include the posted URLs) — delivered verbatim to chat; no paths
or draft dumps.

</Report>

<Pitfalls>

- Working from this core file without loading the mode reference.
- Publishing from a content-plan or advisory task because a P1 grant was
  present — the goal decides, not the grant.
- Blocking without a `STATE:` checkpoint, or block reasons that don't
  survive 160-char truncation.
- Reusing a question number or re-asking an answered `Q<n>`.
- Inferring a Publish grant from chat-style comments — only the body
  `Publish:` line and `AUTHORITY+:` comments count.
- Long silent runs with no `PROGRESS:` trail.

</Pitfalls>

<Verification>

- Mode routed per <ModeRouting>; the matching reference was loaded before
  work started.
- Effective Publish grant computed (body + `AUTHORITY+:`); every published
  post maps to a verbatim approval or an in-cap P1 grant.
- Blocks were preceded by `STATE:`/`Q<n>:` comments; resumes matched every
  open `Q<n>` to its DECISION and never re-posted shipped posts.
- Report covers shipped/delivered items, ungated drafts, and risks — plus
  the per-mode Verification list in the loaded reference.

</Verification>
