# Marketing state — the standing record

Marketing decisions outlive sessions. Each marketed project keeps a
**state record** — plain markdown files you maintain in the
project's private data area (under the project's `~/Workspaces`
tree, never in this public config repo, never in chat memory alone).
The record is the durable layer campaigns ground in; SessionBriefs
reference it by path.

## Files and their schemas

| File | Holds |
| --- | --- |
| `positioning.md` | the approved positioning (`positioning.md` leaf decisions) + validation evidence + revisit triggers |
| `offers.md` | the offer ladder, per-rung status, pricing bases presented, and the user's price decisions (dated) |
| `channels.md` | per channel: role, arbitration scores, dated policy-risk notes, automation involvement; a channel with no role is an exit candidate |
| `facts.md` | **the fact ledger** — every approved product/proof fact, each with source and registration date. Shipped copy may claim ONLY what resolves here; unknowns are marked unresearched and queued, never inferred |
| `non-goals.md` | rejected initiatives: what, the concrete reason, the governing policy or precedent, the alternative chosen. Every new plan checks against it |
| `decisions.md` | append-only decision log: date, decider (user/you), the declaration, evidence quality, status, unresolved items. Never edited, only appended |
| `kpi.md` | the KPI tree: north-star metric for the current and next maturity stage; acquisition/conversion/retention/referral/revenue metrics, each labeled implemented or unmeasured (unmeasured = instrumentation backlog) |
| `experiments.md` | proposal ledger + running experiments: hypothesis, target metric, confidence, observation window, tolerance limit, baseline, outcome |

Ship-time operational ledgers (queue, connections, journey mapping)
live with execution — `../../execute/marketing/publish-ops.md`.

## Rules

- **Facts before copy**: a claim the ledger lacks is either
  registered (with source) before use or removed from the draft —
  the marketer's factual inspection enforces this; you own the
  ledger's integrity.
- **Unknown ≠ plausible**: fields you have not researched say so
  explicitly; filling gaps by inference corrupts every downstream
  campaign.
- **Non-goals are binding**: a plan conflicting with an entry either
  changes the entry (user decision, logged) or changes the plan.
- **The log is the memory**: strategy declarations, price decisions,
  channel entries/exits, red-team issue maps, improvement-loop
  adjudications — all land in `decisions.md` the day they happen.
- Refresh cadence: the record is reviewed at each improvement loop
  (`../../execute/marketing/improvement.md`) and inventoried
  quarterly; stale evidence is relabeled, not silently trusted.

## Bootstrap

First marketing work on a project creates the record: seed
`positioning.md` (or mark it unvalidated), an empty-but-present fact
ledger, and the KPI file with the current stage's north star. A
campaign planned without a state record is a red-flag plan — the
record is cheap; re-deriving strategy every session is not.
