# Creator hands — overview

The v3 hands contract: client model, skill tree, form, handoff, media craft, migration. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Creator hands (v3, 2026-09)

Media production runs in three **hands** profiles — `image-creator`
(A2A `:9907`), `video-creator` (`:9908`) and `audio-creator` (`:9909`). Each
is a receive-only A2A endpoint with the tools of its medium and nothing else.
The Assistant commissions them; Creator only advises. Family details:
[`image.md`](./image.md), [`video.md`](./video.md), [`audio.md`](./audio.md);
the client side: [`broker.md`](../broker.md).

The rule is **one skill = one concrete deliverable = one form**, with nothing
above the skill but a reader. A hands leaf is never a technic and never a
generated index. Add no `menu.yaml`, no generated `MENU.md`, no preset layer
and no cross-media Styles — generic technics decided nothing, and a governing
layer above the leaves encoded one choice in several places and drifted.

### Client model

Specialist transport preserves the original agent request and a per-turn
private handoff record, distinguishes current instructions from non-actionable
history, and identifies the caller as an agent even during conversational
follow-ups. This is provenance for inspection, not authenticated human approval.
Keep relayed human decisions with their source/proposal/scope separate from
agent implementation choices. Do not weaken the outcome to match a template;
use the granted discretion without unnecessary repeated questions.

The hands have one **client**, the Assistant. It picks the leaf, **fills its
form** from the user's words and relayed decisions (with Creator's draft
handoff when Creator was consulted), sends it, relays proposals and approvals,
and delivers. The hands never see the user or invent requirements: they
receive a filled form or return one batched `Q<n>:` text block. A leaf may own
creative execution within that form (a storyboard or MV direction, for
example), behind its explicit proposal approval gate. A request from any other
caller is answered with a pointer to the Assistant and nothing is produced.

Creator reads the forms and option references to propose directions and
revisions, but never sends a handoff and never receives a report. When to
consult it, and how a `Q<n>:` is answered: [`broker.md`](../broker.md).

For a stuck resident transport, `specialist_session(action="reconcile", ...,
evidence=...)` verifies its recorded process group is gone and its shell lock is
absent or belongs to that same dead process. It retains an owned dead lock and
records `interrupted`, with external effects still unknown and no continuation
allowed. A2A, missing handles and foreign/unverifiable locks remain blocked.
Bookkeeping close is neither acceptance nor evidence that a retry is safe.

Acceptance follows the initial audience/outcome and the actual returned version,
not the producer's chosen metaphor or successful process exit. Record component
versions and dependent checks in existing job notes; revisions invalidate only
affected evidence. Local acceptance, preview approval and a reopened service-side
draft are separate facts. The work-continuity verification (see `AGENTS.md`)
checks routing coverage for all hands, real skill discovery and the
profile/runtime regressions; subjective comprehension and live save behavior
still need actual-use evidence.

### Skill tree

```
profiles/<hands>/skills/
  <hands>-pipeline/
    SKILL.md                 # <=40 lines: validate form -> load leaf -> run -> QA -> report
    scripts/                 # helpers shared by several leaves (e.g. img-postprocess.sh)
    <verb>/<subject>/
      SKILL.md               # name: <verb>-<subject>  (one deliverable, one form)
      references/styles/*.md # this leaf's style notes only — never cross-media
      assets/reference-*.*   # optional: a sample the leaf has actually produced
      scripts/
```

- **Verbs** (closed set): `create` — drawn deterministically from inputs
  (script / SVG / grid; free); `generate` — a model draws the pixels or the
  waveform (free local synthesis or metered provider); `edit` — transform an
  existing asset (free unless the edit itself generates); `source` — fetch a
  published asset and record its license (free); `analyze` — inspect an
  existing asset and return findings, not new/repaired media (free). Most
  analyze leaves return reply findings; analyze-ad may retain its report and
  evidence at an explicit deliver path for a later creative brief, never a new
  ad. The `create`/`generate` boundary is whether a generation model is asked
  to draw.
- **Cost is independent of verb.** `free` means no metered media-provider fee,
  not zero reasoning cost or unlimited compute. Local speech synthesis still
  has a take allowance: one take plus one corrective per script by default.
  Failed synthesis invocations count. Long free work still uses resident sessions.
