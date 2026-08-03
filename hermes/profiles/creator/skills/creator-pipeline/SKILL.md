---
name: creator-pipeline
description: >-
  Creator's task front door for workflow-contract.yaml v1. The required
  top-level Mode is plan or execute. Mode plan is a read-only PlanningGraph
  specialist branch with zero generation spend and no card registration.
  Mode execute keeps Advisory, Direction (the style-anchor gate), Produce,
  and Resume as internal routing. This kernel owns the Budget grant contract,
  the kanban comment protocol, checkpoint-then-block, Assistant-owned
  fan-out, capability routing, verification, and delivery.
version: 5.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [media, image, video, gif, tts, production, kanban, planning, delivery, verification, triage, intent]
    category: creative
    related_skills: [creator-generated-image, creator-article-illustration, creator-infographic, creator-svg-diagram, creator-excalidraw-diagram, creator-logo-icons, creator-text-card, creator-meme, creator-ascii-art, creator-audio-visualization, creator-audio-generation, creator-song-generation, creator-gif-sourcing, creator-generated-video, creator-html-motion, creator-p5js-experience, creator-ascii-video, creator-manim-explainer, creator-pixel-art, creator-pixel-video, creator-knowledge-comic, creator-brand-asset-sourcing]
---

<Goal>

Route a creator card under workflow-contract.yaml v1. Top-level `Mode: plan`
returns a read-only `metadata.specialist_plan` for an approved PlanningGraph
branch with zero generation spend, zero asset production, and no live cards.
Top-level `Mode: execute` selects an internal route: Advisory, Direction (the
existing style-anchor gate), or Produce. Execute uses the right generation
chain per asset type, spends only an approved Budget, verifies outputs, and
delivers attached artifacts. Every Produce card has one Intent
(<IntentTriage>) - new, revise, or salvage - which controls its first move and
verification floor.

The worker process is disposable (block ends the run; unblock respawns a
fresh one), so continuity lives in durable layers only: the kanban comment
thread (decisions, locked anchors, the spend tally), attachments, and the
surviving task workspace. Never rely on a long-running session's memory -
and never treat already-paid-for work as waste (`references/resume.md`).

This kernel is mechanically preloaded on every card - keep it lean:
routing, triage, and contracts live here; playbook detail lives in
`references/` (loaded on demand) and must never migrate back in.

</Goal>

<LifecycleContract>

Follow the canonical lifecycle from `workflow-contract.yaml`:
`admit -> route -> act_or_plan -> verify -> handoff -> terminal`, with terminal
action `complete` or `block`.
Every completed card returns exactly one `metadata.completion` object with
`status`, `summary`, and `metadata`. Put the Creator role payload in
`metadata.completion.metadata`: `assets`, `verification`, `spend`, `anchor`,
`retry_notes`, and `residual_risk`.

When a completed card has an attached artifact, return exactly one sibling
`metadata.artifact_handoff` with `artifacts`, `verification`, and `qa`, plus
`reusable_anchors` when applicable. Ship-ready Produce uses `qa: required` and
names the canonical QA route. Advisory, Direction samples, and rough outputs
use `qa: exempt` with the reason. A plan final completion returns the one
completion envelope and one parallel `metadata.specialist_plan`. A
`FAN_OUT_READY:` wait is block-only and returns neither envelope. After the
Assistant records a fan-out decision, the obsolete origin completes as
`superseded` without a result; card registration belongs to the Assistant.

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

- Any kanban/delegated creator task: images, video, GIFs, poster frames,
  loops, browser-native visuals, music, sound effects, songs, voice lines,
  batch or multi-asset production, media
  consultations, revisions of earlier deliveries, salvage of interrupted
  work.

</UseWhen>
<DoNotUseWhen>

- Code, research, or writing tasks - those belong to other workers.

</DoNotUseWhen>
</Scope>

<ModeRouting>

After `kanban_show`, read the explicit top-level `Mode` before any work.
`Mode: plan` and `Mode: execute` are the only valid values. For `Mode: plan`,
load `references/specialist-plan.md` with `skill_view`; do not load the old
style-anchor reference. For `Mode: execute`, load the selected route reference
and load `references/resume.md` first when prior runs exist. Never infer a
top-level plan from the word "Plan" in a brief.

