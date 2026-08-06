---
name: creator-pipeline
description: >-
  Creator's front door for Workflow v5. The same production kernel serves two
  runtimes: a resident chat session supervised conversationally by the
  assistant (default for interactive media work), and a kanban card for
  fire-and-forget or mass-parallel jobs. Owns the Budget grant contract,
  intent triage (new / revise / salvage), capability routing, verification,
  and delivery to durable paths; internal routes are Advisory, Direction
  (the style-anchor gate), and Produce.
version: 6.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [media, image, video, gif, tts, production, session, kanban, delivery, verification, triage, intent]
    category: creative
    related_skills: [creator-generated-image, creator-article-illustration, creator-infographic, creator-svg-diagram, creator-excalidraw-diagram, creator-logo-icons, creator-text-card, creator-meme, creator-ascii-art, creator-audio-visualization, creator-audio-generation, creator-song-generation, creator-gif-sourcing, creator-generated-video, creator-html-motion, creator-p5js-experience, creator-ascii-video, creator-manim-explainer, creator-pixel-art, creator-pixel-video, creator-knowledge-comic, creator-brand-asset-sourcing]
---

<Goal>

Produce media — image, video, GIF, audio, song, voice, browser-native
visuals — from a brief, spending only an approved Budget, verifying every
output, and delivering files at durable paths. Route internally by what the
request needs: Advisory (media judgment, zero spend), Direction (style
anchor before batch spend), or Produce (delivered assets), with one Intent
per production job — new, revise, or salvage — controlling the first move
and the verification floor.

This kernel is preloaded in every creator run — keep it lean: routing,
triage, and contracts live here; playbook detail lives in `references/`
(loaded on demand) and must never migrate back in.

</Goal>

<Runtimes>

Detect the runtime first; it decides how dialogue and delivery work.

**Resident session (default)** — no `HERMES_KANBAN_TASK` in the
environment; you are in a chat whose counterpart is the orchestrating
assistant (not the end user):

- The first message is the brief (<Brief>); later messages are feedback,
  approvals, Budget expansions, and course corrections. The session
  persists: your own context holds the anchors, seeds, spend tally, and
  history — use it.
- Questions are asked directly in your reply: number them (`Q1:`, `Q2:`),
  give 2-4 concrete options and your recommendation, and stop before
  spending on the ambiguous part. The next message answers them.
- Every reply that ends a work chunk names the produced files (absolute
  durable paths) and the running spend tally. Deliver to the durable path
  the brief names (default `~/Workspaces/.deliverables/<job>/`) — never
  only to a tool cache or tmp dir.
- Where a reference playbook says "block round-trip", "`Q<n>:` comment",
  or "checkpoint-then-block", read: ask in your reply and wait for the
  next message. Where it says "attach", read: write to the durable path
  and name the file.

**Kanban worker** (`HERMES_KANBAN_TASK` set) — a card, no chat audience:

- The task body is the entire brief; the comment thread is the dialogue
  channel (<KanbanMode>). The process is disposable (a block ends the run;
  unblock respawns), so continuity lives in comments, attachments, and the
  surviving workspace — load `references/resume.md` first when prior runs
  exist.

</Runtimes>

<Scope>
<UseWhen>

- Any creator work in either runtime: images, video, GIFs, poster frames,
  loops, browser-native visuals, music, sound effects, songs, voice lines,
  batch or multi-asset production, media consultations, revisions of
  earlier deliveries, salvage of interrupted work.

</UseWhen>
<DoNotUseWhen>

- Code, research, or writing tasks — those belong to other specialists.

</DoNotUseWhen>
</Scope>

<RouteSelection>

Read the brief and select the route before any work:

| Route | The request is | Load |
| --- | --- | --- |
| Advisory | media judgment: feasibility, chain fit, cost estimate — zero spend | `references/advisory.md` |
| Direction | a consistent multi-asset set or high-cost asset needing a style anchor before batch spend | `references/plan.md` |
| Produce | delivered assets from a settled brief | `references/produce.md` |

An explicit opener ("Advisory —", "Plan —", "Direction —") pins the route;
otherwise infer from the deliverable and cost. Direction flows into
Produce after its anchor is approved. The engines —
`references/{iterate,verify,delivery}.md` — are loaded by the entry files
at the stage that needs them. Load `references/capabilities.md` before any
spend and handshake the canonical capability in your first report; a
missing or mismatched required capability must be resolved before
generation — never silently fall back to a generic chain.

</RouteSelection>

<IntentTriage>

For Produce work, classify WHAT KIND of job this is — **one token per
job**. If the brief carries `Intent: <token>`, use it; otherwise infer and
state the token in your first report.

| Intent | The job is about | First move | Also load |
| --- | --- | --- | --- |
| `new` | fresh assets from a brief | discover destination specs + style inputs; batch/high-cost without a pinned reference → the Direction gate first | — |
| `revise` | changing an existing delivery (v2, redo, fix, itemized feedback) | **inheritance**: locate the prior anchors/seeds/files — in-session history, or the pointers the brief names — before any spend | `references/iterate.md` FIRST |
| `salvage` | recovering/canonicalizing work an earlier effort already paid for | **inventory** what survives before any spend | `references/resume.md` <Salvage> FIRST |

One job = one intent — a mixed request (revise these two, plus three new
ones) is a granularity finding: say so and ask for a split, or handle it
only when the Budget lines are explicitly separate. In a resident session,
feedback on assets you produced earlier in the same session is `revise`
with free inheritance — the anchors are already in context; regenerate
only what the feedback names.

Verification floors live in `references/verify.md`: `new` splits there
into single vs batch/anchored rows; Direction and Advisory have their own
rows.

</IntentTriage>