- **Subjects** are concrete nouns (`icon`, `hero`, `clip`, `voice-line`),
  **unique across all hands** because the Assistant and Creator each read every
  hands' tree through one `skills.external_dirs` list; the validator
  (`validate_hands`) enforces the shape and rejects a subject that appears under
  two hands. `name` equals `<verb>-<subject>` and equals the path.
- The pipeline root holds no router and no lifecycle beyond the five steps
  above; discovery is the client reading the leaves' front matter directly. No
  generated index, no shared Style system, no palette vocabulary above the leaf.
- Hands report a defect in a leaf's own scripts or references to the
  maintainer; they never patch tracked skill roots (`skill-topology` blocks
  such writes at the tool layer).

**Execution-environment traps** go into the Procedure of the leaf that hits
them, not into a shared note:

- Japanese `。` in an argv string trips the terminal guard → pass text as a file.
- Foreground terminal calls die at 420 s → long renders run `background: true`
  and are polled.
- Vision holds ~3 images → contact sheet first, then one image at a time.
- Append each look's finding to `qa.md` before the next `vision_analyze`; an
  unwritten look did not happen — an image leaves the context three looks later.
  `qa.md` is appended, never rewritten.
- `magick montage` aborts without a default font → use `+append`.
- A multi-file `rm` trips the guard → leave `/tmp` alone.
- An inline `for` loop over a script variable trips the guard → run batches
  through a script file.
- The write guard reads the WHOLE terminal command, so `cp … && <skill script>`
  is refused → run a skill script in a command of its own.
- A 32 px tile is judged point-magnified 4x.

**Instruction context.** The hands' always-on contracts re-evaluate the named
leaf and selected references on inbound turns/completions and before a changed
operation, subject or option. The executing profile's full kernel and required
instructions must be in current context, not merely recorded as loaded.
Canonical `read_file` recovery follows genuine truncation offsets; unrecoverable
required instructions stop the action. Optional advisory references keep their
fallback. Loading never grants a new operation, resets spend or reruns a
completed render. The Assistant or Creator reading a hands form does not become
that hands' executor.

### The form (front matter is the only representation)

<!-- prettier-ignore -->
```yaml
---
name: generate-icon
description: >-
  <one sentence: what this leaf delivers, from which inputs — the only line
  a client needs to choose it>
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: image-creator
    cost: metered                      # free | metered
    output: "icon_<slug>_<size>.png (transparent, square) + .svg when vector"
    form:
      what_for:   {required: true,  label: "何のアイコンか", example: "Slack 通知 bot"}
      style:      {required: true,  options: [flat-minimal, glass, pixel, line, clay], other: true}
      background: {required: false, options: [transparent, brand-fill, tile], other: true}
      reference:  {required: false, type: image, label: "参照画像のパス"}
      note:       {required: false, type: text}
---
```

Field keys: `required` (bool), `label` / `example` (interview prompts),
`options` + `other: true` (a controlled vocabulary that still accepts a
free value — the leaf's `references/styles/<option>.md` backs each listed
option), `type` (`text` default, `image`, `file`, `path`, `int`). `note` is
the escape hatch every leaf carries. The SKILL.md body has exactly three
sections — `<Procedure>`, `<QA>`, `<Report>` — no Goal / Inputs / Presets
sections, because `description` and `form` already say that.

If a field has options and its leaf has `references/<field>/`, every
listed option must have a matching Markdown file. `style` keeps its
mandatory `references/styles/` mapping. This lets kit content tables live
under `references/contents/` without a generated registry. Theme uses
`references/themes/`; an explicit `references` declaration makes option
backing mandatory even when the directory is missing. MV keeps style
(rendering), theme (world vocabulary) and direction (staging) within one leaf.
Multi-value text fields describe their comma-list syntax in the label;
`other: true` permits that string at intake, and the leaf validates each
member. An option is not a requirement to generate every default item:
The Assistant confirms the expanded item list and spend with the user before
batch production.

Hermes discovery reads only the first 4,000 characters of a SKILL.md before
parsing YAML, so a leaf's complete front matter must close inside that prefix
(use compact labels; keep full procedures in the body) — an incomplete fence
silently collapses sibling leaves into one parent-named skill even though the
topology validator passes.

### Handoff message (Assistant → hands, A2A or resident session alike)

