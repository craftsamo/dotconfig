# Creative capability — plan / execute / qa

Load whenever the work involves media: image, video, GIF, voice, music,
diagrams — advisory, single asset, or batch. All media production runs in a
**creator** resident session; the assistant produces no media itself, ever.

## Plan

Collect the MediaBrief from chat, memory, and the user before starting the
session — creator should never burn credits guessing style:

- **Purpose & audience** — what the asset is for, where it will be seen.
- **Destination & specs** — platform/placement constraints (dimensions,
  aspect ratio, duration, format, file-size cap) when known.
- **Style direction** — tone, palette, brand assets, reference
  images/links; pass references via `--image` or paths in Inputs.
- **Quantity & variants** — how many, which sizes/crops.
- **Budget** — a `Budget:` line with generation-spend caps; omitted =
  creator defaults (4 image variants / 2 video renders per asset, 1
  corrective pass, batch = the brief's count). Widen it up front for
  sanctioned exploratory work; expand mid-session in a later turn.
- **Deadline / priority.**

Ask at most one compact `clarify` round for missing essentials; fill
sensible defaults yourself and say so.

**Feasibility and cost questions go to the session first**: for a novel
technique, an expensive asset, or an uncertain chain, open the session in
advisory ("この方針は現実的? 概算コストは?") before promising the user
anything. The reply grounds your plan.

**Style anchor before batch spend** — for a consistent multi-asset set or
a high-cost asset (a long video), the first production turn asks for one
cheap sample/anchor. Check it (<ModeQA>), show the user when taste is
theirs to judge, then approve the batch in the next turn. Never let a
batch run before its anchor passed.

## Execute

Start `resident-session.sh start <topic>-creator …` with the SessionBrief
carrying the MediaBrief. Then supervise:

- Production lands as files at the durable path named in `Deliverable:`
  (default `~/Workspaces/.deliverables/<job>/`); the reply names every
  file. Scratch-only output is a defect — say so in the next turn.
- Feedback and revisions are turns in the same session, itemized per
  asset ("C2: 白紙束ではなく開いた本に", "C9: 最後2秒は開眼"). Everything
  unnamed is preserved — the session already holds the style anchors,
  seeds, and history, so revisions cost only the changed assets.
- Budget expansion requests come back as a question in the reply; approve
  within what the user sanctioned, relay beyond it.
- A wholesale direction change («全面組み直し», new concept) re-anchors:
  new cheap sample + sign-off before any full re-render.

Mass-parallel production of independent assets (each with a settled brief,
no per-item feedback expected) may go to kanban instead —
`references/kanban-lite.md`, `assignee: creator`,
`skills: ["creator-pipeline"]`.

## QA

Verify actual artifacts before the user sees them — per
`references/qa/` (raster/video/audio/… contracts). Minimum floor for any
media delivery:

- Files exist at the durable path; format/dimensions/duration match the
  brief (`ffprobe` for av media).
- Look at it: vision on images and sampled video frames; listen-check
  duration/waveform for audio. Check text-in-image spelling, anatomy,
  style consistency across the set, and continuity for video.
- For many artifacts, fan per-artifact checks out via `delegate_task` and
  keep only verdicts.

Defects go back as a feedback turn (same session). Deliver only what you
verified; close the session on acceptance.

## Pitfalls

- Generating or improvising media yourself, whatever the tier.
- Starting production without a Budget the user's plan sanctions.
- Letting a batch run before its style anchor passed.
- Re-briefing style in a revision turn — the session holds the anchors;
  name only what changes.
- Accepting "done" replies without files at durable paths.
