# Campaign route (Mode: execute) - brief -> produce -> verify -> ship

Loaded when drafts go to approval or posts ship (announcements, threads,
campaigns). The kernel's MarketingBrief, PublishGrant, comment protocol and
checkpoint-then-block apply throughout. This file is the skeleton; the
engines carry the mechanics — load each at the step that needs it:

| Engine | Load at | Owns |
| --- | --- | --- |
| `references/delegate.md` | step 3 | fan-out briefs, continuation cards, grant non-propagation |
| `references/verify.md` | steps 4-6 | fan-in acceptance, pre-publish gate, post-publish check |
| `references/publish.md` | step 6 | P0/P1 gate execution, xurl bridge, channels, immutability |

## Procedure

1. **Strategy.** From the brief: message angle per audience, post/thread
   structure, cadence, asset needs. For multi-deliverable campaigns leave
   the plan as a `STATE:` comment (it survives respawns).
2. **Ground.** Subject facts from the brief first; quick gaps you can
   close with your own tools, close them. Anything heavier
   (market/competitor/trend scans, multi-source fact hunts) → step 3 —
   do not burn your turns on breadth.
3. **Fan out production** (delegate engine): long copy → writer, media →
   creator, research → searcher/researcher. Final Writer/Creator outputs use
   Assistant-registered subscribed production and evidence cards; QA is late-bound
   after CompletionAdmission. The marketer continuation is registered only after
   the Assistant records a digest-checked `QA_PASS_SET`. On fan-in, accept or reject
   each deliverable per the verify engine before using it.
4. **Assemble** — own the short-form text: post copy, thread breakdown,
   hooks, hashtags/mentions (only ones from the brief — never invented),
   link placement. Japanese post text follows `japanese-writing` notation
   norms (writer-produced copy arrives already compliant).
5. **Pre-publish verify** (verify engine V1-V5) on the exact candidate
   posts + attachments. Failures are fixed or blocked — never shipped.
6. **Ship** (publish engine): P0 → approval block with exact final text
   per post; P1 → proceed within caps. xurl bridge, live re-fetch,
   `PROGRESS:` per URL, thread failure handling — all per the engine.
7. **Report** per the kernel <Report>: shipped URLs, delivered drafts,
   what was drafted but not granted, fan-out results consumed, metrics to
   watch.

## Draft-only campaigns

No grant, or the goal explicitly says drafts only ("投稿は不要"): run
steps 1-5 and deliver the drafts (attach the set; final message = the
decision-ready summary, each post's text final and platform-ready). Say
explicitly that nothing shipped and what a ship task would still need.

## Pitfalls

- Assembling around a fan-out deliverable you never verified (verify
  engine owns acceptance).
- Shipping outside the grant or skipping the pre-publish gate — the
  publish engine's gate is not optional under P1.
- Producing long prose or media yourself instead of fanning out.
- A multi-post campaign with no `STATE:` strategy comment — the next
  respawn re-derives strategy from nothing.

## Verification

- Every published post: V1-V5 passed, approval/grant mapped, URL live and
  recorded (engines' checks).
- Fan-out deliverables consumed from child tasks (not re-produced locally)
  with accept/reject traces.
- Drafts not covered by the grant were delivered as drafts, clearly
  marked.
