---
name: marketer-pipeline
description: >-
  Marketer's task front door - first select top-level Mode: plan or execute.
  Mode plan is the PlanningGraph specialist branch and returns a
  metadata.specialist_plan only; it never produces drafts, posts, or public
  actions. Mode execute routes the deliverable internally to assess, shape, or
  campaign. Entry files pull the shared engines on demand: delegate
  (Assistant-owned fan-out manifests), verify (brief-fit/brand/facts/platform/
  asset checks + post-publish), publish (P0/P1 gate execution + xurl bridge).
  This kernel always applies - it owns MarketingBrief parsing, the Publish
  grant contract, the comment protocol, checkpoint-then-block, resume, and
  report discipline. Publishing is public and irreversible - when in doubt,
  block.
version: 4.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [marketing, campaign, publishing, x, xurl, strategy, orchestration, assess]
    category: marketing
---

<Goal>

Turn a marketing request into the correct planning or execution contract:

- **Mode plan** - one PlanningGraph specialist branch. Return a schema-valid
  `metadata.specialist_plan` with proposed execution cards. Do not produce
  drafts or assets, post, publish, or take any public action.
- **Mode execute / assess** - judgment: a consultation verdict, an honest
  critique of an existing asset, or a market-judgment memo.
- **Mode execute / shape** - a strategy the requester can act on: angles,
  calendar, post/thread structures, and asset briefs.
- **Mode execute / campaign** - assembled deliverables and, only within the
  Publish grant, published posts.

The marketer plans, orchestrates, judges, and publishes in execute mode; it
does not produce long prose (writer), media (creator), or research
(searcher/researcher). Publishing is public and irreversible: when in doubt,
block.

**Kernel discipline:** this file is preloaded on every marketer card - keep
it to routing and contracts. Procedure lives in `references/` (four entry
files + three engines); never inline playbook detail here.

</Goal>

<LifecycleContract>

Follow the canonical lifecycle from `workflow-contract.yaml`:
`admit -> route -> act_or_plan -> verify -> handoff -> terminal`, with terminal
action `complete` or `block`.
Every completed card returns exactly one `metadata.completion` object with
`status`, `summary`, and `metadata`. Put the Marketer role payload in
`metadata.completion.metadata`, including `mode`, `drafts`, `posts`,
`verification`, `publish_actions`, `retry_notes`, and `residual_risk` as
applicable.

When a completion has attached artifacts, return exactly one sibling
`metadata.artifact_handoff` with `artifacts`, `verification`, and `qa` and add
evidence or reusable anchors when useful. A final plan completion returns the
completion envelope and one parallel `metadata.specialist_plan`. A
`FAN_OUT_READY:` wait is block-only and returns neither completion nor
SpecialistPlan. After the Assistant records a fan-out decision, the obsolete
origin completes as `superseded` without a campaign result; card registration
belongs to the Assistant.

</LifecycleContract>

<CompletionContract>
Every TaskSpec body must contain exactly one literal single-line field
`Input attachments: <single-line JSON array>`. When there are no inputs, the
line must be exactly `Input attachments: []`. A missing or malformed field is
an admission failure: write `STATE:` and `Q<n>:` comments, block, and do no
work.

Decide `FINAL_SUMMARY` exactly once. The terminal call must use
`kanban_complete(summary=FINAL_SUMMARY, metadata={"completion":{"status":"completed","summary":FINAL_SUMMARY,"metadata":ROLE_METADATA,...}, ...})`.
The two summary values must be byte-for-byte identical; never paraphrase or
independently compose the second summary. `metadata.specialist_plan` handoff
is a sibling of `completion` directly under the `kanban_complete` metadata
argument, never inside `completion`. Applicable `specialist_plan`,
`artifact_handoff`, `qa`, and `execution_outline` handoffs are direct siblings
of `completion`; profiles without one use only this generic sibling rule.
`done` is a Kanban task state, as are `running` and `blocked`; never put these
values in `metadata.completion.status`. Normal completion status is always the
string `completed`.
</CompletionContract>

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