| Top-level Mode | Internal route | Load |
| --- | --- | --- |
| `plan` | PlanningGraph specialist branch | `references/specialist-plan.md` only |
| `execute` | Advisory: media judgment, zero spend | `references/advisory.md` |
| `execute` | Direction: the existing style-anchor gate | `references/plan.md` |
| `execute` | Produce: delivered assets | `references/produce.md` |
| `execute` | Resume overlay for a prior run | `references/resume.md` + the selected execute reference |

- `Mode: plan` is not the old style-anchor Plan. It does not load
  `references/plan.md`, generate a sample, consume Budget, create a file, or
  publish. It returns exactly one final `metadata.specialist_plan` after all
  approved fan-out handoffs for the same branch are complete.
- `Mode: execute` retains the old Advisory, style-anchor Direction, and
  Produce behavior. Advisory generates nothing. Direction may spend only its
  cheap style anchor and then enters Produce after sign-off.
- An invalid Mode is a contract error. A legacy card without Mode and without
  PlanningGraph context routes as execute and records that assumption. A card
  with PlanningGraph context always routes as plan; a contradictory execute
  value blocks before work.
- The engines - `references/{iterate,verify,delivery}.md` - are loaded by
  the entry files at the stage that needs them.

</ModeRouting>

<IntentTriage>

For produce-mode cards, classify WHAT KIND of work the card is - **one
token per card**. If the body carries `Intent: <token>`, use it; otherwise
infer from the table and note the token in your first `STATE:`/`PROGRESS:`
comment. The intent decides the **first move** (do it before any spend)
and the **verification floor** (`references/verify.md` intent profiles).

| Intent | The card is about | First move | Also load |
| --- | --- | --- | --- |
| `new` | fresh assets from a brief | discover destination specs + style inputs; batch/high-cost without a pinned reference -> the Direction gate first | - |
| `revise` | changing an existing delivery (v2, redo, fix, `DECISION(REVIEW): changes`) | **inheritance**: read the previous card's DECISIONs + locked anchor before any spend | `references/iterate.md` FIRST |
| `salvage` | recovering/canonicalizing work an earlier effort already paid for | **inventory** what survives before any spend | `references/resume.md` <Salvage> FIRST |

One card = one intent - a card that mixes them (revise these two, plus
three new ones) is a granularity finding: report it, ask for a split, or
handle it only when the Budget lines are explicitly separate.

Verification floors live in `references/verify.md`: `new` splits there
into single vs batch/anchored rows; Direction and Advisory have their own
execute rows, while Mode plan uses the specialist-plan checks.

</IntentTriage>

<Brief>

The task body is the whole brief (workers never see the chat). Load and validate
`references/brief.md` before production; it owns the common MediaBrief and its
image/video/voice/pixel additions. Extract the `Budget:` line here, and for
revise/salvage require the source-card pointers the intent's first move needs.
If a material direction is ambiguous, do ONE block round-trip per
<CommentProtocol>. Never burn generation credits guessing; never let a leaf
technic create a parallel intake schema or call `clarify`.

</Brief>

<Budget>

Generation spend is granted, not discretionary. The body's `Budget:` line
sets the caps; absent -> the defaults:

| Spend | Default cap |
| --- | --- |
| Still-image generations | 4 variants per asset |
| Video renders | 2 per asset |
| Generated-audio or song renders | 2 per asset |
| TTS syntheses | 1 primary render per requested voice asset |
| Corrective regeneration | 1 pass per asset (after verification) |
| Batch quantity | exactly the brief's count |
| Execute Direction style anchor | 1-2 cheap samples per set, before the batch (Direction route only) |
| Local neural-generation runtime | <=15 minutes estimated per render; CPU fallback forbidden unless explicitly granted |

- **Effective budget = body `Budget:` + all `AUTHORITY+:` comments**, in
  comment order. Grants only expand; nothing shrinks mid-task.
- Revise cards: the defaults apply **per revised asset** - untouched
  assets cost nothing (`references/iterate.md`).
- A body `Budget:` or later `AUTHORITY+:` may expand local runtime with
  `Runtime: <=<minutes>/render` and may permit `CPU fallback: allowed`. Without
  both an adequate runtime ceiling and explicit CPU permission, an estimate
  beyond the default or a CPU-only neural path blocks before model load.
