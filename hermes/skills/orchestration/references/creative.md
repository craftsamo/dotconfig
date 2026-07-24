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
- **Quantity & variants** — how many, which sizes/crops.
- **Budget** — generation-spend caps as a `Budget:` line. Omitted → creator
  applies its defaults (4 image variants / 2 video renders per asset, 1
  corrective pass, batch = the brief's count). Widen it up front for
  exploratory work the user has sanctioned; expansions mid-task go through
  `AUTHORITY+:` comments only (see below), never a body edit.
- **Deadline / priority.**

Ask the user at most one compact round of questions for missing essentials
(a `clarify` if options exist); fill sensible defaults yourself and say so.

## Technique selection (skills)

When the request names or clearly implies a specific craft/style, force-load
the matching creator skill by passing it in the task's `skills:` field
(`kanban_create(..., skills=["<name>"])`) — creator loads that skill's craft
on top of `media-production`. Set a technique only when the request implies
one; otherwise leave it off and let creator route by asset type.

| Request signal | skill |
| --- | --- |
| pixel art / retro sprite / ドット絵 | `pixel-art` |
| meme / ミーム | `meme-generation` |
| educational or non-software diagram / 概念図 / how-X-works figure | `concept-diagrams` |
| article or blog illustration / 記事挿絵 | `baoyu-article-illustrator` |
| knowledge comic / 漫画 / educational strip | `baoyu-comic` |

The catalog is larger than this curated set — creator scans it for other
asset types (`<AssetRouting>` in `media-production`). Some techniques need a
running prerequisite (HTML-to-video `hyperframes` needs its toolchain,
`blender` a Blender session); dispatch those only when the prereq is up, else
creator blocks with a `Q<n>:` naming what to start.

## Dispatching

Put all of the MediaBrief in the task body (`Inputs` / `Constraints`) —
creator cannot see this chat. Use the standard `<TaskSpec>` shape from the
main skill, with:

- `assignee: creator`
- `workspace_kind: scratch` (or `dir` if assets must land somewhere specific)
- The MediaBrief fields in the body
- Output spec: file format(s); every final artifact is delivered via
  `kanban_attach` (scratch dies on completion), with
  `~/Workspaces/.deliverables/` only as an additional copy destination
  when the user wants files on disk

For a **consistent multi-asset set** or a **high-cost asset** (a long video),
open the body with `Plan —`: creator locks the style on a cheap sample and
blocks for sign-off before spending the batch budget (its plan mode). Approve
the anchor with a `DECISION(Q<n>):` — or relay it to the user when the brief
set `Review: required` — and the same task continues into the batch. One cheap
asset dispatches normally (produce).

Ack with the task id and deliver on the completion notification. Small
single assets go to creator too — never improvise media inline.

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
