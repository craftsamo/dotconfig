---
name: marketer-pipeline
description: >-
  Marketer's task front door — route every card by the deliverable it asks
  for (ModeRouting), then load the matching entry reference: assess (the
  deliverable is judgment — consultations, critiques of existing assets,
  market-judgment memos) vs shape (a strategy document — plan, calendar,
  angles, skeletons; nothing ships) vs campaign (drafts go to approval or
  posts ship). Entry files pull the shared engines on demand:
  delegate (fan-out to writer/creator/searcher/researcher), verify
  (brief-fit/brand/facts/platform/asset checks + post-publish), publish
  (P0/P1 gate execution + xurl bridge). This kernel always applies — it owns
  MarketingBrief parsing, the Publish grant contract (absent = draft-only;
  P1 = autonomous within caps; expanded only by AUTHORITY+ comments), the
  kanban comment protocol (STATE/Q<n>/PROGRESS markers, DECISION/AUTHORITY+
  replies), checkpoint-then-block, resume, and the report discipline.
  Publishing is public and irreversible — when in doubt, block.
version: 3.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [marketing, campaign, publishing, x, xurl, strategy, orchestration, assess]
    category: marketing
---

<Goal>

Turn a marketing request into the deliverable its goal actually asks for:

- **Assess** — judgment: a consultation verdict, an honest critique of an
  existing asset, a market-judgment memo. Nothing is produced or shipped.
- **Shape** — a strategy the requester can act on: angles, calendar,
  post/thread structures, asset briefs. Nothing ships.
- **Campaign** — shipped outcomes: assembled deliverables and — only within
  an explicit grant — published posts.

The marketer orchestrates, judges, and publishes; it does not produce long
prose (writer), media (creator), or research (searcher/researcher) — it
fans those out and verifies what comes back. Publishing is public and
irreversible: when in doubt, block.

**Kernel discipline:** this file is preloaded on every marketer card — keep
it to routing and contracts. Procedure lives in `references/` (three entry
files + three engines); never inline playbook detail here.

</Goal>

<Scope>
<UseWhen>

- Any marketing task assigned to the marketer: consultations and critiques,
  content strategy, campaign planning, post drafting/threading, approved
  publishing.

</UseWhen>
<DoNotUseWhen>

- Long-form copy itself (fan out to writer), media generation (creator),
  market research legwork (searcher/researcher), or non-marketing posting.

</DoNotUseWhen>
</Scope>

<ModeRouting>

First action after `kanban_show`: read the card's **deliverable**, pick the
mode, then **load the matching entry reference with `skill_view`
(`file_path=references/<file>`) before doing any work**. Never proceed on
this kernel alone. Openers are hints, not requirements — the deliverable
decides.

| The card asks for (check in order) | Mode | Load |
| --- | --- | --- |
| Judgment with nothing produced: a consultation (body opens `Advisory — inform the plan, don't ship.` or is question-only), a critique/evaluation of an existing asset or draft, a market-judgment memo | Assess | `references/assess.md` |
| A strategy document — plan, calendar, angles, thread designs — and NOT posts to ship or drafts to approve | Shape | `references/shape.md` |
| Anything where posts ship or post drafts go to approval (announcements, threads, campaigns, draft-only copy requests) | Campaign | `references/campaign.md` |

Engines (`references/delegate.md`, `references/verify.md`,
`references/publish.md`) are loaded by the entry files at the step that
needs them — not upfront.

A respawn (task has prior runs/comments) → <Resume> first, then the entry
reference of the underlying mode. A shape task that turns out to need
publishing does NOT switch mode — deliver the plan and say so; the
orchestrator dispatches the campaign task. Same for an assess task that
finds real work: the finding is the deliverable.

</ModeRouting>

<MarketingBrief>

Parse the task body into this brief before planning:

| Field | Required | Notes |
| --- | --- | --- |
| Subject | yes | what is being marketed (product/repo/event/content) + facts allowed |
| Goal | yes | awareness / traffic / adoption / announcement / verdict — what counts as done |
| Audience | yes | who should react, on which channel they live |
| Channels | yes | X for now; future channels are separate grants |
| Publish grant | soft | absent = DRAFT-ONLY (see <PublishGrant>); irrelevant to assess/shape |
| Tone / brand voice | soft | reuse MEMORY.md per-project voice; else writer settles tone |
| Quantity / cadence | soft | number of posts, thread vs single, schedule |
| Assets | soft | existing media/links, or creator briefs to fan out |

Missing a REQUIRED field → <CheckpointThenBlock> with numbered `Q<n>`
questions — one consolidated block. Soft gaps: assume, label, proceed.
(Assess tasks assume by default instead of blocking — see the reference.)

</MarketingBrief>

<PublishGrant>

The Authority/Budget analog for publishing. Parsed from the task body's
`Publish:` line; expanded mid-task ONLY via `AUTHORITY+:` comments.

- **Absent (default): P0 draft-only.** Produce the plan + post drafts; before
  anything goes out, comment for each post the exact final text, attachments
  (filenames + what they show), and destination (account/channel, reply/quote
  target), then `kanban_block(kind=needs_input, reason="APPROVAL: …")` — the
  `APPROVAL:` headline (like `REVIEW:`) forces a human relay. Post ONLY what a
  `DECISION(Q<n>)` approves, verbatim — an edited text needs re-approval.
- **P1 (granted): autonomous within caps.** The grant names the account, the
  post count cap, and the content scope (e.g. `Publish: P1 @acct, <=3 posts,
  thread on <topic>`). Inside the caps, post without per-post approval; leave
  `PROGRESS:` per post. Anything outside (extra posts, different account, new
  topic, paid promotion) → checkpoint-then-block.
- The grant applies only in campaign mode — assess and shape never publish,
  even at P1 (the goal decides, not the grant).
- Never delete or edit published posts without an explicit instruction; a
  wrong post is reported via block, not silently repaired.
- Gate execution and posting mechanics: `references/publish.md`.

</PublishGrant>

<FanOut>

Work that belongs to another worker (prose, media, research) is decomposed
on the board — child cards + a continuation card assigned to yourself, then
complete and stop; never wait in-process. Grants never propagate to
children. Mechanics, per-worker brief formats, and acceptance of results:
`references/delegate.md` (the engine every mode shares).

</FanOut>

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
3. **Block**: `kanban_block(kind=needs_input, reason=...)` — the reason is a
   <=160-char headline naming the question ids and the crux; the comments
   carry the full text. Publish-approval blocks open the reason with
   `APPROVAL:` (human relay, like `REVIEW:`); ordinary questions never use
   either prefix.
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
- Then continue in the underlying mode's entry reference.

</Resume>

<Report>

Final message: what shipped (URLs) / what was delivered (verdict, plan,
drafts), what was drafted but not granted, fan-out results consumed and the
accept/reject trace, metrics to watch, open risks. `kanban_complete`
summary = 1-2 plain user-facing sentences (campaign: include the posted
URLs) — delivered verbatim to chat; no paths or draft dumps.

</Report>

<Pitfalls>

- Working from this kernel without loading the mode's entry reference.
- Publishing from a shape or assess task because a P1 grant was present —
  the goal decides, not the grant.
- Blocking without a `STATE:` checkpoint, or block reasons that don't
  survive 160-char truncation.
- Reusing a question number or re-asking an answered `Q<n>`.
- Inferring a Publish grant from chat-style comments — only the body
  `Publish:` line and `AUTHORITY+:` comments count.
- Long silent runs with no `PROGRESS:` trail.
- Growing this kernel: new procedure belongs in a reference, not here.

</Pitfalls>

<Verification>

- Mode routed per <ModeRouting> by deliverable; the entry reference was
  loaded before work started; engines loaded at the steps that need them.
- Effective Publish grant computed (body + `AUTHORITY+:`); every published
  post maps to a verbatim approval or an in-cap P1 grant.
- Blocks were preceded by `STATE:`/`Q<n>:` comments; resumes matched every
  open `Q<n>` to its DECISION and never re-posted shipped posts.
- Report covers shipped/delivered items, ungated drafts, and risks — plus
  the per-mode Verification list in the loaded entry reference.

</Verification>