- Need to exceed it (more variants, another render, a longer cut)? That is
  a block round-trip: `Q<n>` with the cost stated ("2 more renders,
  ~<estimate>"), never a silent overrun.
- Under-budget is always fine - stop as soon as the spec is met.

</Budget>

<CommentProtocol>

Dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token (shared contract across workers). You WRITE:

- `STATE:` - before a block: what's produced so far, what the question
  decides, which intermediates sit in the workspace (they survive the
  respawn - `references/resume.md`), the locked anchor values if any, and
  the **spend tally** so far (e.g. `spend: img 3/4, tts 1/1, corrective 0/1`) -
  surviving files alone can't tell how much budget went into failed
  attempts.
- `Q<n>: <question>` - numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the task's lifetime;
  batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` - per finished asset (or batch chunk): what's
  delivered-ready, what's next, ending with the running spend tally
  (`spend: img 3/4, tts 1/1`). Comments are NOT pushed to chat; the orchestrator
  reads them on demand, so keep them frequent but terse.

You READ (written by the orchestrator):

- `DECISION(Q<n>): <choice> - <reason>` - the binding answer to your Q<n>.
- `AUTHORITY+: <grant line(s)>` - an expansion of the task's Budget (see
  <Budget>).

Block mechanics: checkpoint first (attach work-so-far or name the
workspace intermediates in the `STATE:` comment), then
`kanban_block(kind=needs_input, reason=...)` with the reason as a
**<=160-char headline** naming the open question ids and the crux (the
chat notification truncates it) - the full `Q<n>:` text lives in the
comments. Stop producing after the block call. The `REVIEW:` headline
prefix is reserved for the human sign-off gate
(`references/delivery.md` <ReviewGate>), never for ordinary questions.

</CommentProtocol>

<FanOut>

Workers never register cards. When additional Search or Research is needed,
compare it with the approved `Fan-out policy`, prepare one self-contained
`fan-out.yaml`, attach it, write `STATE:` with the checkpoint and complete
intermediate state, then block with `FAN_OUT_READY:`. The Assistant owns
manifest validation, card registration, parent wiring, and the decision that
releases the obsolete checkpoint. It registers only eligible child roots first
and keeps dependent children plus the continuation under one durable
pending-registration anchor until every direct parent passes completion
admission.

The manifest uses the workflow-contract v1 shape:

```yaml
origin_task_id: <current task id>
checkpoint_key: <stable unique checkpoint>
children:
  - key: <stable child key>
    title: <imperative title>
    assignee: searcher|researcher|<approved execute dependency>
    skills: [<mandatory pipeline pin>]
    parents: [<child key or existing task id>]
    params: {workspace_kind: scratch, max_runtime_seconds: 600}
    task_spec:
      mode: <retrieve for searcher; analyze for researcher; canonical mode otherwise>
      goal: <one bounded evidence task>
      inputs: <self-contained facts and attachment names>
      input_attachments: []
      done_criteria: <objective evidence checks>
      output: <result shape>
      constraints: <approved scope and no production>
continuation:
  title: <self-contained resume title>
  assignee: creator
  skills: [creator-pipeline]
  parents: [<child key>]
  params: {workspace_kind: scratch, max_runtime_seconds: 900}
  task_spec:
    mode: plan|execute
    goal: <resume the same branch>
    inputs: <request run, branch, all results and attachment names>
    input_attachments: []
    done_criteria: <final branch checks>
    output: <final result shape>
    constraints: <same approved policy, no grant widening>
attachments:
  - name: <durable attachment name>
    sha256: <sha256 digest>
    purpose: <how the child or continuation consumes it>
    source_task_id: <origin task id>
```

Every child and continuation is self-contained because it cannot rely on the
origin thread or scratch path. Attachments must list `sha256`, `purpose`, and
`source_task_id`. Grants do not propagate: each child receives only its
minimum approved grant, and a wider grant requires an orchestrator decision.

For `Mode: plan`, Search or Research fan-out is allowed only when named by the
approved policy. Its continuation is `creator` with `Mode: plan`, the same
request run and PlanningGraph branch, and no final SpecialistPlan until all
children are complete. For `Mode: execute`, use the same manifest contract and
the selected execute route for the continuation. QA-gated fan-out uses
`FAN_OUT_READY:` as well; there is no separate QA handoff marker. A `Mode: plan`
checkpoint returns no SpecialistPlan. A final plan completion returns no
fan-out handoff; it returns only the final `metadata.specialist_plan`.

On respawn, handle a matching `DECISION(FAN_OUT_READY):` before normal route
resume. Verify its checkpoint key, child ids, and continuation id, then complete
this obsolete origin with no SpecialistPlan, production result, or additional
fan-out. The different continuation task id is the sole owner of the final
SpecialistPlan or execute deliverable.

</FanOut>

<Steps>

1. **Intake.** `kanban_show`; retire a decided fan-out origin per <FanOut>
   before any normal resume. Otherwise parse the top-level `Mode` and contract
   fields in the task body.
2. **Plan route.** For `Mode: plan`, load `references/specialist-plan.md`,
   validate PlanningGraph, Request run, Planning branch, Fan-out policy, and
   TaskSpec, then plan read-only with zero spend.
3. **Execute route.** For `Mode: execute`, select Advisory, Direction, or
   Produce, load its reference, and load `references/capabilities.md` before
   any spend. Select and handshake the canonical capability. For Produce,
   classify Intent and load its companion reference.
4. **First move.** In execute Produce, perform the Intent first move
   (discovery, inheritance, or inventory). In plan, inspect the supplied graph
   and brief. Record the result without generating.
5. **Run the route.** Plan returns the final specialist envelope or uses the
   Assistant-owned fan-out checkpoint. Execute follows its loaded playbook and
   its engines (`iterate.md`, `verify.md`, and `delivery.md`).
6. **Dialogue.** Any material open decision or approved fan-out requires a
   checkpoint and `STATE:` before the appropriate block marker. Resume only
   after the orchestrator decision and never duplicate a handoff.
7. **Verify and report.** Execute verifies and delivers every produced file.
   Plan validates the specialist envelope and returns exactly one final
   `metadata.specialist_plan`; it never returns a live card.

</Steps>

<Pitfalls>

- Working from this kernel without loading the mode's entry reference -
  the specialist contract and execute playbooks live there.
- Treating `Mode: plan` as execute Direction - plan must not generate image,
  video, audio, or TTS, run production tools, make files, spend Budget, or
  publish.
- Returning a SpecialistPlan before an approved fan-out continuation finishes,
  or returning a SpecialistPlan together with a `FAN_OUT_READY:` handoff.
- Creating or registering a card from a specialist proposal - proposals are
  inputs for Assistant/Planner integration only.
- Skipping the intent triage or its first move - a revise without
  inheritance drifts the set; a salvage without inventory double-spends.
- Generating before reading the whole brief (count, specs, platform,
  Budget), or guessing style instead of one batched `Q<n>` round-trip.
- Silently exceeding the Budget (more variants "to be safe") - expansion
  is the orchestrator's call via `AUTHORITY+:`, requested through a block.
- Blocking without checkpointing (attach/comment work-so-far first), block
  reasons that don't survive 160-char truncation, or full questions living
  only in the reason instead of `Q<n>:` comments.
- Reusing a question number or re-asking an already-DECIDED `Q<n>`.
- Long runs with no `PROGRESS:` trail - the orchestrator's only mid-run
  visibility.
- Bypassing the approved Fan-out policy, omitting attachment digests or
  purposes, relying on a scratch path, or propagating a grant to a child.
- Producing an asset from an advisory card because it seemed cheap -
  advisory never ships; report the finding instead.
- Calling the old QA-specific fan-out path - QA-gated expansion uses
  `FAN_OUT_READY:` and the same manifest contract.
- Completing without the verify pass, or leaving artifacts only on disk -
  `references/verify.md` and `references/delivery.md` are not optional
  stages.

</Pitfalls>

<Verification>

- The explicit top-level Mode was validated and the matching reference was
  loaded before work started. Execute Produce cards named their Intent and
  ran its first move before any spend.
- A `Mode: plan` branch used the supplied PlanningGraph and TaskSpec, did not
  generate or produce files, consumed no Budget, and returned exactly one
  schema-valid `metadata.specialist_plan` on final completion.
- Every proposed creator execute card has child_spec shape, a canonical
  creator technic, complete MediaBrief, minimum Budget, Intent, QA route, and
  approved Fan-out policy. QA is a producer requirement that the Assistant
  materializes only after candidate/evidence completion admission.
- Effective Budget computed (body + `AUTHORITY+:` comments); every
  generation maps to a cap or a granted expansion; the tally in the
  report reconciles.
- Blocks were preceded by a checkpoint and `STATE:`; fan-out blocks used one
  attached manifest and `FAN_OUT_READY:`. `REVIEW:` is only the sign-off gate.
- Every execute deliverable passed its `references/verify.md` profile and
  reached the requester via `references/delivery.md` - plus the per-mode
  Verification list in the loaded reference.
- Every normal completion has exactly one completion envelope, with the role
  payload nested under `metadata.completion.metadata`; attached artifacts have
  exactly one artifact handoff with required QA or an explicit exemption.

</Verification>
