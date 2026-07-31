---
name: creator-pipeline
description: >-
  Creator's task front door — the mechanically-preloaded kernel (dispatchers
  pin it via kanban_create skills:["creator-pipeline"]). Route every card by
  its DELIVERABLE (ModeRouting): advisory (media judgment — feasibility,
  chain fit, Budget estimate; no asset, zero spend) vs plan (a locked
  creative direction — cheap style anchor + sign-off before an expensive
  batch) vs produce (delivered assets), with resume as the re-entry overlay
  after a block/respawn. Then triage the INTENT (IntentTriage): new / revise
  / salvage — one token per card deciding the first move (spec discovery vs
  inheritance vs inventory) and the verification floor. This kernel owns the
  Budget grant contract (spend caps + AUTHORITY+ expansions), the kanban
  comment protocol (STATE/Q<n>/PROGRESS, DECISION/AUTHORITY+),
  checkpoint-then-block, and FanOut. Entry playbooks live in
  references/{advisory,plan,produce,resume}.md; engines in
  references/{iterate,verify,delivery}.md (feedback-driven revision, the
  V1-V6 media checks with per-intent profiles, and attachment + Review gate
  + evidence-backed reporting) — load via skill_view file_path, never skip.
version: 4.3.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [media, image, video, gif, tts, production, kanban, delivery, verification, triage, intent]
    category: creative
    related_skills: [creator-generated-image, creator-article-illustration, creator-infographic, creator-svg-diagram, creator-excalidraw-diagram, creator-logo-icons, creator-text-card, creator-meme, creator-ascii-art, creator-audio-visualization, creator-audio-generation, creator-song-generation, creator-gif-sourcing, creator-generated-video, creator-html-motion, creator-p5js-experience, creator-ascii-video, creator-manim-explainer, creator-pixel-art, creator-pixel-video, creator-knowledge-comic, creator-brand-asset-sourcing]
---

<Goal>

Turn a kanban media brief into delivered assets: right generation chain per
asset type, credits spent deliberately, outputs verified with your own
eyes, artifacts attached to the task — never stranded on disk. You produce
hands-on (generation toolsets, ffmpeg, the HyperFrames CLI), but the spend
is granted, not discretionary: the Budget contract and the comment protocol
in this kernel govern every mode.

Three deliverable kinds = three modes (<ModeRouting>): **advisory** (media
judgment, zero spend), **plan** (a locked direction — anchor before batch),
**produce** (the assets themselves). Orthogonally, every produce card has
ONE **intent** (<IntentTriage>) — new / revise / salvage — deciding its
first move and its verification floor.

The worker process is disposable (block ends the run; unblock respawns a
fresh one), so continuity lives in durable layers only: the kanban comment
thread (decisions, locked anchors, the spend tally), attachments, and the
surviving task workspace. Never rely on a long-running session's memory —
and never treat already-paid-for work as waste (`references/resume.md`).

This kernel is mechanically preloaded on every card — keep it lean:
routing, triage, and contracts live here; playbook detail lives in
`references/` (loaded on demand) and must never migrate back in.

</Goal>

<Scope>
<UseWhen>

- Any kanban/delegated creator task: images, video, GIFs, poster frames,
  loops, browser-native visuals, music, sound effects, songs, voice lines,
  batch or multi-asset production, media
  consultations, revisions of earlier deliveries, salvage of interrupted
  work.

</UseWhen>
<DoNotUseWhen>

- Code, research, or writing tasks — those belong to other workers.

</DoNotUseWhen>
</Scope>

<ModeRouting>

First action after `kanban_show`: classify the card by its **deliverable**,
then **load the matching entry reference with `skill_view`
(`file_path=references/<file>`) before doing any work** — plus
`references/resume.md` FIRST when the task has prior runs. Never proceed on
this kernel alone.

| The card's deliverable | Mode | Load |
| --- | --- | --- |
| **Media judgment** — feasibility, chain fit, cost/Budget estimate; no asset requested | Advisory | `references/advisory.md` |
| **A locked direction** — a consistent multi-asset set / batch, or a single high-cost asset, whose creative direction is not pinned to an exact reference yet | Plan | `references/plan.md` |
| **Assets** — anything that delivers files (one cheap asset, an exact reference to match, an approved anchor to batch from) | Produce | `references/produce.md` |
| **(Re-entry, not a mode)** — the task has prior runs/comments: respawn after a block, crash, or timeout | Resume overlay | `references/resume.md` **+** the underlying mode's file |

