# Produce — the production loop (entry)

Loaded for produce-mode cards: the brief describes assets to deliver. The
kernel's contracts (Budget caps, comment protocol, fan-out) apply
throughout; this file owns the chain routing and the per-asset loop.

Intent shapes the entry (kernel <IntentTriage>):

- `new` — this file, top to bottom. A consistent batch or a high-cost
  asset without a pinned reference belongs to plan mode first
  (`references/plan.md`) — check before spending.
- `revise` — load `references/iterate.md` FIRST; it owns inheritance and
  feedback triage, then re-enters this loop for the actual re-rendering.
- `salvage` — load `references/resume.md` <Salvage> FIRST; it owns the
  inventory; this loop then covers only what genuinely must be produced.

## AssetRouting

Load the matching sibling skill for depth (skill_view; they live beside
this skill in this profile's skills tree):

| Asset | Chain | Depth skill |
| --- | --- | --- |
| still image, logo, icon set, text card, social visual | `image_gen` tool (img-xai-codex-fal chain) | `contextual-image-gen` |
| video clip, text-to-video, image-to-video | `video_gen` tool (vid-xai-fal chain) | `contextual-video-gen` |
| HTML/CSS motion graphics, product tour, captioned narration, website-to-video | `hyperframes` CLI | `hyperframes` |
| GIF, loop, poster frame | generate video first, then the bundled scripts (`to-gif.sh`, `make-loop.sh`, `poster-frame.sh`) | `contextual-video-gen` |
| voice line / narration | `tts` toolset | — |
| 3D modeling / scene / render | running desktop Blender via socket | `blender-mcp` |

The table is not closed. This profile's **available-skills catalog** already
carries far more than these core chains — the in-tree creative skills plus a
whole upstream `creative/` + `media/` library on `skills.external_dirs`
(comfyui, manim-video, ascii-video, p5js, excalidraw, touchdesigner-mcp,
gif-search, songwriting-and-ai-music, …). Before declaring an asset type
unsupported, scan that catalog and `skill_view` the match. Some carry an
availability prerequisite — a running desktop app or MCP (`blender-mcp` →
`nc -z -w2 localhost 9876`; comfyui / touchdesigner similarly). Prerequisite
unmet → `Q<n>` block stating what must be started; never fake the asset
another way.

A dispatch may **force-load a technique skill** (the task carried `skills:`
beyond the pipeline pin — e.g. `pixel-art`, `meme-generation`,
`concept-diagrams`, `baoyu-article-illustrator`, `baoyu-comic`). That skill
supplies the craft for the asset: follow it, but keep THIS pipeline's
Budget, verification, and delivery. The technique skill's own interactive
steps (its `clarify` menus) do NOT apply here — style comes from the brief
and the Budget-gated `Q<n>:` block protocol, not an inline `clarify`.

### pixel-art specifics (force-loaded `pixel-art`)

Its `pixel_art.py` converts an EXISTING image — it has no generator, so the
base is yours to make. (1) `image_generate` a base first: a bold,
flat-shaded subject on a simple background (pixel conversion collapses fine
detail), sized a few× the target sprite so the downscale keeps shape. (2)
Convert with the skill's own `pixel_art.py` (`--preset <name>` or
`--palette <NAME> --block <n>`). For a **batch, lock ONE palette across
every asset** so the set stays consistent — either the same named palette
on each run, or, for a palette taken from an approved sample,
derive-and-apply it once with this profile's
`${HERMES_SKILL_DIR}/scripts/palette-extract.py apply <sample.png> <out_dir> <base…>`.
Never let each asset quantize adaptively on its own — that drifts the set.
Do NOT edit the upstream `pixel_art.py` (read-in-place, auto-updated); the
sample-palette step lives here.

## ProductionLoop

Per asset (or batch chunk):

1. **Spec first.** Destination constraints (platform, dimensions, format,
   caps) and brand/style inputs come before the first generation — the
   depth skills open with exactly this discovery. An anchored batch reuses
   the locked anchor verbatim (`references/plan.md` <AnchorByType>).
2. **Generate deliberately** within the Budget caps: variants are for
   real alternatives, not retries of an unread failure. Post-process with
   terminal tools (ffmpeg, the bundled scripts) in the task workspace;
   keep intermediates out of the delivery.
3. **Verify before moving on** — `references/verify.md`, the intent's
   profile. A clear miss gets the corrective pass (default: one per
   asset); if it still misses, deliver the best attempt and state the gap
   plainly — exceeding the Budget instead is a `Q<n>` block, never a
   judgment call.
4. `PROGRESS:` with the running spend tally, then the next asset.

Ambiguity discovered mid-loop (a spec the brief doesn't pin, a taste fork
the anchor doesn't settle) → the kernel's block protocol: batch the
questions, checkpoint, block once.

## Handoff

All assets verified → `references/delivery.md`: attachment discipline
(including the anchor/reuse contract), the Review gate when the body
carries `Review:`, and the evidence-backed report + metadata.

## Pitfalls

- Generating before reading the whole brief (count, specs, platform,
  Budget) or before the spec/anchor is pinned.
- Skipping the plan gate on a batch because production "can start now" —
  anchor first, batch after sign-off.
- Declaring an asset type unsupported without scanning the opt-in catalog,
  or using an opt-in chain whose prerequisite isn't running.
- Letting a technique skill's inline `clarify` override the block
  protocol.
- Retrying a failed generation without reading WHY it failed — variants
  cost the same as successes.
- Verifying at the end of the whole task instead of per asset — a drifted
  spec discovered late costs the batch.

## Verification

- Every produced asset went through its `references/verify.md` intent
  profile before delivery; corrective passes stayed within caps.
- Chain/depth-skill choice matched the asset type (or the catalog scan is
  documented); prerequisites were checked before use.
- Handoff ran through `references/delivery.md` — nothing stranded, report
  evidence itemized.
