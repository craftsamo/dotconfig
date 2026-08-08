# Publish engine — the only irreversible act

Loaded when a unit actually ships. The kernel's <PublishGrant>
decides WHETHER; this file owns HOW. The four-stage inspection
(`verify.md`) has already passed on the exact candidate — shipping
un-inspected content is a red-floor violation, not a shortcut.

## Gate execution

- **P0**: the reply presented exact text + attachments +
  destination; the approval message arrived; ship precisely that.
  Any difference — wording, attachment set, reply target — means
  re-present, not ship.
- **P1**: consume **approved inventory** within the named caps
  (account, count, scope). New claims or appeals never become
  green by cap arithmetic. Outside any cap: ask and wait.
- Reconcile one-to-one: each shipped post maps to its approval or
  its approved-queue entry; dispatch is idempotent — a retried
  turn must not double-post.

## xurl bridge (X, live)

Load the external `xurl` skill for mechanics before the first call.
Per post:

1. Media first: upload attachments, collect media ids.
2. Create the post (text + media ids).
3. **Re-fetch the returned id once** — a returned id is not proof
   the post is live.
4. Report the live URL in your reply, one per shipped post.

Threads are an ordered reply chain. Mid-thread failure: report what
shipped (URLs) and what remains, then wait — never re-post shipped
items; resumption covers only the unshipped tail. Auth failures
(`xurl auth status`, token errors): ask in your reply; never retry
in a loop.

## Channels

- **X (live)** — via `xurl` (OAuth pre-configured).
- **Everything else** — no live integration: deliver
  destination-formatted drafts and say so. A future channel arrives
  as its own integration + per-channel grant line; never improvise
  posting through other tools.

## After shipping

- Shipped posts are immutable facts: no edits, no deletions, no
  re-posts without an explicit instruction. A wrong post is
  reported — what shipped, what is wrong, options — never silently
  repaired. Deletion, when instructed, is itself an approval-gated
  action.
- Collect the unit's measurements (impressions, clicks,
  destination attribution) into the campaign's records; the weekly
  improvement turn interprets them.
- The final report carries every live URL, the reconciliation
  against approvals/queue, and spend against caps.

## Pitfalls

- Shipping approved text you then "improved" — verbatim means
  verbatim.
- Skipping the live re-fetch, or reporting ids instead of URLs.
- Treating a P1 cap as covering a new appeal because the count
  allows it.
- Retrying a failed thread from the top, duplicating shipped
  posts.
- Posting from a grounding turn because a grant exists — grounding
  never publishes.
