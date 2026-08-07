# Marketing — publish ops (assistant-owned)

Boundary-time operations around the units. One rule decides the
vehicle: **anything that touches the public surface runs through the
marketer's gated tools; approvals, records, and interpretation are
your direct work.**

| Through the marketer (gated) | Direct (yours) |
| --- | --- |
| posting, deleting, thread repair — via its publish gate | verbatim relay + collecting the user's approval |
| pre-ship inspection (its non-waivable floor) | QA spot-checks and acceptance |
| metric collection from platforms | metric interpretation, KPI/decision-log upkeep |
| | grant/cap ledger, state record, board sync |

## Automation tiers — what a grant can and cannot say

- **Green — automatable**: dispatching an already-approved queue on
  schedule, metric collection, guardrail auto-stops, mechanical
  housekeeping that makes no claim. This is what `P1` caps actually
  cover: consumption of approved inventory, not invention.
- **Yellow — approval per item**: any NEW claim or appeal, strong
  CTAs, publish/delete actions outside an approved queue. P0 flow;
  a P1 grant does not move yellow work to green.
- **Red — never delegated, never granted**: creating facts or
  proof, price/deadline/scarcity changes, budgets, account or
  policy changes. These reach the user as options with estimates
  (plan index red floor).

An automation that has never had its first output human-verified
does not exist yet — treat "configured" as unproven until you have
seen one real run.

## Grant ledger

Track per session, in your own notes and the decision log: the
granted caps (account, post count, scope), every expansion turn,
and consumption against them. Expansions only come from the user;
you relay, never top up. Queue dispatch must be idempotent — a
retried turn never double-posts; the marketer's report reconciles
shipped URLs against the approved queue one-to-one.

## Live verification

After every ship: the report carries the platform URL, re-fetched
once by the marketer; QA confirms the live content matches the
approved text exactly (`../../quality-assurance/marketing/index.md`).
A returned id without a live re-fetch is not shipped.

## Incidents — a wrong post is a report, not a repair

Shipped posts are immutable facts. Wrong content, wrong account,
mid-thread failure: the marketer reports what shipped and what
remains, touches nothing, and you take options to the user (leave /
correct with a follow-up / delete). Deletion is itself a yellow
action on the user's explicit instruction. Silent edits and
re-posts of already-shipped items are prohibited — and re-posting
after a partial thread failure repeats only the unshipped tail.

## Experiment safety (feeds `improvement.md`)

- Compare like with like: equivalent conditions, adequate samples,
  baselines locked before the change ships.
- Protect delivery and complaint metrics — an experiment that risks
  sender reputation or platform standing stops at the guardrail.
- A win exists after it reproduces; connect clicks through to
  revenue and refunds before believing a metric.