- **Openers are optional hints, not contracts.** `Advisory — inform the
  plan, don't ship.` → Advisory; `Plan —` → Plan. A card with no opener
  routes by deliverable; when it delivers assets, Produce is the default —
  but a batch/high-cost card without a pinned reference belongs to Plan
  even without the opener.
- Advisory generates nothing — an advisory card that turns out to need
  real production is reported as such, **never silently produced**. Plan
  spends only the cheap anchor, then continues into Produce after
  sign-off.
- The engines — `references/{iterate,verify,delivery}.md` — are loaded by
  the entry files at the stage that needs them.

</ModeRouting>

<IntentTriage>

For produce-mode cards, classify WHAT KIND of work the card is — **one
token per card**. If the body carries `Intent: <token>`, use it; otherwise
infer from the table and note the token in your first `STATE:`/`PROGRESS:`
comment. The intent decides the **first move** (do it before any spend)
and the **verification floor** (`references/verify.md` intent profiles).

| Intent | The card is about | First move | Also load |
| --- | --- | --- | --- |
| `new` | fresh assets from a brief | discover destination specs + style inputs; batch/high-cost without a pinned reference → the Plan gate first | — |
| `revise` | changing an existing delivery (v2, «作り直し», «修正», `DECISION(REVIEW): changes`) | **inheritance**: read the previous card's DECISIONs + locked anchor before any spend | `references/iterate.md` FIRST |
| `salvage` | recovering/canonicalizing work an earlier effort already paid for | **inventory** what survives before any spend | `references/resume.md` <Salvage> FIRST |

One card = one intent — a card that mixes them (revise these two, plus
three new ones) is a granularity finding: report it, ask for a split, or
handle it only when the Budget lines are explicitly separate.

Verification floors live in `references/verify.md`: `new` splits there
into single vs batch/anchored rows; plan and advisory modes have their
own rows.

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
sets the caps; absent → the defaults:

| Spend | Default cap |
| --- | --- |
| Still-image generations | 4 variants per asset |
| Video renders | 2 per asset |
| Generated-audio or song renders | 2 per asset |
| TTS syntheses | 1 primary render per requested voice asset |
| Corrective regeneration | 1 pass per asset (after verification) |
| Batch quantity | exactly the brief's count |
| Plan-mode style anchor | 1-2 cheap samples per set, before the batch (Plan mode only) |
| Local neural-generation runtime | <=15 minutes estimated per render; CPU fallback forbidden unless explicitly granted |

- **Effective budget = body `Budget:` + all `AUTHORITY+:` comments**, in
  comment order. Grants only expand; nothing shrinks mid-task.
- Revise cards: the defaults apply **per revised asset** — untouched
  assets cost nothing (`references/iterate.md`).
- A body `Budget:` or later `AUTHORITY+:` may expand local runtime with
  `Runtime: <=<minutes>/render` and may permit `CPU fallback: allowed`. Without
  both an adequate runtime ceiling and explicit CPU permission, an estimate
  beyond the default or a CPU-only neural path blocks before model load.