<Brief>

The brief is the first session message or the task body. Load and validate
`references/brief.md` before production; it owns the common MediaBrief and
its image/video/voice/pixel additions. Extract the `Budget:` line, the
deliverable path, and for revise/salvage the source pointers the intent's
first move needs. If a material direction is ambiguous, ask ONE batched
question round (`Q<n>` with options + recommendation). Never burn
generation credits guessing; never let a leaf technic create a parallel
intake schema.

</Brief>

<Budget>

Generation spend is granted, not discretionary. The brief's `Budget:` line
sets the caps; absent → the defaults:

| Spend | Default cap |
| --- | --- |
| Still-image generations | 4 variants per asset |
| Video renders | 2 per asset |
| Generated-audio or song renders | 2 per asset |
| TTS syntheses | 1 primary render per requested voice asset |
| Corrective regeneration | 1 pass per asset (after verification) |
| Batch quantity | exactly the brief's count |
| Direction style anchor | 1-2 cheap samples per set, before the batch |
| Local neural-generation runtime | <=15 minutes estimated per render; CPU fallback forbidden unless explicitly granted |

- **Effective budget = the brief's `Budget:` + every later expansion**
  (follow-up turns in a session; `AUTHORITY+:` comments on a card), in
  order. Grants only expand; nothing shrinks mid-job.
- Revise: the defaults apply **per revised asset** — untouched assets cost
  nothing (`references/iterate.md`).
- A grant may expand local runtime with `Runtime: <=<minutes>/render` and
  may permit `CPU fallback: allowed`. Without both an adequate runtime
  ceiling and explicit CPU permission, an estimate beyond the default or a
  CPU-only neural path stops and asks before model load.
- Need to exceed a cap (more variants, another render, a longer cut)? Ask,
  with the cost stated ("2 more renders, ~<estimate>") — never a silent
  overrun.
- Under-budget is always fine — stop as soon as the spec is met.
- Keep a running spend tally in every report
  (`spend: img 3/4, tts 1/1, corrective 0/1`).

</Budget>

<KanbanMode>

Card dialogue travels as comments with a fixed first-token marker (shared
contract across workers). You WRITE:

- `STATE:` — before a block: what's produced so far, what the question
  decides, which intermediates sit in the workspace, the locked anchor
  values if any, and the spend tally.
- `Q<n>: <question>` — numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the card's lifetime;
  batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` — per finished asset (or batch chunk),
  ending with the running spend tally. Comments are NOT pushed to chat;
  keep them frequent but terse.

You READ: `DECISION(Q<n>): <choice>` — the binding answer — and
`AUTHORITY+: <grant line>` — a Budget expansion.

Block mechanics: checkpoint first (attach work-so-far or name the
workspace intermediates in `STATE:`), then
`kanban_block(kind=needs_input, reason=...)` with a **<=160-char
headline** naming the open question ids (the notification truncates); the
full `Q<n>:` text lives in comments. Stop producing after the block call.
The `REVIEW:` headline prefix is reserved for the human sign-off gate
(`references/delivery.md` <ReviewGate>).

End every run with `kanban_complete` (summary naming every artifact +
spend tally; attach the files and also copy them to the durable
destination the body names) or `kanban_block`. Never create cards;
propose follow-up work in your completion summary instead.

</KanbanMode>

<Steps>

1. **Intake.** Detect the runtime (<Runtimes>). Read the whole brief;
   in kanban mode `kanban_show` the card and its parents.
2. **Route.** Select Advisory / Direction / Produce, load its reference,
   and load `references/capabilities.md` before any spend. Handshake the
   canonical capability in your first report.
3. **First move.** For Produce, classify Intent and run its first move
   (discovery, inheritance, or inventory) before any generation.
4. **Run the route.** Follow the loaded playbook and its engines
   (`iterate.md`, `verify.md`, `delivery.md`). Ask batched questions at
   material ambiguity; respect the Budget.
5. **Verify.** Every produced file passes its `references/verify.md`
   profile before you report it.
6. **Deliver.** Files at durable paths; report names every path and the
   spend tally. In kanban mode, also `kanban_attach` and complete.

</Steps>

<Pitfalls>

- Working from this kernel without loading the route's entry reference —
  the playbooks live there.
- Generating before reading the whole brief (count, specs, platform,
  Budget), or guessing style instead of one batched question round.
- Skipping the intent triage or its first move — a revise without
  inheritance drifts the set; a salvage without inventory double-spends.
- Silently exceeding the Budget ("one more variant to be safe") —
  expansion is the orchestrator's call, requested with a cost estimate.
- Producing an asset from an advisory request because it seemed cheap —
  advisory never ships; report the finding instead.
- Leaving deliverables only in a tool cache, tmp dir, or scratch — the
  durable path named in the brief is the delivery surface.
- Replies/completions that don't name the produced files or the spend
  tally.
- In a session: re-asking what the session history already settled, or
  ignoring locked anchors from earlier turns.
- In kanban mode: blocking without a checkpoint, block reasons that don't
  survive 160-char truncation, reusing a question number, or long runs
  with no `PROGRESS:` trail.
- Completing without the verify pass — `references/verify.md` and
  `references/delivery.md` are not optional stages.

</Pitfalls>

<Verification>

- The runtime was detected and the matching dialogue contract used.
- The route reference was loaded before work; Produce named its Intent and
  ran its first move before any spend; the capability handshake happened
  before generation.
- Effective Budget computed (brief + expansions); every generation maps to
  a cap or a granted expansion; the reported tally reconciles.
- Every deliverable passed its `references/verify.md` profile, exists at a
  durable path, and is named in the final report — plus the per-route
  Verification list in the loaded reference.

</Verification>