```
skill: generate-icon
intent: new | revise <path of the previous delivery>
deliver: ~/Workspaces/Projects/<Group>/.agent/<YYYYMMDD>-<job>/
budget: 4 variants + 1 corrective          # media calls or local speech takes
form:
  what_for: Slack 通知 bot のアプリアイコン
  style: glass
  background: transparent
  reference: /path/to/ref.png
  note: 青系、角丸は控えめ
```

The selected Group must already exist. Its draft job directory
`.agent/<YYYYMMDD>-<job>/` and job-owned descendants (such as `video-plan` or
`music-plan`) are accepted by all three hands; so are the Group root itself
and the unassigned `~/Workspaces/.agent/<YYYYMMDD>-<job>/`. Everything under `.agent/` is a draft; the Workspaces rules
own promotion and cleanup.
A job directory may be created beneath an existing parent, subject to the
leaf's exclusive-output checks. Never create a new Group or relocate a
valid Group-local job merely because it is below the Group root. This is
an operating contract, not a filesystem sandbox or upload/overwrite consent.

The hands reply with the leaf's `<Report>` (paths, every QA check with its
evidence, spend) or with one batched `Q<n>:` block naming the missing
required fields — never with a substitute. A request no leaf fits is a
finding back to the Assistant (`no skill fits: …`), which tells the user and
records it for the maintainer; neither side improvises a leaf.
Short free single-reply leaves use `specialist_call(kind="inquiry")`; anything
metered, multi-turn or longer than one reply window uses `kind="work"` from
the Assistant. Continue with the same target and returned conversation_id. Released
inputs, permissions, budgets and the exact handoff text are unchanged. CLI
calls wait within a finite deadline; A2A inbound cannot launch work and must
ask its caller to reissue the unit through a work conversation.

Transport limits: A2A identifies loopback callers by IP, not by a
cryptographically verified profile, so a verbal origin confirmation adds no
security; keep the localhost restriction and never widen the transport. All
three hands run in the single multiplex gateway; after a restart, readiness is
proven by the agent card answering HTTP 200 plus listener ownership, not by
launchctl's return. An early `Unknown toolsets: a2a` CLI warning during plugin
discovery is benign — never add a second gateway to work around it.

### Media craft knowledge

The four tracked, portable `media-craft-direction`, `media-craft-visual`,
`media-craft-motion` and `media-craft-audio` skills live in `agents/curated/`,
not in hands' production trees or generated Styles catalogs, and use the
standard shared-store install links. Creator's shared store already exposes
them; image-creator pins direction/visual, video-creator direction/visual/motion,
and audio-creator direction/audio individually, and the Assistant pins
direction. No hands receives the whole store. Each hands kernel's
`references/craft.md` owns conditional reading for all its current subjects and
actual creative decisions; Creator's entries read the same knowledge to name
directions and changes.

These are technique and judgment resources, not new forms, producer roles,
cross-media Styles, permissions, outside workflows or executable scripts. The
optional HyperFrames technical pins keep their own leaf scope and fallback
([`video.md`](./video.md) "Video authoring references"); craft pins are a
separate knowledge-only exception. Local procedures still own engines, source
integrity, proposal/preview approvals, budgets and QA commands. Required craft
bodies must be current before the affected creative decision; missing or
ambiguous knowledge is a named stop for that decision, never an install or
capability expansion. Mechanical work skips the craft reading. Audio perception
stays human-reported: acceptance uses attributed human listening, meters and ASR
never become a listening verdict, and the shared skill authorizes no new tool.
Fresh conversations are needed after an explicitly approved install/cutover.
Existing jobs and frozen outputs are not migrated. Candidate and
structural/discovery validation is neither live cutover nor artistic acceptance.

### Vision window

Native `vision_analyze` puts the image itself into the tool result, and Hermes
sends only the newest three image-bearing tool results with each request. A
step that asked for 29 frames showed three, while the other 26 results still
read "Image loaded into your context"; the model saw no image, assumed the
load had failed and asked again. In the 2026-09-23 Creator A/B one frame was
opened 68-80 times, 566-972 looks per 16 s job over 30-44 files, against 19-47
for OpenCode on the same brief. Most of the 20-40M input tokens per job were
that long history replayed, not the images.

