# Campaign mode — research → fan-out → assemble → publish

Loaded when posts ship (or drafts go to approval). The core file's
MarketingBrief, PublishGrant, comment protocol, and checkpoint-then-block
apply throughout.

## Procedure

1. **Strategy.** From the brief: message angle per audience, post/thread
   structure, cadence, asset needs. For multi-deliverable campaigns leave
   the plan as a `STATE:` comment (it survives respawns).
2. **Research.** Ground the angle in facts: subject facts from the brief
   first; quick gaps you can close with your own tools, close them. Anything
   heavier (market/competitor/trend scans, multi-source fact hunts) →
   fan out per step 3 — do not burn your turns on breadth.
3. **Fan-out** — via `kanban_create` (+ `parents` fan-in, assignee set);
   dispatch in parallel where inputs allow:
   - **writer**: long copy, article-length text, tone-sensitive wording —
     pass the WritingBrief fields (audience, purpose, medium, tone, length,
     facts).
   - **creator**: images/video/GIF — pass a full MediaBrief + destination
     specs (X: 16:9 or 1:1, alt text).
   - **searcher/researcher**: market/competitor/trend input you lack.
   Sub-task bodies must be self-contained (workers never see your task).
   Consume their final messages; verify attachments exist before
   referencing. Record dispatched child ids in a `PROGRESS:` comment.
4. **Assemble** — own the short-form text: post copy, thread breakdown,
   hooks, hashtags/mentions (only ones from the brief — never invented),
   link placement. Japanese post text follows `japanese-writing` notation
   norms (writer-produced copy arrives already compliant).
5. **Publish gate** — per the core <PublishGrant>: P0 → approval block
   (exact final text + attachments + destination per post); P1 → proceed
   within caps.
6. **Publish (xurl bridge)** — load the external `xurl` skill for
   mechanics. Per post: `xurl` create (text, media upload first when
   attaching) → take the returned post id/URL → re-fetch it once to verify
   it is live → `PROGRESS:` comment with the URL. Thread = reply chain in
   order; on a mid-thread failure, checkpoint-then-block with what shipped
   and what remains (never re-post already-shipped items).
7. **Report** per the core <Report>.

## Channels

- **X (live)**: via the `xurl` CLI (OAuth pre-configured on this machine;
  `xurl auth status` to check — auth problems are a block, not a retry
  loop).
- **Future (not granted by default)**: Discord / Instagram / TikTok etc.
  will arrive as per-channel accounts + per-channel grant lines. A brief
  naming a channel with no live integration → deliver drafts formatted for
  that channel and say so; never improvise posting through other tools.

## Pitfalls

- Publishing anything not covered by a verbatim approval or an in-cap P1
  grant — including "improved" wording after approval (re-approve it).
- Inventing hashtags, mentions, or claims not grounded in the brief or
  retrieved facts.
- Referencing a creator/writer attachment you never verified exists.
- Re-posting shipped items after a mid-thread failure — resume from the
  recorded URLs.
- Skipping the live re-fetch after posting — a returned id is not proof
  the post is up.

## Verification

- Every published post maps to its approval/grant; URLs verified live and
  recorded in `PROGRESS:` comments.
- Fan-out deliverables were consumed from child tasks (not re-produced
  locally) and attachments existed.
- Drafts not covered by the grant were delivered as drafts, clearly marked.
