---
name: media-production
description: >-
  Creator's task front door — route every task by purpose (ModeRouting):
  produce (the production loop, in this file) vs advisory (Plan-Loop media
  consultations — feasibility, chain fit, Budget estimate; playbook in
  references/advisory.md, loaded via skill_view file_path). Production: parse
  the brief and its Budget grant (defaults 4 image variants / 2 video renders
  / 1 corrective pass; expanded only by AUTHORITY+ comments), route by asset
  type to the right generation chain (image / video / GIF / poster / voice,
  plus opt-in depth skills like blender-mcp for 3D), clarify creative
  direction through structured STATE/Qn block round-trips instead of burning
  credits on guesses, leave a per-asset PROGRESS trail, resume after unblock
  by matching DECISION(Qn) answers and reusing intermediates surviving in the
  task workspace, post-process with the bundled scripts, verify outputs
  visually, and deliver every artifact through kanban_attach with a one-line
  chat-ready summary. Deep per-type guidance lives in the sibling
  contextual-image-gen / contextual-video-gen skills.
version: 2.0.0
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

<ModeRouting>

Pick the mode first:

| Signal | Mode | Playbook |
| --- | --- | --- |
| Task body opens with `Advisory — inform the plan, don't ship.` — or only asks questions (media feasibility, chain fit, cost/Budget estimate) and requests no asset | Advisory | load `references/advisory.md` via `skill_view` (`file_path=references/advisory.md`) before doing any work |
| Anything that delivers assets | Produce | the rest of THIS file |

Advisory tasks generate nothing — no credits spent, no assets delivered; an
advisory task that turns out to need real production is reported as such,
not silently produced.

</ModeRouting>

<CommentProtocol>

Dialogue with the orchestrator travels as kanban comments with a fixed
marker as the first token (shared contract across workers). You WRITE:

- `STATE:` — before a block: what's produced so far, what the question
  decides, which intermediates sit in the workspace (they survive the
  respawn — see <Resume>), and the **spend tally** so far (e.g.
  `spend: img 3/4, corrective 0/1`) — surviving files alone can't tell how
  much budget went into failed attempts.
- `Q<n>: <question>` — numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the task's lifetime;
  batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` — per finished asset (or batch chunk): what's
  delivered-ready, what's next, ending with the running spend tally
  (`spend: img 3/4`). Comments are NOT pushed to chat; the orchestrator
  reads them on demand, so keep them frequent but terse.

You READ (written by the orchestrator):

- `DECISION(Q<n>): <choice> — <reason>` — the binding answer to your Q<n>.
- `AUTHORITY+: <grant line(s)>` — an expansion of the task's Budget (see
  <Budget>). Grants only expand; nothing shrinks mid-task.

Block mechanics: `kanban_block(kind=needs_input, reason=...)` with the
reason as a **<=160-char headline** naming the open question ids and the
crux (the chat notification truncates it) — the full `Q<n>:` text lives in
the comments. Stop producing after the block call.

</CommentProtocol>

<Brief>

The task body is the whole brief (workers never see the chat). Extract before
generating: purpose/audience, asset type(s) and count, style/tone references,
dimensions/platform specs, delivery format, and the `Budget:` line
(<Budget>). If creative direction is ambiguous and the body carries no
reference (style, aspect, tone), do ONE block round-trip per
<CommentProtocol>. Never burn generation credits guessing; never block
twice for what one batched question could settle.

</Brief>

<Budget>

Generation spend is granted, not discretionary. The body's `Budget:` line
sets the caps; absent → the defaults:

| Spend | Default cap |
| --- | --- |
| Still-image generations | 4 variants per asset |
| Video renders | 2 per asset |
| Corrective regeneration | 1 pass per asset (after <Verification>) |
| Batch quantity | exactly the brief's count |

- **Effective budget = body `Budget:` + all `AUTHORITY+:` comments**, in
  comment order.
- Need to exceed it (more variants, another render, a longer cut)? That is
  a block round-trip: `Q<n>` with the cost stated ("2 more renders,
  ~<estimate>"), never a silent overrun.
- Under-budget is always fine — stop as soon as the spec is met.

</Budget>

<AssetRouting>

Load the matching sibling skill for depth (skill_view; they live beside this
skill in this profile's skills tree):

| Asset | Chain | Depth skill |
| --- | --- | --- |
| still image, logo, icon set, text card, social visual | `image_gen` tool (img-xai-codex-fal chain) | `contextual-image-gen` |
| video clip, text-to-video, image-to-video | `video_gen` tool (vid-xai-fal chain) | `contextual-video-gen` |
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

Post-process with terminal tools (ffmpeg, the skill scripts) in the task
workspace; keep intermediate files out of the delivery.

</AssetRouting>

<Resume>

Every respawned run (task has prior runs/comments):

1. `kanban_show <id>` — rebuild the dialogue state mechanically: match every
   `Q<n>` against a `DECISION(Q<n>)` (unanswered + gating → re-block with the
   same n), and recompute the effective Budget (body + `AUTHORITY+:`
   comments).
2. **Inventory the workspace** (`$HERMES_KANBAN_WORKSPACE`): scratch dirs
   survive block/crash respawns — deletion happens only on completion. List
   what's already generated. **Spent budget stays spent**: take the tally
   from the latest `STATE:`/`PROGRESS:` comment (not from counting files —
   failed attempts also cost); no recorded tally after a crash → count
   conservatively (files present + 1).
3. **Reuse, don't regenerate**: apply the DECISION to the surviving
   intermediates (post-process, re-crop, continue the batch). Regenerate
   only what the DECISION actually invalidates.
4. Record the outcome in a short `PROGRESS:` comment.

</Resume>

<Verification>

Before completing, inspect every produced file yourself (image/video input —
vision): dimensions and format match the spec, no artifacts/garbled text, the
style matches the brief. A clear miss gets the Budget's corrective pass
(default: one per asset); if it still misses, deliver the best attempt and
state the gap plainly — exceeding the budget instead is a `Q<n>` block, not
a judgment call.

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

- Generating before reading the whole brief (count, specs, platform, Budget).
- Guessing style direction instead of one batched `Q<n>` block round-trip.
- Silently exceeding the Budget (more variants "to be safe") — expansion is
  the orchestrator's call via `AUTHORITY+:`, requested through a block.
- Regenerating after a respawn what already sits in the workspace — the
  scratch dir survives blocks; inventory before spending (<Resume>).
- Block reasons that don't survive 160-char truncation, or full questions
  living only in the reason instead of `Q<n>:` comments.
- Long batch runs with no `PROGRESS:` trail — the orchestrator's only
  mid-run visibility.
- Declaring an asset type unsupported without checking the opt-in sibling
  skills, or using an opt-in chain whose prerequisite isn't running.
- Leaving artifacts only on disk / forgetting kanban_attach.
- Completing without visually inspecting the output.
- Paths, prompts, or seeds in the kanban_complete summary line.
- Endless regeneration loops — the budgeted corrective pass, then report
  honestly.

</Pitfalls>