The `vision-window` plugin (enabled on creator and the three hands) rewrites
native `vision_analyze` results through the `transform_tool_result` hook, with
no Hermes core change:

- The 4th and later image in one step returns "Image not shown: <path>. Only 3
  images can be shown to you per step ... request it again in your next step."
  The model is told the truth instead of a false "loaded".
- An image whose bytes were already shown 3 times in the turn returns "Image
  not shown again ... Use what you already noted about it." This stops
  flip-flopping comparisons; a re-rendered file has new bytes and is shown.

Which three of a parallel batch are shown follows completion order. Verified
on an isolated home with the unmodified runtime (6 parallel frames: 3 shown, 3
"not shown", and the model reported exactly which). Leaf procedures keep their
rules: contact sheets, at most three looks per step, a finding in `qa.md`
before the next look.

### Families and former technics

A family lands on its hands in steps, each verified before the next: (0)
contract and validator, (1) the hands skeleton, (2) the family's leaves proven
from the hands' own CLI with a pasted filled form, (3) both client-side
references ([`broker.md`](../broker.md) "References each side owns"), (4) a soak
through the Assistant, recording what the form got wrong.

Creator's former `creator-*` technics end with the advisor cutover. Five became
hands leaves: on image-creator the SVG diagram (`create-diagram`), grid-exact
pixel art (`create-pixel-art`), text-free generated illustration
(`generate-illustration`) and official brand-asset sourcing (the official path
of `source-icon`), and on video-creator pixel animation
(`create-pixel-animation`). The other fourteen are archived under `hermes/archive/creator-technic/`, which no profile
reads; `image_gen` / `video_gen` / `tts` / `unreal-engine` leave Creator's
toolsets with them.

| Family          | Hands         | Leaves                                                                                                            | Former technic                                                                                       |
| --------------- | ------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| icon            | image-creator | source, create, generate, edit, analyze                                                                           | `creator-logo-icons` retired; `creator-brand-asset-sourcing` folds into `source-icon`                |
| emoji           | image-creator | create, generate, edit, analyze                                                                                   | none; published glyphs use `source-icon`                                                             |
| mascot          | image-creator | generate, edit, analyze                                                                                           | none                                                                                                 |
| reimagine       | image-creator | generate                                                                                                          | none                                                                                                 |
| kit             | image-creator | source, create, generate, edit, analyze                                                                           | none maps 1:1                                                                                        |
| card            | image-creator | create, generate, edit, analyze                                                                                   | `creator-text-card` archived                                                                         |
| diagram         | image-creator | create                                                                                                            | `creator-svg-diagram` archived                                                                       |
| pixel-art       | image-creator | create                                                                                                            | `creator-pixel-art` archived                                                                         |
| illustration    | image-creator | generate                                                                                                          | `creator-generated-image` archived                                                                   |
| clip            | video-creator | generate, edit, analyze                                                                                           | `creator-generated-video` archived (local ComfyUI included)                                          |
| music-video     | video-creator | generate                                                                                                          | none                                                                                                 |
| tour            | video-creator | create                                                                                                            | `creator-html-motion` archived                                                                       |
| ad              | video-creator | analyze, create (a generated ad is generate-clip shots composed by create-ad; an authored PV is create-promotion) | none                                                                                                 |
| explainer-video | video-creator | create                                                                                                            | `creator-manim-explainer` archived                                                                   |
| promotion       | video-creator | create                                                                                                            | `creator-html-motion` archived (overlays on footage, captioned narration, audio-reactive, >60 s too) |
| story           | video-creator | create                                                                                                            | `creator-html-motion` archived                                                                       |
| master          | video-creator | create                                                                                                            | `creator-media-assembly` archived (segment sound, ducking, edit-spec trims too)                      |
| pixel-animation | video-creator | create                                                                                                            | `creator-pixel-video` archived                                                                       |
| speech          | audio-creator | generate, edit, analyze                                                                                           | voice card retired; AudioCraft/HeartMuLa/songsee withdrawn                                           |
| sfx             | audio-creator | create, generate, edit, analyze                                                                                   | none                                                                                                 |
| music           | audio-creator | create, generate, edit, analyze                                                                                   | vocal-song generation and standalone audio visualization withdrawn                                   |
| mix             | audio-creator | create, edit, analyze                                                                                             | none                                                                                                 |
