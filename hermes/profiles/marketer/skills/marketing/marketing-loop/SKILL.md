---
name: marketing-loop
description: Marketer's campaign pipeline — MarketingBrief and Publish-grant parsing, strategy and content planning, fan-out to writer/creator/searcher/researcher, approval-gated publishing through the xurl bridge with per-post PROGRESS and URL verification, and kanban-thread resume. Publishing is irreversible; the default is always draft + approval block.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [marketing, campaign, publishing, x, xurl, strategy, orchestration]
    category: marketing
---

<Goal>

Turn a marketing request into shipped outcomes: a content plan, assembled
deliverables, and — only within an explicit grant — published posts. The
marketer orchestrates and publishes; it does not produce long prose (writer),
media (creator), or research (searcher/researcher). Publishing is public and
irreversible: when in doubt, block.

</Goal>

<Scope>
<UseWhen>

- Any marketing task assigned to the marketer: content strategy, campaign
  planning, post drafting/threading, approved publishing.
- NOT for: long-form copy itself (fan out to writer), media generation
  (creator), market research (searcher/researcher), or non-marketing posting.

</UseWhen>
</Scope>

<MarketingBrief>

Parse the task body into this brief before planning:

| Field | Required | Notes |
| --- | --- | --- |
| Subject | yes | what is being marketed (product/repo/event/content) + facts allowed |
| Goal | yes | awareness / traffic / adoption / announcement — what counts as done |
| Audience | yes | who should react, on which channel they live |
| Channels | yes | X for now; future channels are separate grants |
| Publish grant | soft | absent = DRAFT-ONLY (see PublishGrant) |
| Tone / brand voice | soft | reuse MEMORY.md per-project voice; else writer settles tone |
| Quantity / cadence | soft | number of posts, thread vs single, schedule |
| Assets | soft | existing media/links, or creator briefs to fan out |

Missing a REQUIRED field -> checkpoint (`STATE:` comment), then
`kanban_block(kind=needs_input)` with numbered `Q<n>` questions (2-4 options +
recommendation) — one consolidated block. Soft gaps: assume, label, proceed.

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
  topic, paid promotion) -> checkpoint-then-block.
- Never delete or edit published posts without an explicit instruction; a
  wrong post is reported via block, not silently repaired.

</PublishGrant>

<Procedure>

1. **Brief** — `kanban_show`, parse MarketingBrief + PublishGrant; block on
   required gaps.
2. **Strategy** — content plan: message angle per audience, post/thread
   structure, cadence, asset needs. For multi-deliverable campaigns leave the
   plan as a `STATE:` comment (it survives respawns).
3. **Fan-out** — via `kanban_create` (+ `parents` fan-in, assignee set):
   - writer: long copy, article-length text, tone-sensitive wording — pass
     the WritingBrief fields (audience, purpose, medium, tone, length, facts).
   - creator: images/video/GIF — pass a full MediaBrief + destination specs
     (X: 16:9 or 1:1, alt text).
   - searcher/researcher: market/competitor/trend input you lack.
   Consume their final messages; verify attachments exist before referencing.
4. **Assemble** — own the short-form text: post copy, thread breakdown,
   hooks, hashtags/mentions (only ones from the brief — never invented),
   link placement. Japanese post text follows `japanese-writing` notation
   norms (writer-produced copy arrives already compliant).
5. **Publish gate** — per PublishGrant: P0 -> approval block; P1 -> proceed
   within caps.
6. **Publish (xurl bridge)** — load the external `xurl` skill for mechanics.
   Per post: `xurl` create (text, media upload first when attaching) -> take
   the returned post id/URL -> re-fetch it once to verify it is live ->
   `PROGRESS:` comment with the URL. Thread = reply chain in order; on a
   mid-thread failure, checkpoint-then-block with what shipped and what
   remains (never re-post already-shipped items).
7. **Report** — final message: what shipped (URLs), what was drafted but not
   granted, metrics to watch. `kanban_complete` = 1-2 sentences with the
   posted URLs (delivered verbatim to chat).

</Procedure>

<Channels>

- **X (live)**: via the `xurl` CLI (OAuth pre-configured on this machine;
  `xurl auth status` to check — auth problems are a block, not a retry loop).
- **Future (not granted by default)**: Discord / Instagram / TikTok etc. will
  arrive as per-channel accounts + per-channel grant lines. A brief naming a
  channel with no live integration -> deliver drafts formatted for that
  channel and say so; never improvise posting through other tools.

</Channels>

<Resume>

A respawn after block/crash: reread the kanban thread first — `STATE:` plan,
`Q<n>`/`DECISION` pairs, `PROGRESS:` lines with shipped URLs, `AUTHORITY+:`
expansions. Shipped posts are facts; never re-post them. Re-verify surviving
fan-out results (child tasks may have completed while blocked) before
re-dispatching anything.

</Resume>
