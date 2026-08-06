# Campaign route (Mode: execute) - brief -> produce -> verify -> ship

Loaded when drafts go to approval or posts ship (announcements, threads,
campaigns). The kernel's MarketingBrief and PublishGrant apply throughout.
This file is the skeleton; the
engines carry the mechanics — load each at the step that needs it:

| Engine | Load at | Owns |
| --- | --- | --- |
| `references/delegate.md` | step 3 | input requests (prose/media/research) and their acceptance |
| `references/verify.md` | steps 4-6 | input acceptance, pre-publish gate, post-publish check |
| `references/publish.md` | step 6 | P0/P1 gate execution, xurl bridge, channels, immutability |

## Procedure

1. **Strategy.** From the brief: message angle per audience, post/thread
   structure, cadence, asset needs. Keep the plan in the resident session
   context and summarize any important decision in your reply.
2. **Ground.** Subject facts from the brief first; quick gaps you can
   close with your own tools, close them. Anything heavier
   (market/competitor/trend scans, multi-source fact hunts) → step 3 —
   do not burn your turns on breadth.
3. **Request production inputs** (delegate engine) in your reply: long copy →
   writer, media → creator, research → searcher/researcher. The assistant
   decides what to orchestrate, runs the producing specialists, and supplies
   their inputs in later messages. When inputs arrive, accept or reject each
   per the verify engine before using it.
4. **Assemble** — own the short-form text: post copy, thread breakdown,
   hooks, hashtags/mentions (only ones from the brief — never invented),
   link placement. Japanese post text follows `japanese-writing` notation
   norms (writer-produced copy arrives already compliant).
5. **Pre-publish verify** (verify engine V1-V5) on the exact candidate
   posts + attachments. Failures are fixed or withheld — never shipped.
6. **Ship** (publish engine): P0 → present exact final text
   per post; P1 → proceed within caps. xurl bridge, live re-fetch,
   report each live URL in your reply, and handle thread failures as defined
   by the engine.
7. **Report** per the kernel <Report>: shipped URLs, delivered drafts,
   what was drafted but not granted, inputs consumed, metrics to
   watch.

## Draft-only campaigns

No grant, or the goal explicitly says drafts only ("投稿は不要"): run
steps 1-5 and deliver the drafts (attach the set; final message = the
decision-ready summary, each post's text final and platform-ready). Say
explicitly that nothing shipped and what a ship task would still need.

## Pitfalls

- Assembling around an input you never verified (verify engine owns
  acceptance).
- Shipping outside the grant or skipping the pre-publish gate — the
  publish engine's gate is not optional under P1.
- Producing long prose or media yourself instead of requesting it.
- Losing the strategy while assembling a multi-post campaign — keep its
  decisions in the resident session and restate them in the reply when useful.

## Verification

- Every published post: V1-V5 passed, approval/grant mapped, URL live and
  recorded (engines' checks).
- Specialist inputs supplied in later assistant messages were consumed rather
  than re-produced locally, with accept/reject traces.
- Drafts not covered by the grant were delivered as drafts, clearly
  marked.