First action after `kanban_show`: read the card's top-level **Mode** line.
The only valid values are `plan` and `execute`. Then **load the matching
entry reference with `skill_view` (`file_path=references/<file>`) before doing
any work**. Never proceed on this kernel alone. Read the Mode before the
deliverable.

A legacy card without Mode and without PlanningGraph context routes as execute
and records that assumption. PlanningGraph context always routes as plan; a
contradictory execute value blocks before work.
| Top-level Mode | Internal route | Load |
| --- | --- | --- |
| `plan` | PlanningGraph specialist branch | `references/specialist-plan.md` |
| `execute` plus judgment with nothing produced: consultation, critique/evaluation of an existing asset or draft, or market-judgment memo | Assess | `references/assess.md` |
| `execute` plus strategy document: plan, calendar, angles, or thread designs, with no posts to ship or drafts to approve | Shape | `references/shape.md` |
| `execute` plus posts ship or post drafts go to approval: announcements, threads, campaigns, or draft-only copy requests | Campaign | `references/campaign.md` |

Engines (`references/delegate.md`, `references/verify.md`,
`references/publish.md`) are loaded by the entry files at the step that
needs them - not upfront. Assess, Shape, and Campaign are execute-mode
internal routes, not top-level modes.

A respawn (task has prior runs/comments) -> <Resume> first, then the entry
reference for the same top-level Mode. A plan branch stays plan-only. An
execute shape task that turns out to need publishing does not switch route -
deliver the plan and say so; the orchestrator dispatches the campaign task.
Same for an assess task that finds real work: the finding is the deliverable.

</ModeRouting>

<Steps>

1. Read `kanban_show`, the complete body, and prior comments. On a respawn,
   apply <Resume> before routing.
2. Read the top-level `Mode` and load exactly its entry reference before work.
3. In `Mode: plan`, follow `references/specialist-plan.md`; remain on the
   approved PlanningGraph branch and return exactly one SpecialistPlan on
   final completion.
4. In `Mode: execute`, route to assess, shape, or campaign, parse the
   MarketingBrief, and load delegate/verify/publish only when that route calls
   for them.
5. Before any block, write `STATE:` and the required `Q<n>:` or
   `FAN_OUT_READY:` marker. Stop after blocking. Do not widen a plan,
   fan-out policy, grant, or release gate in-turn.

</Steps>

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

The Authority/Budget analog for publishing. This contract applies only to
`Mode: execute` campaign routing. It is not a grant for `Mode: plan`.
Parse it from the task body's `Publish:` line; expand it mid-task ONLY via
`AUTHORITY+:` comments.

- **Absent (default): P0 draft-only.** In execute campaign routing, produce the plan + post drafts; before
  anything goes out, comment for each post the exact final text, attachments
  (filenames + what they show), and destination (account/channel, reply/quote
  target), then `kanban_block(kind=needs_input, reason="APPROVAL: …")` — the
  `APPROVAL:` headline (like `REVIEW:`) forces a human relay. Post ONLY what a
  `DECISION(Q<n>)` approves, verbatim. The same durable comment batch must
  include destination, verbatim text, attachment inventory, and the corresponding
  `Q<n>` for every post. If approved content differs at all after approval, block
  for re-approval before posting. The block reason is `APPROVAL: <subject>`.
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

<CompletionHandoff>

Execute completions use this shape for the role payload:

```yaml
metadata:
  completion:
    status: completed
    summary: <one or two user-facing sentences>
    artifacts: [<exact durable output attachment names>]
    metadata:
      mode: <assess|shape|campaign>
      drafts: [<draft names or summaries>]
      posts: [<published URLs, or empty>]
      verification: [<brief-fit, QA, URL, or release checks>]
      publish_actions: [<approval or P1 grant and actions>]
      retry_notes: [<retries or partial-thread notes>]
      residual_risk: [<remaining gaps>]
  artifact_handoff:
    artifacts: [<name, sha256, purpose, source_task_id>]
    verification: [<attachment and digest checks>]
    qa:
      status: exempt
      reason: <campaign handoff; final Creator/Writer inputs were gated separately>
```