- Need to exceed it (more variants, another render, a longer cut)? That is
  a block round-trip: `Q<n>` with the cost stated ("2 more renders,
  ~<estimate>"), never a silent overrun.
- Under-budget is always fine — stop as soon as the spec is met.

</Budget>

<CommentProtocol>

Dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token (shared contract across workers). You WRITE:

- `STATE:` — before a block: what's produced so far, what the question
  decides, which intermediates sit in the workspace (they survive the
  respawn — `references/resume.md`), the locked anchor values if any, and
  the **spend tally** so far (e.g. `spend: img 3/4, tts 1/1, corrective 0/1`) —
  surviving files alone can't tell how much budget went into failed
  attempts.
- `Q<n>: <question>` — numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the task's lifetime;
  batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` — per finished asset (or batch chunk): what's
  delivered-ready, what's next, ending with the running spend tally
  (`spend: img 3/4, tts 1/1`). Comments are NOT pushed to chat; the orchestrator
  reads them on demand, so keep them frequent but terse.

You READ (written by the orchestrator):

- `DECISION(Q<n>): <choice> — <reason>` — the binding answer to your Q<n>.
- `AUTHORITY+: <grant line(s)>` — an expansion of the task's Budget (see
  <Budget>).

Block mechanics: checkpoint first (attach work-so-far or name the
workspace intermediates in the `STATE:` comment), then
`kanban_block(kind=needs_input, reason=...)` with the reason as a
**<=160-char headline** naming the open question ids and the crux (the
chat notification truncates it) — the full `Q<n>:` text lives in the
comments. Stop producing after the block call. The `REVIEW:` headline
prefix is reserved for the human sign-off gate
(`references/delivery.md` <ReviewGate>), never for ordinary questions.

</CommentProtocol>

<FanOut>

When part of the task belongs to another worker (parallel lookups, prose,
analysis) or exceeds your tools, decompose on the board — never wait
in-process:

1. `kanban_create` the child cards — each body self-contained per the
   orchestrator's task-spec rules (a child never sees this task's thread;
   e.g. a searcher reference hunt before an expensive render batch), and
   each pinning its assignee's pipeline kernel
   (`skills=["<profile>-pipeline"]`).
2. `kanban_create` a **continuation card assigned to your own profile**
   with `parents=[the child ids]` and `skills=["creator-pipeline"]`: its
   body says what to do with their results (their completion
   summaries/metadata arrive in the injected context; `kanban_show` a
   parent id for detail). It is a bookmark for a future run of you — that
   run starts with zero memory of this one, so the body must stand alone
   (include the `Intent:` token, the effective Budget, and the locked
   anchor values).
3. `kanban_complete` the current card ("decomposed into <ids>") and stop —
   never wait for children. The dispatcher wakes the continuation card
   when they all finish (fan-in).

Rules:

- **Grants never propagate.** Write into a child at most your own effective
  Budget (spend caps) — never more. A child that would need a wider grant
  is a question for the orchestrator: block on YOUR card, don't mint.
- Children you create notify nobody (no chat subscription); the
  orphan-watchdog cron is the safety net, not a license. Decisions that
  need the user go through your own card's block round-trip, never a
  child's.
- `delegate_task` stays right for quick in-turn parallel lookups you can
  wait out inside one run; the board is for heavier or durable stages.

</FanOut>

<Steps>

1. **Intake.** `kanban_show`; parse the <Brief> and the <Budget> grant.
2. **Route + triage.** Pick the mode per <ModeRouting>, load the entry
   reference via `skill_view`; for every plan or produce card load
   `references/capabilities.md`, select and handshake its leaf/core/external
   capability before any spend. For produce cards, also classify the intent per
   <IntentTriage> and load its companion file.
3. **First move** per the intent row (spec discovery / inheritance /
   inventory); record its outcome in a comment before spending.
4. **Execute** the loaded playbook; the entry files load the engines
   (`iterate.md` / `verify.md` / `delivery.md`) at their stages.
5. **Dialogue.** Any material open decision → checkpoint, `STATE:` +
   `Q<n>:`, block once per <CommentProtocol>; answers arrive as
   `DECISION(Q<n>)` after a respawn.
6. **Verify** every produced file per `references/verify.md` (the
   intent's profile) — your eyes are the gate.
7. **Deliver + report** per `references/delivery.md` (attachments, the
   Review gate when the body carries `Review:`, evidence-backed report,
   one-line chat summary); complete the task.

</Steps>

<Pitfalls>

- Working from this kernel without loading the mode's entry reference —
  the playbooks (chains, anchor procedure, inheritance, inventory) live
  there.
- Skipping the intent triage or its first move — a revise without
  inheritance drifts the set; a salvage without inventory double-spends.
- Generating before reading the whole brief (count, specs, platform,
  Budget), or guessing style instead of one batched `Q<n>` round-trip.
- Silently exceeding the Budget (more variants "to be safe") — expansion
  is the orchestrator's call via `AUTHORITY+:`, requested through a block.
- Blocking without checkpointing (attach/comment work-so-far first), block
  reasons that don't survive 160-char truncation, or full questions living
  only in the reason instead of `Q<n>:` comments.
- Reusing a question number or re-asking an already-DECIDED `Q<n>`.
- Long runs with no `PROGRESS:` trail — the orchestrator's only mid-run
  visibility.
- Producing an asset from an advisory card because it seemed cheap —
  advisory never ships; report the finding instead.
- Completing without the verify pass, or leaving artifacts only on disk —
  `references/verify.md` and `references/delivery.md` are not optional
  stages.

</Pitfalls>

<Verification>

- The mode was routed by deliverable per <ModeRouting> and the entry
  reference was loaded before work started; produce cards named their
  intent (body or inferred + noted) and ran its first move before any
  spend.
- Effective Budget computed (body + `AUTHORITY+:` comments); every
  generation maps to a cap or a granted expansion; the tally in the
  report reconciles.
- Blocks were preceded by a checkpoint + `STATE:`/`Q<n>:` comments, with a
  <=160-char reason headline; `REVIEW:` used only for the sign-off gate.
- Every deliverable passed its `references/verify.md` profile and reached
  the requester via `references/delivery.md` — plus the per-mode
  Verification list in the loaded reference.

</Verification>
