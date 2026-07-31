# Creative approach — reference

Loaded after Step 3 picks **Approach=Creative**. Dispatches to creator for
any media production; you produce no media yourself.

## When to pick Creative

- **Any media production** — image, video, GIF, voice, single or batch.
  Always goes to creator, no matter how small. The front door only collects
  the brief and dispatches.
- If the request mixes media with implementation/research, Plan likely
  applies instead (Plan can fan out a creator sub-task mid-stream) — see
  `references/plan.md`.

## What to collect before dispatching (MediaBrief)

Gather (from the chat, the user, and memory) before dispatching, so creator
never has to block on style questions or burn credits guessing:

- **Purpose & audience** — what the asset is for, where it will be seen.
- **Destination & specs** — platform/placement and its constraints
  (dimensions, aspect ratio, duration, format, file-size cap) when known.
- **Style direction** — tone, palette, brand assets, reference images/links;
  paste or link references into the task body.
- **Technique** — when the production method is clear, use the canonical
  Creator technic from the table below and repeat it as a `Technique:` line in
  the body. The body lets Creator recover even if an optional preload is
  skipped.
- **Quantity & variants** — how many, which sizes/crops.
- **Budget** — generation-spend caps as a `Budget:` line. Omitted → creator
  applies its defaults (4 image variants / 2 video renders per asset, 1
  corrective pass, batch = the brief's count, plus a 1-2 cheap-sample
  anchor allowance in plan mode). Widen it up front for
  exploratory work the user has sanctioned; expansions mid-task go through
  `AUTHORITY+:` comments only (see below), never a body edit.
- **Deadline / priority.**

Ask the user at most one compact round of questions for missing essentials
(a `clarify` if options exist); fill sensible defaults yourself and say so.

## Technique selection (skills)

**Every creator card carries `skills: ["creator-pipeline"]`** — the
dispatcher preloads pinned skills mechanically into the worker's system
prompt, which turns creator's routing/Budget kernel from a prompt-level
instruction into a guarantee (same rule as engineer's pipeline pin).

When the final deliverable and production method clearly select a canonical
technic, force-load it on top:
`kanban_create(..., skills=["creator-pipeline", "<technique>"])`. Set a
technique only when the request implies one; otherwise pin the pipeline
alone and let creator route by asset type.

| Request signal / final method | Canonical skill |
| --- | --- |
| generated cover, hero, illustration, thumbnail, text-free social/document art | `creator-generated-image` |
| favicon / Apple / PWA / app-icon set from a first-party SVG | `creator-logo-icons` |
| OG / social / title card with exact text | `creator-text-card` |
| text-to-video / image-to-video / reference-guided generated clip | `creator-generated-video` |
| pixel-art still / retro sprite / ドット絵 | `creator-pixel-art` |
| pixel animation / sprite motion / ドット絵動画 / pixel GIF | `creator-pixel-video` |
| official third-party logo/mark sourcing | `creator-brand-asset-sourcing` |

Before pinning any technic beyond `creator-pipeline`, verify that exact name on
the Creator profile. Canonical leaves have matching files under
`~/.hermes/profiles/creator/skills/technic/<name>/SKILL.md`. Never pin the bare
external name `pixel-art`: official and shared copies can collide, and the
canonical Pixel technics resolve their optional implementation scripts.

The catalog is larger than this curated set — creator scans it for niche asset
types. External techniques need an assignee-profile preflight and sometimes a
running prerequisite (`hyperframes` needs its toolchain, Blender a desktop
session). If availability is uncertain, put the requested method in the body
and pin only `creator-pipeline`; Creator either resolves it or blocks before
spend.

## Dispatching

Put all of the MediaBrief in the task body (`Inputs` / `Constraints`) —
creator cannot see this chat. Use the standard `<TaskSpec>` shape from the
main skill, with:

- `assignee: creator`
- `skills: ["creator-pipeline"]` (+ any technique — see above)
- `workspace_kind: scratch` (or `dir` if assets must land somewhere specific)
- The MediaBrief fields in the body
- A `Technique: <canonical-name>` line when the table resolves one
- Output spec: file format(s); every final artifact is delivered via
  `kanban_attach` (scratch dies on completion), with
  `~/Workspaces/.deliverables/` only as an additional copy destination
  when the user wants files on disk

For a **consistent multi-asset set** or a **high-cost asset** (a long video),
open the body with `Plan —`: creator locks the style on a cheap sample and
blocks for sign-off before spending the batch budget (its plan mode). Approve
the anchor with a `DECISION(Q<n>):`; when the brief set `Review: required`,
creator blocks with a `REVIEW:` headline instead — relay it to the user and
answer with `DECISION(REVIEW): approved` (or `changes — <list>`). The same
task then continues into the batch. One cheap asset dispatches normally
(produce).

Ack with the task id and deliver on the completion notification. Small
single assets go to creator too — never improvise media inline.

## Revision dispatches (redo / fix an earlier delivery)

When the user asks to change something a previous creator card delivered
(«作り直し», «修正», "make it v2", or feedback after a completion), the new
card is a **revise** card, and its economics depend on inheritance — a
revise card that can't find the previous work regenerates from scratch and
drifts the set. The body MUST carry:

- `Intent: revise` (creator routes its first move on it), and Inputs with
  the **previous card id** and its anchor pointers (the completion
  metadata's `anchor` values — style spec / palette / seed / voice — or
  the attachment names).
- **Itemized feedback** — what changes, per asset; relay the user's words,
  not a paraphrase of the style. Everything unnamed is treated as approved
  and preserved.
- A fresh `Budget:` line — the caps apply per revised asset; untouched
  assets cost nothing.

A wholesale direction change («全面組み直し», a new concept) is not a
revise: creator will stop and re-anchor via its plan gate — expect a cheap
sample + sign-off round before any full re-render, and prefer opening such
a card with `Plan —` yourself. Cards that rescue interrupted or stranded
work instead carry `Intent: salvage` + the source card/workspace pointers
(inventory first, spend only on what's genuinely missing).

## After dispatch

Hand off to Step 7's standard mechanics: `<AfterCreate>` ack, `<Failures>`
recovery, `<BlockedTriage>` for any creator block (rare — the MediaBrief
should have eliminated style ambiguity up front). Creator speaks the shared
worker comment protocol: blocks arrive as `Q<n>:` comments (style choice,
budget-overrun request with a cost estimate, or a missing prerequisite such
as a desktop app for an opt-in chain); answer each with a
`DECISION(Q<n>):` comment before unblocking, and grant extra generation
spend with an `AUTHORITY+:` line. Its `PROGRESS:` comments land per
finished asset — `<StatusCheck>` works the same as for engineer.

Creator's first state/progress note also carries its capability handshake: a
canonical leaf + version, `core:tts`, or a preflighted `external:<skill>`, plus
the concrete backend/path and preflight result. A missing or mismatched required
capability must be resolved before any generation spend; do not treat generic
image/video output as an acceptable silent fallback.