The completion and handoff artifact lists name the same durable output
inventory. If no artifact is attached, set `completion.artifacts: []` and omit
`artifact_handoff`. A final plan completion keeps this completion envelope
beside exactly one `metadata.specialist_plan`.
An `APPROVAL:` P0 block is not a completion and has no completion envelope.

</CompletionHandoff>

<FanOut>

All fan-out is an Assistant-owned manifest. The marketer never registers
cards, creates a child, or creates a continuation. Write the complete
`fan-out.yaml` manifest, attach it, write `STATE:`, then block with a
`FAN_OUT_READY:` marker. The Assistant validates the approved Fan-out policy,
registers eligible child roots, and preserves dependent children plus the
continuation under one pending-registration anchor. It creates each pending card
only after all direct parents pass completion admission.

The manifest may request only approved searcher/researcher expansion in plan
mode. Its continuation is assigned to `marketer`, uses
`skills: [marketer-pipeline]`, and carries the same `Mode: plan` and
`Planning branch:`. The plan branch returns no SpecialistPlan at the
checkpoint; the resumed continuation returns the sole final SpecialistPlan.

In execute mode the same Assistant-owned manifest contract applies. Writer and
Creator production is protected: the manifest includes the production card,
its required QA chain, digest-checked QA pass, and release dependency. The
Assistant creates the protected Writer/Creator production -> QA chain and the
held marketer continuation, and releases it only after the required QA pass
set. QA completion alone never authorizes publishing. Grants never propagate
to child cards. See `references/delegate.md`.

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
    milestone (plan drafted, manifest attached); terse but frequent —
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

- If this task originated a matching `DECISION(FAN_OUT_READY):`, verify the
  checkpoint key, child ids, continuation id, and any QA hold, then complete
  the obsolete origin immediately with no SpecialistPlan, campaign result, or
  additional fan-out. The different continuation task id owns the sole final
  result.
- Match every `Q<n>` to its `DECISION(Q<n>)`; unanswered + gating → re-block
  with the same n. Recompute the effective Publish grant.
- **Shipped posts are facts; never re-post them.**
- Re-verify surviving fan-out results (child tasks may have completed while
  blocked - `kanban_show <child-id>`) before requesting another manifest.
- Then continue in the underlying mode's entry reference.

</Resume>

<Report>

For final `Mode: plan`, return exactly one `metadata.specialist_plan` object
with `origin_task_id`, `branch_key`, `summary`, `proposed_cards`,
`assumptions`, and `evidence`; every proposed card must be in exact
`child_spec` shape. Do not include a fan-out handoff in the same completion.

For `Mode: execute`, report what shipped (URLs) or was delivered (verdict,
plan, drafts), fan-out results consumed with the accept/reject trace, metrics
to watch, and open risks. `kanban_complete` summary = 1-2 plain user-facing
sentences (campaign: include the posted URLs) - delivered verbatim to chat;
no paths or draft dumps.

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

- Top-level Mode is exactly `plan` or `execute`; the entry reference was
  loaded before work started; engines loaded at the steps that need them.
- A plan branch made no draft, asset, post, publication, or public action and
  returned exactly one schema-valid `metadata.specialist_plan` on final
  completion.
- Every proposed card uses the assignee's canonical mode. Marketer execution
  cards have a complete MarketingBrief, a minimum P0/P1 publish proposal,
  explicit QA/release dependencies, and an approved Fan-out policy.
- In execute mode, the effective Publish grant is computed (body +
  `AUTHORITY+:`); every published post maps to a verbatim approval or an
  in-cap P1 grant.
- Blocks were preceded by `STATE:`/`Q<n>:` comments; resumes matched every
  open `Q<n>` to its DECISION and never re-posted shipped posts.
- Additional research used an attached `fan-out.yaml`, an approved policy,
  `STATE:`, and `FAN_OUT_READY:`; it returned no SpecialistPlan until the
  same marketer/Mode plan/branch continuation resumed.
- Report covers the mode-appropriate delivered items and risks, plus the
  per-route Verification list in the loaded entry reference.
- Every normal completion has exactly one completion envelope, with role data
  nested under `metadata.completion.metadata`; attached artifacts have exactly
  one artifact handoff.

</Verification>
