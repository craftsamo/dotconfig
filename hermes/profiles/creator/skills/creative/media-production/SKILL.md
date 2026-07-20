---
name: media-production
description: Creator's production loop for kanban media tasks — parse the brief, route by asset type to the right generation chain (image / video / GIF / poster / voice), clarify creative direction via one block round-trip instead of burning credits on guesses, post-process with the bundled scripts, verify outputs visually, and deliver every artifact through kanban_attach with a one-line chat-ready summary. Deep per-type guidance lives in the shared contextual-image-gen / contextual-video-gen skills.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [media, image, video, gif, tts, production, kanban, delivery]
    category: creative
    related_skills: [contextual-image-gen, contextual-video-gen]
---

<Goal>

Turn a kanban media brief into delivered assets: right generation chain per
asset type, credits spent deliberately, outputs verified with your own eyes,
artifacts attached to the task — never stranded on disk.

</Goal>

<Scope>
<UseWhen>

- Any kanban/delegated creator task: images, video, GIFs, poster frames,
  loops, voice lines, batch or multi-asset production.

</UseWhen>
<DoNotUseWhen>

- Code, research, or writing tasks — those belong to other workers.

</DoNotUseWhen>
</Scope>

<Brief>

The task body is the whole brief (workers never see the chat). Extract before
generating: purpose/audience, asset type(s) and count, style/tone references,
dimensions/platform specs, and delivery format. If creative direction is
ambiguous and the body carries no reference (style, aspect, tone), do ONE
block round-trip: `kanban_comment` a short state note, then
`kanban_block(kind=needs_input)` with one question, 2-4 concrete options, and
your recommendation. Never burn generation credits guessing; never block
twice for what one batched question could settle.

</Brief>

<AssetRouting>

Load the matching sibling skill for depth (skill_view; they live beside this
skill in this profile's creative category):

| Asset | Chain | Depth skill |
| --- | --- | --- |
| still image, logo, icon set, text card, social visual | `image_gen` tool (img-xai-codex-fal chain) | `contextual-image-gen` |
| video clip, text-to-video, image-to-video | `video_gen` tool (vid-xai-fal chain) | `contextual-video-gen` |
| GIF, loop, poster frame | generate video first, then the bundled scripts (`to-gif.sh`, `make-loop.sh`, `poster-frame.sh`) | `contextual-video-gen` |
| voice line / narration | `tts` toolset | — |

Post-process with terminal tools (ffmpeg, the skill scripts) in the task
workspace; keep intermediate files out of the delivery.

</AssetRouting>

<Verification>

Before completing, inspect every produced file yourself (image/video input —
vision): dimensions and format match the spec, no artifacts/garbled text, the
style matches the brief. One regeneration pass for a clear miss; if it still
misses, deliver the best attempt and state the gap plainly.

</Verification>

<Delivery>

- `kanban_attach` every final artifact (scratch workspaces are deleted on
  completion — a file not attached is a file lost).
- Final message: assets produced (type, dimensions, format), chain/provider
  used, prompts or seeds worth keeping, verification result, gaps or risks.
- `kanban_complete` summary: one line of 1-2 plain user-facing sentences —
  delivered verbatim to the requester's chat; no prompts, seeds, or paths.

</Delivery>

<Pitfalls>

- Generating before reading the whole brief (count, specs, platform).
- Guessing style direction instead of one batched clarify block.
- Leaving artifacts only on disk / forgetting kanban_attach.
- Completing without visually inspecting the output.
- Paths, prompts, or seeds in the kanban_complete summary line.
- Endless regeneration loops — one corrective pass, then report honestly.

</Pitfalls>
