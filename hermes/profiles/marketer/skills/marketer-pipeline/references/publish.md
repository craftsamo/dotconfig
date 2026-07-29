# Publish engine — the only irreversible act

Shared engine for shipping posts. Loaded only when a campaign task reaches
its publish stage. The kernel's <PublishGrant> decides WHETHER anything may
ship; this file owns HOW. Publishing is public and irreversible — when in
doubt, block.

## Gate (recap, kernel owns the contract)

- **P0 (no `Publish:` line): approval block.** Before anything goes out,
  `kanban_block(kind=needs_approval)` showing per post: exact final text,
  attachments (filenames + what they show), destination (account/channel,
  reply/quote target). Post ONLY what a `DECISION(Q<n>)` approves,
  verbatim — edited wording, however improved, needs re-approval.
- **P1: autonomous within caps.** The grant names account, post-count cap,
  and content scope. Inside all caps, post without per-post approval.
  Anything outside — extra posts, another account, a new topic, paid
  promotion — is a checkpoint-then-block, not an interpretation.
- Run the verify engine's pre-publish gate (V1-V5) before either path.

## xurl bridge (X, live)

Load the external `xurl` skill for mechanics before the first call. Per
post:

1. Media first: upload attachments, collect media ids.
2. `xurl` create the post (text + media ids).
3. Take the returned post id/URL and **re-fetch it once** to confirm it is
   live (verify engine V6).
4. `PROGRESS:` comment with the URL — one per shipped post.

Threads are an ordered reply chain: post 1, reply to it with post 2, and so
on. On a mid-thread failure: checkpoint-then-block with what shipped (URLs)
and what remains — **never re-post already-shipped items**; resume continues
the chain from the recorded URLs.

Auth problems (`xurl auth status` fails, token errors) are a block, not a
retry loop.

## Channels

- **X (live)** — via `xurl` (OAuth pre-configured on this machine).
- **Future (not granted by default)** — Discord / Instagram / TikTok etc.
  arrive as per-channel accounts + per-channel grant lines. A brief naming
  a channel with no live integration → deliver drafts formatted for that
  channel and say so; never improvise posting through other tools.

## After shipping

- Shipped posts are immutable facts: never delete or edit a published post
  without an explicit instruction. A wrong post is surfaced via a block
  (what shipped, what is wrong, options), not silently repaired.
- Every shipped URL lives in a `PROGRESS:` comment — that trail is what a
  respawn uses to avoid double-posting, and what the report cites.

## Pitfalls

- Shipping anything not covered by a verbatim approval or an in-cap P1
  grant — including approved text you then "improved".
- Skipping the live re-fetch — a returned id is not proof the post is up.
- Retrying auth failures instead of blocking.
- Re-posting shipped items after a partial failure.
- Posting from a shape or assess task because a P1 grant exists —
  the goal decides, not the grant (kernel rule).

## Verification

- Every shipped post maps to its approval or in-cap grant, passed V1-V5
  before shipping, and has a live-verified URL in a `PROGRESS:` comment.
- No published post was edited, deleted, or re-posted; failures were
  blocked with the shipped/remaining split stated.
